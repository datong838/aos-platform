from __future__ import annotations

from collections import Counter

from aos_api.tenant_resource_registry import (
    PostgresTableSnapshot,
    build_postgres_coverage_report,
    load_tenant_resource_registry,
    postgres_registry_entries,
    validate_registry,
)


def _snapshots_from_registry() -> list[PostgresTableSnapshot]:
    return [
        PostgresTableSnapshot(
            name=name,
            tenant_columns=tuple(entry["tenantColumns"]),
            primary_key=tuple(entry["primaryKey"]),
            rls_enabled=False,
            force_rls=False,
        )
        for name, entry in postgres_registry_entries().items()
    ]


def test_registry_is_valid_and_covers_current_postgres_inventory() -> None:
    registry = load_tenant_resource_registry()
    entries = postgres_registry_entries(registry)

    assert validate_registry(registry) == []
    assert len(entries) == 95
    assert Counter(entry["currentState"] for entry in entries.values()) == {
        "STRONG_PK": 40,
        "WEAK_PK": 28,
        "NO_TENANT": 27,
    }


def test_registry_separates_templates_globals_and_tenant_instances() -> None:
    registry = load_tenant_resource_registry()
    entries = postgres_registry_entries(registry)

    assert entries["asset_bundle"]["classification"] == "PLATFORM_TEMPLATE"
    assert entries["bundle_installation"]["classification"] == "TENANT_OWNED"
    assert entries["meta_org"]["classification"] == "SYSTEM_GLOBAL"
    assert entries["meta_module"]["classification"] == "TENANT_OWNED"
    assert entries["meta_module"]["currentState"] == "WEAK_PK"
    assert entries["ecom_object"]["canonicalProjectAlias"] == "workspace_id"

    non_table_kinds = {
        entry["kind"]
        for entry in registry["resources"]
        if entry["kind"] != "postgres_table"
    }
    assert non_table_kinds == {
        "object_store_prefix",
        "vector_records",
        "cache_namespace",
        "offline_storage",
        "message_queue",
        "scheduler_jobs",
        "process_memory",
    }

    execution_groups = registry["executionPlan"]["groups"]
    planned_resources = [
        name for group in execution_groups for name in group["resources"]
    ]
    assert registry["executionPlan"]["authorization"] == "PLAN_ONLY"
    assert len(planned_resources) == len(set(planned_resources)) == 102


def test_coverage_report_accepts_exact_inventory_without_claiming_rls_green() -> None:
    report = build_postgres_coverage_report(
        _snapshots_from_registry(), policy_count=0
    )

    assert report["ok"] is True
    assert report["database"]["tableCount"] == 95
    assert report["database"]["coveragePercent"] == 100.0
    assert report["database"]["rls"]["enabledTableCount"] == 0
    assert report["database"]["rls"]["policyCount"] == 0


def test_coverage_report_fails_closed_on_unregistered_and_schema_drift() -> None:
    snapshots = _snapshots_from_registry()
    snapshots[0] = PostgresTableSnapshot(
        name=snapshots[0].name,
        tenant_columns=("org_id",),
        primary_key=snapshots[0].primary_key,
        rls_enabled=False,
        force_rls=False,
    )
    snapshots.append(
        PostgresTableSnapshot(
            name="unregistered_table",
            tenant_columns=(),
            primary_key=("id",),
            rls_enabled=False,
            force_rls=False,
        )
    )

    report = build_postgres_coverage_report(snapshots, policy_count=0)

    assert report["ok"] is False
    assert report["database"]["unregisteredTables"] == ["unregistered_table"]
    assert report["database"]["drift"][0]["name"] == "aip_eval_report"
