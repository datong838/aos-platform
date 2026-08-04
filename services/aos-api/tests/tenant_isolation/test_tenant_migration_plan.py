from __future__ import annotations

from aos_api.tenant_migration_plan import build_ti0e_artifacts
from aos_api.tenant_resource_registry import load_tenant_resource_registry


def _ledger() -> dict:
    return {
        "resources": [
            {
                "resource": "authz_tuple",
                "rowCount": 9,
                "blockers": ["TENANT_COLUMNS_MISSING", "UNATTRIBUTED_ROWS"],
            }
        ]
    }


def _non_postgres() -> dict:
    names = {
        "tenant-object-prefixes": "PROBED",
        "tenant-vector-records": "PROBED",
        "tenant-cache-namespaces": "NOT_CONFIGURED",
        "tenant-offline-storage": "NOT_IMPLEMENTED",
        "tenant-message-queues": "NOT_CONFIGURED",
        "tenant-scheduler-jobs": "PROBED",
        "tenant-process-memory": "STATIC_ONLY",
    }
    return {
        "resources": [
            {"name": name, "status": status} for name, status in names.items()
        ]
    }


def test_ti0e_plan_covers_every_registry_resource_once() -> None:
    registry = load_tenant_resource_registry()
    artifacts = build_ti0e_artifacts(
        registry=registry,
        migration_ledger=_ledger(),
        non_postgres_inventory=_non_postgres(),
    )
    order = artifacts["ti0e-migration-order.json"]
    names = [
        resource["name"]
        for group in order["groups"]
        for resource in group["resources"]
    ]

    assert order["mode"] == "PLAN_ONLY"
    assert order["resourceCount"] == 102
    assert len(names) == len(set(names)) == 102
    assert set(names) == {entry["name"] for entry in registry["resources"]}


def test_ti0e_plan_preserves_blockers_and_never_authorizes_execution() -> None:
    artifacts = build_ti0e_artifacts(
        migration_ledger=_ledger(),
        non_postgres_inventory=_non_postgres(),
    )
    order = artifacts["ti0e-migration-order.json"]
    authz = next(
        resource
        for group in order["groups"]
        for resource in group["resources"]
        if resource["name"] == "authz_tuple"
    )
    rollback = artifacts["ti0e-rollback-points.json"]

    assert authz["executionStatus"] == "BLOCKED_BEFORE_E3"
    assert authz["blockers"] == ["TENANT_COLUMNS_MISSING", "UNATTRIBUTED_ROWS"]
    assert rollback["automaticExecutionAllowed"] is False
    assert rollback["points"][-1]["authorization"] == "TI_6_APPROVAL_REQUIRED"


def test_each_wave_has_all_six_required_test_types() -> None:
    artifacts = build_ti0e_artifacts(
        migration_ledger=_ledger(),
        non_postgres_inventory=_non_postgres(),
    )
    matrix = artifacts["ti0e-test-matrix.json"]

    assert len(matrix["waves"]) == 5
    assert all(len(wave["tests"]) == 6 for wave in matrix["waves"])
    assert all(
        all(test["required"] for test in wave["tests"])
        for wave in matrix["waves"]
    )
