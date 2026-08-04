"""TI-0B tenant resource registry loader and read-only PostgreSQL coverage audit."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml

SCHEMA_VERSION = "aos.dev/tenant-resources/v1alpha1"
POSTGRES_KIND = "postgres_table"
CLASSIFICATIONS = frozenset(
    {"SYSTEM_GLOBAL", "PLATFORM_TEMPLATE", "TENANT_OWNED"}
)
CURRENT_STATES = frozenset({"STRONG_PK", "WEAK_PK", "NO_TENANT", "N/A"})
BASELINE_SCOPES = frozenset({"BUSINESS_DATA", "CONTROL_PLANE", "GLOBAL"})
RESOURCE_KINDS = frozenset(
    {
        POSTGRES_KIND,
        "object_store_prefix",
        "vector_records",
        "cache_namespace",
        "offline_storage",
        "message_queue",
        "scheduler_jobs",
        "process_memory",
    }
)


@dataclass(frozen=True)
class PostgresTableSnapshot:
    name: str
    tenant_columns: tuple[str, ...]
    primary_key: tuple[str, ...]
    rls_enabled: bool
    force_rls: bool

    @property
    def current_state(self) -> str:
        if not self.tenant_columns:
            return "NO_TENANT"
        if set(self.tenant_columns).issubset(self.primary_key):
            return "STRONG_PK"
        return "WEAK_PK"


def load_tenant_resource_registry() -> dict[str, Any]:
    raw = resources.files("aos_api").joinpath("tenant_resources.yaml").read_text(
        encoding="utf-8"
    )
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise TypeError("tenant resource registry root must be an object")
    return data


def validate_registry(registry: dict[str, Any] | None = None) -> list[str]:
    data = registry or load_tenant_resource_registry()
    issues: list[str] = []
    if data.get("schemaVersion") != SCHEMA_VERSION:
        issues.append(f"schemaVersion must be {SCHEMA_VERSION}")
    entries = data.get("resources")
    if not isinstance(entries, list) or not entries:
        return [*issues, "resources must be a non-empty list"]

    names: Counter[tuple[str, str]] = Counter()
    for index, entry in enumerate(entries):
        label = f"resources[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{label} must be an object")
            continue
        name = _text(entry.get("name"))
        kind = _text(entry.get("kind"))
        classification = _text(entry.get("classification"))
        current_state = _text(entry.get("currentState")) or "N/A"
        baseline_scope = _text(entry.get("baselineScope")) or (
            "BUSINESS_DATA" if classification == "TENANT_OWNED" else "GLOBAL"
        )
        if not name:
            issues.append(f"{label}.name is required")
        if kind not in RESOURCE_KINDS:
            issues.append(f"{label}.kind is invalid: {kind!r}")
        if classification not in CLASSIFICATIONS:
            issues.append(f"{label}.classification is invalid: {classification!r}")
        if current_state not in CURRENT_STATES:
            issues.append(f"{label}.currentState is invalid: {current_state!r}")
        if baseline_scope not in BASELINE_SCOPES:
            issues.append(f"{label}.baselineScope is invalid: {baseline_scope!r}")
        if not _text(entry.get("owner")):
            issues.append(f"{label}.owner is required")
        if not _text(entry.get("migrationWave")):
            issues.append(f"{label}.migrationWave is required")
        if name and kind:
            names[(kind, name)] += 1

        tenant_columns = _string_list(entry.get("tenantColumns"), label, issues)
        primary_key = _string_list(entry.get("primaryKey"), label, issues)
        target_columns = _string_list(entry.get("targetTenantColumns"), label, issues)
        if kind == POSTGRES_KIND:
            if not primary_key:
                issues.append(f"{label}.primaryKey is required for postgres_table")
            if classification == "TENANT_OWNED":
                if not target_columns:
                    issues.append(
                        f"{label}.targetTenantColumns is required for TENANT_OWNED"
                    )
                if entry.get("rlsRequired") is not True:
                    issues.append(f"{label}.rlsRequired must be true for TENANT_OWNED")
                if not isinstance(entry.get("clearOrder"), int):
                    issues.append(f"{label}.clearOrder must be an integer")
            elif entry.get("rlsRequired") is True:
                issues.append(f"{label}.rlsRequired cannot be true for global resources")
            expected_state = _state_from_columns(tenant_columns, primary_key)
            if current_state != expected_state:
                issues.append(
                    f"{label}.currentState={current_state} does not match "
                    f"tenantColumns/primaryKey ({expected_state})"
                )

    for key, count in sorted(names.items()):
        if count > 1:
            issues.append(f"duplicate resource {key[0]}:{key[1]}")
    return issues


def postgres_registry_entries(
    registry: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    data = registry or load_tenant_resource_registry()
    return {
        str(entry["name"]): entry
        for entry in data.get("resources", [])
        if isinstance(entry, dict) and entry.get("kind") == POSTGRES_KIND
    }


def read_postgres_snapshot(conn: Any) -> tuple[list[PostgresTableSnapshot], int]:
    rows = conn.execute(
        """
        WITH table_columns AS (
          SELECT c.oid, c.relname, c.relrowsecurity, c.relforcerowsecurity,
                 array_agg(a.attname ORDER BY a.attnum)
                   FILTER (WHERE a.attname IN ('org_id','project_id','workspace_id'))
                   AS tenant_columns
            FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            LEFT JOIN pg_attribute a
              ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
           WHERE n.nspname='public' AND c.relkind='r'
           GROUP BY c.oid, c.relname, c.relrowsecurity, c.relforcerowsecurity
        ), primary_keys AS (
          SELECT i.indrelid AS oid,
                 array_agg(a.attname ORDER BY key_column.ordinality) AS primary_key
            FROM pg_index i
            CROSS JOIN LATERAL unnest(i.indkey)
              WITH ORDINALITY AS key_column(attnum, ordinality)
            JOIN pg_attribute a
              ON a.attrelid=i.indrelid AND a.attnum=key_column.attnum
           WHERE i.indisprimary
           GROUP BY i.indrelid
        )
        SELECT relname, COALESCE(tenant_columns, ARRAY[]::name[]) AS tenant_columns,
               COALESCE(primary_key, ARRAY[]::name[]) AS primary_key,
               relrowsecurity, relforcerowsecurity
          FROM table_columns
          LEFT JOIN primary_keys USING (oid)
         ORDER BY relname
        """
    ).fetchall()
    policy_row = conn.execute(
        "SELECT COUNT(*) AS count FROM pg_policies WHERE schemaname='public'"
    ).fetchone()
    snapshots = [
        PostgresTableSnapshot(
            name=str(row["relname"]),
            tenant_columns=tuple(str(value) for value in row["tenant_columns"]),
            primary_key=tuple(str(value) for value in row["primary_key"]),
            rls_enabled=bool(row["relrowsecurity"]),
            force_rls=bool(row["relforcerowsecurity"]),
        )
        for row in rows
    ]
    return snapshots, int((policy_row or {}).get("count") or 0)


def build_postgres_coverage_report(
    snapshots: Iterable[PostgresTableSnapshot],
    *,
    policy_count: int,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = registry or load_tenant_resource_registry()
    validation_issues = validate_registry(data)
    expected = postgres_registry_entries(data)
    actual = {item.name: item for item in snapshots}
    unregistered = sorted(set(actual) - set(expected))
    stale = sorted(set(expected) - set(actual))
    drift: list[dict[str, Any]] = []
    for name in sorted(set(actual) & set(expected)):
        snapshot = actual[name]
        entry = expected[name]
        expected_columns = tuple(str(v) for v in entry.get("tenantColumns") or [])
        expected_primary_key = tuple(str(v) for v in entry.get("primaryKey") or [])
        expected_state = str(entry.get("currentState") or "")
        differences: dict[str, Any] = {}
        if snapshot.tenant_columns != expected_columns:
            differences["tenantColumns"] = {
                "registry": list(expected_columns),
                "database": list(snapshot.tenant_columns),
            }
        if snapshot.primary_key != expected_primary_key:
            differences["primaryKey"] = {
                "registry": list(expected_primary_key),
                "database": list(snapshot.primary_key),
            }
        if snapshot.current_state != expected_state:
            differences["currentState"] = {
                "registry": expected_state,
                "database": snapshot.current_state,
            }
        if differences:
            drift.append({"name": name, "differences": differences})

    state_counts = Counter(item.current_state for item in actual.values())
    classification_counts = Counter(
        str(entry.get("classification")) for entry in expected.values()
    )
    tenant_owned = [
        name
        for name, entry in expected.items()
        if entry.get("classification") == "TENANT_OWNED"
    ]
    tenant_owned_rls = [name for name in tenant_owned if actual.get(name) and actual[name].rls_enabled]
    tenant_owned_force_rls = [
        name for name in tenant_owned if actual.get(name) and actual[name].force_rls
    ]
    table_count = len(actual)
    covered_count = table_count - len(unregistered)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "ok": not validation_issues and not unregistered and not stale and not drift,
        "registryValidationIssues": validation_issues,
        "database": {
            "tableCount": table_count,
            "registeredTableCount": len(expected),
            "coveredTableCount": covered_count,
            "coveragePercent": round((covered_count / table_count * 100), 2)
            if table_count
            else 100.0,
            "unregisteredTables": unregistered,
            "staleRegistryTables": stale,
            "drift": drift,
            "currentStateCounts": dict(sorted(state_counts.items())),
            "classificationCounts": dict(sorted(classification_counts.items())),
            "rls": {
                "enabledTableCount": sum(item.rls_enabled for item in actual.values()),
                "forceTableCount": sum(item.force_rls for item in actual.values()),
                "policyCount": policy_count,
                "tenantOwnedEnabledCount": len(tenant_owned_rls),
                "tenantOwnedForceCount": len(tenant_owned_force_rls),
            },
        },
    }


def _state_from_columns(
    tenant_columns: list[str], primary_key: list[str]
) -> str:
    if not tenant_columns:
        return "NO_TENANT"
    if set(tenant_columns).issubset(primary_key):
        return "STRONG_PK"
    return "WEAK_PK"


def _string_list(value: Any, label: str, issues: list[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not _text(item) for item in value):
        issues.append(f"{label} list fields must contain non-empty strings")
        return []
    return [str(item).strip() for item in value]


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
