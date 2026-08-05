from __future__ import annotations

import json
from pathlib import Path

from aos_api.tenant_precheck import (
    PROBED,
    STATIC_ONLY,
    build_migration_ledger,
    build_non_postgres_inventory,
    build_qiyue_baseline,
    scan_process_memory_sources,
    summarize_object_keys,
    summarize_vector_keys,
)


def _table(
    name: str,
    *,
    state: str,
    row_count: int,
    target_count: int = 0,
    test_count: int = 0,
    unattributed: int = 0,
) -> dict:
    return {
        "name": name,
        "classification": "TENANT_OWNED",
        "baselineScope": "BUSINESS_DATA",
        "currentState": state,
        "migrationWave": "TI-3",
        "targetTenantColumns": ["org_id", "project_id"],
        "rowCount": row_count,
        "targetTenantRowCount": target_count,
        "testTenantRowCount": test_count,
        "unattributedRows": unattributed,
        "blankTenantRowCount": 0,
        "orphanRowCount": 0,
        "tenantForeignKeyPresent": False,
    }


def test_object_key_summary_returns_counts_without_keys() -> None:
    result = summarize_object_keys(
        [
            "dev-org/dev-project/mediasets/a.png",
            "org-org/dev-project/mediasets/b.png",
            "unknown/prefix/value.bin",
            "dev-probes/aos-t42-probe.txt",
            "_maintenance/quarantine/unowned/probe.bin",
        ],
        test_org_id="dev-org",
        test_project_id="dev-project",
        target_org_id="org-org",
        target_project_id="dev-project",
        known_tenant_scopes={
            ("dev-org", "dev-project"),
            ("org-org", "dev-project"),
        },
    )

    assert result == {
        "itemCount": 5,
        "testTenantItemCount": 1,
        "targetTenantItemCount": 1,
        "canonicalPrefixItemCount": 2,
        "maintenanceQuarantineItemCount": 1,
        "unknownPrefixItemCount": 2,
    }
    assert "keys" not in result


def test_vector_key_summary_recognizes_scoped_collection_contract() -> None:
    result = summarize_vector_keys(
        [
            "vector_index:dev-org__dev-project__demo-pipe",
            "vector_index:org-org__dev-project__catalog",
            "vector_index:legacy-name",
        ],
        known_tenant_scopes={
            ("dev-org", "dev-project"),
            ("org-org", "dev-project"),
        },
        test_org_id="dev-org",
        test_project_id="dev-project",
        target_org_id="org-org",
        target_project_id="dev-project",
    )

    assert result == {
        "itemCount": 3,
        "testTenantItemCount": 1,
        "targetTenantItemCount": 1,
        "canonicalPrefixItemCount": 2,
        "unknownPrefixItemCount": 1,
    }


def test_migration_ledger_fails_closed_for_weak_and_unattributed_tables() -> None:
    report = {
        "tables": [
            _table("meta_module", state="WEAK_PK", row_count=3, test_count=3),
            _table(
                "obj_instance",
                state="NO_TENANT",
                row_count=7,
                unattributed=7,
            ),
        ]
    }

    ledger = build_migration_ledger(report)

    assert ledger["resourceCount"] == 2
    assert ledger["blockerCounts"]["TENANT_COLUMNS_NOT_IN_PRIMARY_KEY"] == 1
    assert ledger["blockerCounts"]["TENANT_COLUMNS_MISSING"] == 1
    assert ledger["blockerCounts"]["UNATTRIBUTED_ROWS"] == 1
    assert all(item["precheckStatus"] == "REQUIRES_REMEDIATION" for item in ledger["resources"])


def test_qiyue_baseline_is_not_empty_when_any_resource_is_unprobed() -> None:
    postgres = {
        "scanOk": True,
        "targets": {"qiyue": {"orgId": "org-org", "projectId": "dev-project"}},
        "tables": [_table("meta_module", state="STRONG_PK", row_count=0)],
    }
    non_postgres = {
        "resources": [
            {
                "name": "tenant-object-prefixes",
                "status": PROBED,
                "targetTenantItemCount": 0,
                "unknownPrefixItemCount": 0,
            },
            {"name": "tenant-process-memory", "status": STATIC_ONLY},
        ]
    }

    baseline = build_qiyue_baseline(postgres, non_postgres)

    assert baseline["isProvenEmpty"] is False
    assert baseline["blockers"] == ["NON_POSTGRES_PROBES_INCOMPLETE"]
    assert baseline["nonPostgres"]["incompleteResources"] == [
        "tenant-process-memory"
    ]


def test_qiyue_baseline_detects_existing_and_unattributed_rows() -> None:
    postgres = {
        "scanOk": True,
        "targets": {"qiyue": {"orgId": "org-org", "projectId": "dev-project"}},
        "tables": [
            _table(
                "obj_instance",
                state="NO_TENANT",
                row_count=5,
                target_count=2,
                unattributed=3,
            )
        ],
    }
    non_postgres = {"resources": []}

    baseline = build_qiyue_baseline(postgres, non_postgres)

    assert baseline["isProvenEmpty"] is False
    assert "QIYUE_DATA_PRESENT" in baseline["blockers"]
    assert "UNATTRIBUTED_POSTGRES_ROWS" in baseline["blockers"]


def test_qiyue_baseline_separates_required_control_plane_rows() -> None:
    control = _table(
        "meta_workspace", state="STRONG_PK", row_count=1, target_count=1
    )
    control["baselineScope"] = "CONTROL_PLANE"
    postgres = {
        "scanOk": True,
        "targets": {"qiyue": {"orgId": "org-org", "projectId": "dev-project"}},
        "tables": [control],
    }

    baseline = build_qiyue_baseline(postgres, {"resources": []})

    assert baseline["blockers"] == []
    assert baseline["postgres"]["targetBusinessRowCount"] == 0
    assert baseline["postgres"]["targetControlPlaneRowCount"] == 1
    assert baseline["isProvenEmpty"] is True


def test_process_memory_scan_is_static_and_never_serializes_values(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(
        'SECRET = {"token": "must-not-leak"}\n'
        "QUEUE = Queue()\n"
        "class Store:\n"
        "    _instance = None\n",
        encoding="utf-8",
    )

    report = scan_process_memory_sources(tmp_path)
    encoded = json.dumps(report)

    assert report["status"] == STATIC_ONLY
    assert report["findingCount"] == 3
    assert report["contentInspected"] is False
    assert "must-not-leak" not in encoded


def test_non_postgres_inventory_preserves_incomplete_probe_states() -> None:
    inventory = build_non_postgres_inventory(
        object_store_report={"status": PROBED, "itemCount": 0},
        vector_report={"status": PROBED, "itemCount": 0},
        process_memory_report={"status": STATIC_ONLY, "findingCount": 4},
        scheduler_report={"status": PROBED, "itemCount": 0},
    )

    assert inventory["resourceCount"] == 7
    assert inventory["statusCounts"][PROBED] == 3
    assert inventory["statusCounts"][STATIC_ONLY] == 1
    assert inventory["statusCounts"]["NOT_CONFIGURED"] == 3
    assert "NOT_IMPLEMENTED" not in inventory["statusCounts"]
