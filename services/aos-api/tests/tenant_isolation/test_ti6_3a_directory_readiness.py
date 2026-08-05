from __future__ import annotations

import importlib.util
from pathlib import Path

from aos_api.db import connect
from aos_api.tenant_precheck import build_microshop_readiness

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti6e_directory_readiness.py"


def _migration_module():
    spec = importlib.util.spec_from_file_location("ti6_3a_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _postgres(*, business_rows: int = 0) -> dict:
    return {
        "scanOk": True,
        "targets": {"qiyue": {"orgId": "org-org", "projectId": "dev-project"}},
        "tables": [
            {
                "classification": "TENANT_OWNED",
                "baselineScope": "BUSINESS_DATA",
                "targetTenantRowCount": business_rows,
                "testTenantRowCount": 1,
                "blankTenantRowCount": 0,
                "unattributedRows": 0,
            }
        ],
    }


def _non_postgres(*, target_items: int = 0) -> dict:
    return {
        "resources": [
            {
                "name": "objects",
                "status": "PROBED",
                "targetTenantItemCount": target_items,
                "unknownPrefixItemCount": 0,
            }
        ]
    }


def _directory() -> dict:
    return {
        "testOrgNames": {"meta": "测试组织", "authoritative": "测试组织"},
        "targetOrgNames": {
            "meta": "栖月汇商贸有限公司",
            "authoritative": "栖月汇商贸有限公司",
        },
        "targetWorkspacePresent": {"meta": True, "authoritative": True},
    }


def test_ti6_3a_directory_migration_is_frozen() -> None:
    module = _migration_module()
    assert module.revision == "228ti6edirectory"
    assert module.down_revision == "228ti6drelations"


def test_ti6_3a_live_directory_is_aligned() -> None:
    with connect() as conn:
        names = conn.execute(
            "SELECT 'meta' AS source,name FROM meta_org WHERE id='dev-org' "
            "UNION ALL SELECT 'twa',name FROM twa_org WHERE id='dev-org'"
        ).fetchall()
        qiyue = conn.execute(
            "SELECT (SELECT COUNT(*) FROM twa_org WHERE id='org-org') AS orgs,"
            "(SELECT COUNT(*) FROM twa_workspace WHERE org_id='org-org' "
            "AND project_id='dev-project') AS workspaces"
        ).fetchone()

    assert {row["name"] for row in names} == {"测试组织"}
    assert qiyue == {"orgs": 1, "workspaces": 1}


def test_ti6_3a_local_and_production_gates_are_separate() -> None:
    readiness = build_microshop_readiness(
        _postgres(), _non_postgres(), _directory(), active_module_count=0
    )

    assert readiness["localDevelopmentReady"] is True
    assert readiness["productionDeploymentReady"] is False
    assert readiness["localBlockers"] == []
    assert "TI1_E4_HISTORICAL_QUARANTINE" in readiness["productionBlockers"]


def test_ti6_3a_local_gate_fails_on_target_data_or_installed_module() -> None:
    readiness = build_microshop_readiness(
        _postgres(business_rows=1),
        _non_postgres(target_items=1),
        _directory(),
        active_module_count=1,
    )

    assert readiness["localDevelopmentReady"] is False
    assert set(readiness["localBlockers"]) == {
        "QIYUE_BUSINESS_DATA_PRESENT",
        "QIYUE_INSTALLED_MODULES_PRESENT",
        "QIYUE_NON_POSTGRES_DATA_PRESENT",
    }
