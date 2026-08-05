"""TI-0D read-only tenant ownership precheck and migration ledger builders."""
from __future__ import annotations

import ast
import os
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from psycopg import sql

from aos_api.tenant_resource_registry import (
    load_tenant_resource_registry,
    postgres_registry_entries,
    validate_registry,
)

JSON_TENANT_KEYS = (
    "org_id",
    "orgId",
    "project_id",
    "projectId",
    "workspace_id",
    "workspaceId",
)
PROBED = "PROBED"
STATIC_ONLY = "STATIC_ONLY"
NOT_CONFIGURED = "NOT_CONFIGURED"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
PROBE_ERROR = "PROBE_ERROR"


def read_postgres_precheck(
    conn: Any,
    *,
    registry: dict[str, Any] | None = None,
    test_org_id: str,
    test_project_id: str,
    target_org_id: str,
    target_project_id: str,
) -> dict[str, Any]:
    """Read aggregate ownership evidence without returning business row content."""
    data = registry or load_tenant_resource_registry()
    validation_issues = validate_registry(data)
    entries = postgres_registry_entries(data)
    json_columns = _read_json_columns(conn)
    foreign_keys = _read_foreign_keys(conn)
    table_reports: list[dict[str, Any]] = []
    scan_errors: list[dict[str, str]] = []

    for name, entry in sorted(entries.items()):
        try:
            # A bad/stale registry entry must fail only its own probe.  psycopg
            # leaves the transaction aborted after a SQL error, so isolate each
            # resource behind a savepoint and preserve the remaining evidence.
            with conn.transaction():
                table_reports.append(
                    _read_table_precheck(
                        conn,
                        name=name,
                        entry=entry,
                        json_columns=json_columns.get(name, ()),
                        foreign_keys=foreign_keys.get(name, ()),
                        test_org_id=test_org_id,
                        test_project_id=test_project_id,
                        target_org_id=target_org_id,
                        target_project_id=target_project_id,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            scan_errors.append(
                {"resource": name, "errorClass": type(exc).__name__}
            )

    state_counts = Counter(item["currentState"] for item in table_reports)
    return {
        "stage": "TI-0D",
        "mode": "READ_ONLY_AGGREGATES",
        "scanOk": not validation_issues and not scan_errors,
        "registryValidationIssues": validation_issues,
        "scanErrors": scan_errors,
        "tableCount": len(entries),
        "probedTableCount": len(table_reports),
        "currentStateCounts": dict(sorted(state_counts.items())),
        "targets": {
            "test": {"orgId": test_org_id, "projectId": test_project_id},
            "qiyue": {
                "orgId": target_org_id,
                "projectId": target_project_id,
            },
        },
        "tables": table_reports,
    }


def build_migration_ledger(postgres_precheck: Mapping[str, Any]) -> dict[str, Any]:
    resources: list[dict[str, Any]] = []
    for table in postgres_precheck.get("tables") or []:
        classification = str(table["classification"])
        state = str(table["currentState"])
        blockers: list[str] = []
        action = "retain_system_global"
        if classification == "PLATFORM_TEMPLATE":
            action = "retain_immutable_platform_template"
        elif classification == "TENANT_OWNED":
            if state == "STRONG_PK":
                action = "add_rls_and_validate_service_scope"
            elif state == "WEAK_PK":
                action = "expand_tenant_composite_key_and_foreign_keys"
                blockers.append("TENANT_COLUMNS_NOT_IN_PRIMARY_KEY")
            else:
                action = "add_tenant_scope_and_assign_ownership"
                blockers.append("TENANT_COLUMNS_MISSING")

            if int(table.get("blankTenantRowCount") or 0):
                blockers.append("BLANK_TENANT_VALUES")
            if int(table.get("unattributedRows") or 0):
                blockers.append("UNATTRIBUTED_ROWS")
            if (
                table.get("baselineScope") == "BUSINESS_DATA"
                and int(table.get("targetTenantRowCount") or 0)
            ):
                blockers.append("QIYUE_ALREADY_HAS_ROWS")
            if int(table.get("orphanRowCount") or 0):
                blockers.append("EXISTING_FOREIGN_KEY_ORPHANS")
            if not table.get("tenantForeignKeyPresent") and not table.get(
                "workspaceRoot"
            ):
                blockers.append("TENANT_COMPOSITE_FOREIGN_KEY_MISSING")

        resources.append(
            {
                "resource": table["name"],
                "classification": classification,
                "baselineScope": table["baselineScope"],
                "currentState": state,
                "migrationWave": table["migrationWave"],
                "targetTenantColumns": table["targetTenantColumns"],
                "workspaceRoot": bool(table.get("workspaceRoot")),
                "rowCount": table["rowCount"],
                "action": action,
                "blockers": sorted(set(blockers)),
                "precheckStatus": "REQUIRES_REMEDIATION" if blockers else "READY",
            }
        )
    blocker_counts = Counter(
        blocker for item in resources for blocker in item["blockers"]
    )
    return {
        "stage": "TI-0D",
        "mode": "PLAN_ONLY_NO_MUTATION",
        "resourceCount": len(resources),
        "blockerCounts": dict(sorted(blocker_counts.items())),
        "resources": resources,
    }


def build_qiyue_baseline(
    postgres_precheck: Mapping[str, Any],
    non_postgres_inventory: Mapping[str, Any],
) -> dict[str, Any]:
    tenant_tables = [
        item
        for item in postgres_precheck.get("tables") or []
        if item.get("classification") == "TENANT_OWNED"
    ]
    business_tables = [
        item for item in tenant_tables if item.get("baselineScope") == "BUSINESS_DATA"
    ]
    control_tables = [
        item for item in tenant_tables if item.get("baselineScope") == "CONTROL_PLANE"
    ]
    target_business_rows = sum(
        int(item.get("targetTenantRowCount") or 0) for item in business_tables
    )
    target_control_rows = sum(
        int(item.get("targetTenantRowCount") or 0) for item in control_tables
    )
    test_rows = sum(int(item.get("testTenantRowCount") or 0) for item in tenant_tables)
    unattributed_rows = sum(int(item.get("unattributedRows") or 0) for item in tenant_tables)
    blank_rows = sum(int(item.get("blankTenantRowCount") or 0) for item in tenant_tables)

    resource_probes = list(non_postgres_inventory.get("resources") or [])
    target_non_postgres = sum(
        int(item.get("targetTenantItemCount") or 0) for item in resource_probes
    )
    unknown_non_postgres = sum(
        int(item.get("unknownPrefixItemCount") or 0) for item in resource_probes
    )
    incomplete_resources = sorted(
        str(item.get("name"))
        for item in resource_probes
        if item.get("status") != PROBED
    )
    blockers: list[str] = []
    if not postgres_precheck.get("scanOk"):
        blockers.append("POSTGRES_PRECHECK_INCOMPLETE")
    if target_business_rows or target_non_postgres:
        blockers.append("QIYUE_DATA_PRESENT")
    if unattributed_rows:
        blockers.append("UNATTRIBUTED_POSTGRES_ROWS")
    if blank_rows:
        blockers.append("BLANK_TENANT_VALUES")
    if unknown_non_postgres:
        blockers.append("UNKNOWN_NON_POSTGRES_PREFIXES")
    if incomplete_resources:
        blockers.append("NON_POSTGRES_PROBES_INCOMPLETE")

    return {
        "stage": "TI-0D",
        "tenant": postgres_precheck.get("targets", {}).get("qiyue", {}),
        "isProvenEmpty": not blockers,
        "blockers": blockers,
        "postgres": {
            "tenantOwnedTableCount": len(tenant_tables),
            "businessTableCount": len(business_tables),
            "controlPlaneTableCount": len(control_tables),
            "targetBusinessRowCount": target_business_rows,
            "targetControlPlaneRowCount": target_control_rows,
            "targetTenantRowCount": target_business_rows + target_control_rows,
            "testTenantRowCount": test_rows,
            "unattributedRowCount": unattributed_rows,
            "blankTenantRowCount": blank_rows,
        },
        "nonPostgres": {
            "targetTenantItemCount": target_non_postgres,
            "unknownPrefixItemCount": unknown_non_postgres,
            "incompleteResources": incomplete_resources,
        },
    }


def summarize_object_keys(
    keys: Iterable[str],
    *,
    test_org_id: str,
    test_project_id: str,
    target_org_id: str,
    target_project_id: str,
    known_tenant_scopes: Iterable[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Aggregate S3 keys by canonical tenant prefix without returning any key."""
    key_list = list(keys)
    test_prefix = f"{test_org_id}/{test_project_id}/"
    target_prefix = f"{target_org_id}/{target_project_id}/"
    test_count = sum(key.startswith(test_prefix) for key in key_list)
    target_count = sum(key.startswith(target_prefix) for key in key_list)
    known = set(known_tenant_scopes)
    canonical_count = sum(_looks_like_tenant_key(key, known) for key in key_list)
    maintenance_count = sum(
        key.lstrip("/").startswith("_maintenance/quarantine/unowned/")
        for key in key_list
    )
    return {
        "itemCount": len(key_list),
        "testTenantItemCount": test_count,
        "targetTenantItemCount": target_count,
        "canonicalPrefixItemCount": canonical_count,
        "maintenanceQuarantineItemCount": maintenance_count,
        "unknownPrefixItemCount": len(key_list)
        - canonical_count
        - maintenance_count,
    }


def scan_process_memory_sources(api_root: Path) -> dict[str, Any]:
    """Static-only mutable-global inventory; never imports or reads runtime values."""
    findings: list[dict[str, str]] = []
    parse_errors = 0
    for path in sorted(api_root.rglob("*.py")):
        try:
            tree = ast.parse(
                path.read_text(encoding="utf-8-sig"), filename=str(path)
            )
        except (OSError, SyntaxError, UnicodeError):
            parse_errors += 1
            continue
        relative = path.relative_to(api_root).as_posix()
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                name, value = _assignment_name_value(node)
                kind = _mutable_value_kind(value)
                if name and kind:
                    findings.append({"path": relative, "symbol": name, "kind": kind})
            elif isinstance(node, ast.ClassDef) and any(
                _is_singleton_assignment(child) for child in node.body
            ):
                findings.append(
                    {"path": relative, "symbol": node.name, "kind": "singleton_class"}
                )
    return {
        "status": STATIC_ONLY,
        "sourceFileCount": len(list(api_root.rglob("*.py"))),
        "findingCount": len(findings),
        "parseErrorCount": parse_errors,
        "findings": findings,
        "contentInspected": False,
    }


def build_non_postgres_inventory(
    *,
    object_store_report: Mapping[str, Any],
    vector_report: Mapping[str, Any],
    process_memory_report: Mapping[str, Any],
    scheduler_report: Mapping[str, Any],
) -> dict[str, Any]:
    redis_configured = bool(os.getenv("AOS_REDIS_URL") or os.getenv("REDIS_URL"))
    broker_configured = bool(
        os.getenv("AOS_BROKER_URL")
        or os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        or os.getenv("RABBITMQ_URL")
    )
    resources = [
        {"name": "tenant-object-prefixes", **dict(object_store_report)},
        {"name": "tenant-vector-records", **dict(vector_report)},
        {
            "name": "tenant-cache-namespaces",
            "status": NOT_IMPLEMENTED if redis_configured else NOT_CONFIGURED,
            "backend": "redis" if redis_configured else "none",
        },
        {
            "name": "tenant-offline-storage",
            "status": NOT_CONFIGURED,
            "backend": "no-tenant-owned-offline-store-identified",
        },
        {
            "name": "tenant-message-queues",
            "status": NOT_IMPLEMENTED if broker_configured else NOT_CONFIGURED,
            "backend": "external" if broker_configured else "process-local-only",
        },
        {"name": "tenant-scheduler-jobs", **dict(scheduler_report)},
        {"name": "tenant-process-memory", **dict(process_memory_report)},
    ]
    return {
        "stage": "TI-0D",
        "mode": "READ_ONLY_REDACTED",
        "resourceCount": len(resources),
        "statusCounts": dict(
            sorted(Counter(str(item["status"]) for item in resources).items())
        ),
        "resources": resources,
    }


def read_vector_report(
    conn: Any,
    *,
    known_tenant_scopes: Iterable[tuple[str, str]] = (),
    test_org_id: str = "dev-org",
    test_project_id: str = "dev-project",
    target_org_id: str = "org-org",
    target_project_id: str = "dev-project",
) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT key
          FROM meta_aip_kv
         WHERE key LIKE 'vector_index:%'
        """
    ).fetchall()
    summary = summarize_vector_keys(
        (str(row["key"]) for row in rows),
        known_tenant_scopes=known_tenant_scopes,
        test_org_id=test_org_id,
        test_project_id=test_project_id,
        target_org_id=target_org_id,
        target_project_id=target_project_id,
    )
    return {
        "status": PROBED,
        "backend": "meta_aip_kv",
        **summary,
        "contentInspected": False,
    }


def summarize_vector_keys(
    keys: Iterable[str],
    *,
    known_tenant_scopes: Iterable[tuple[str, str]],
    test_org_id: str,
    test_project_id: str,
    target_org_id: str,
    target_project_id: str,
) -> dict[str, int]:
    """Aggregate canonical vector namespaces without returning logical names."""
    key_list = list(keys)
    known = set(known_tenant_scopes)
    scopes: list[tuple[str, str] | None] = []
    for key in key_list:
        value = key.removeprefix("vector_index:")
        parts = value.split("__", 2)
        scope = (parts[0], parts[1]) if len(parts) == 3 and parts[2] else None
        scopes.append(scope if scope in known else None)
    canonical_count = sum(scope is not None for scope in scopes)
    return {
        "itemCount": len(key_list),
        "testTenantItemCount": sum(
            scope == (test_org_id, test_project_id) for scope in scopes
        ),
        "targetTenantItemCount": sum(
            scope == (target_org_id, target_project_id) for scope in scopes
        ),
        "canonicalPrefixItemCount": canonical_count,
        "unknownPrefixItemCount": len(key_list) - canonical_count,
    }


def read_known_tenant_scopes(conn: Any) -> set[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT org_id, project_id FROM twa_workspace
        UNION
        SELECT org_id, project_id FROM meta_workspace
        """
    ).fetchall()
    return {
        (str(row["org_id"]), str(row["project_id"]))
        for row in rows
        if row.get("org_id") and row.get("project_id")
    }


def _read_table_precheck(
    conn: Any,
    *,
    name: str,
    entry: Mapping[str, Any],
    json_columns: Iterable[str],
    foreign_keys: Iterable[Mapping[str, Any]],
    test_org_id: str,
    test_project_id: str,
    target_org_id: str,
    target_project_id: str,
) -> dict[str, Any]:
    tenant_columns = tuple(str(value) for value in entry.get("tenantColumns") or [])
    target_columns = tuple(
        str(value) for value in entry.get("targetTenantColumns") or []
    )
    row_count = _scalar_count(
        conn, sql.SQL("SELECT COUNT(*) AS count FROM {}").format(sql.Identifier(name))
    )
    blank_count = 0
    test_count = 0
    target_count = 0
    distinct_tenant_groups = 0
    if tenant_columns:
        blank_predicate = sql.SQL(" OR ").join(
            sql.SQL("{} IS NULL OR BTRIM({}::text) = ''").format(
                sql.Identifier(column), sql.Identifier(column)
            )
            for column in tenant_columns
        )
        blank_count = _scalar_count(
            conn,
            sql.SQL("SELECT COUNT(*) AS count FROM {} WHERE {}").format(
                sql.Identifier(name), blank_predicate
            ),
        )
        test_count = _tenant_count(
            conn,
            name=name,
            tenant_columns=tenant_columns,
            org_id=test_org_id,
            project_id=test_project_id,
        )
        target_count = _tenant_count(
            conn,
            name=name,
            tenant_columns=tenant_columns,
            org_id=target_org_id,
            project_id=target_project_id,
        )
        distinct_tenant_groups = _distinct_tenant_groups(
            conn, name=name, tenant_columns=tenant_columns
        )

    json_marker_counts = {
        column: _json_marker_count(conn, table=name, column=column)
        for column in json_columns
    }
    fk_reports = [
        {
            **dict(foreign_key),
            "orphanRowCount": _foreign_key_orphan_count(
                conn, table=name, foreign_key=foreign_key
            ),
        }
        for foreign_key in foreign_keys
    ]
    orphan_count = sum(int(item["orphanRowCount"]) for item in fk_reports)
    tenant_fk_present = any(
        set(target_columns).issubset(set(item.get("sourceColumns") or []))
        for item in fk_reports
    ) if target_columns else False
    classification = str(entry["classification"])
    baseline_scope = str(
        entry.get("baselineScope")
        or ("BUSINESS_DATA" if classification == "TENANT_OWNED" else "GLOBAL")
    )
    unattributed_rows = (
        row_count
        if classification == "TENANT_OWNED" and not tenant_columns
        else blank_count
    )
    return {
        "name": name,
        "classification": classification,
        "baselineScope": baseline_scope,
        "currentState": entry["currentState"],
        "migrationWave": entry["migrationWave"],
        "workspaceRoot": bool(entry.get("workspaceRoot")),
        "tenantColumns": list(tenant_columns),
        "targetTenantColumns": list(target_columns),
        "primaryKey": list(entry.get("primaryKey") or []),
        "rowCount": row_count,
        "blankTenantRowCount": blank_count,
        "unattributedRows": unattributed_rows,
        "testTenantRowCount": test_count,
        "targetTenantRowCount": target_count,
        "otherAttributedRowCount": max(
            0, row_count - blank_count - test_count - target_count
        ) if tenant_columns else 0,
        "distinctTenantGroupCount": distinct_tenant_groups,
        "duplicateCurrentPrimaryKeyGroups": 0,
        "jsonTenantMarkerCounts": json_marker_counts,
        "foreignKeys": fk_reports,
        "orphanRowCount": orphan_count,
        "tenantForeignKeyPresent": tenant_fk_present,
    }


def _read_json_columns(conn: Any) -> dict[str, tuple[str, ...]]:
    rows = conn.execute(
        """
        SELECT table_name, column_name
          FROM information_schema.columns
         WHERE table_schema='public' AND data_type IN ('json', 'jsonb')
         ORDER BY table_name, ordinal_position
        """
    ).fetchall()
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(str(row["table_name"]), []).append(str(row["column_name"]))
    return {name: tuple(columns) for name, columns in grouped.items()}


def _read_foreign_keys(conn: Any) -> dict[str, tuple[dict[str, Any], ...]]:
    rows = conn.execute(
        """
        SELECT con.conname, child.relname AS source_table,
               parent.relname AS target_table,
               array_agg(child_col.attname ORDER BY key_pair.ordinality) AS source_columns,
               array_agg(parent_col.attname ORDER BY key_pair.ordinality) AS target_columns
          FROM pg_constraint con
          JOIN pg_class child ON child.oid=con.conrelid
          JOIN pg_namespace child_ns ON child_ns.oid=child.relnamespace
          JOIN pg_class parent ON parent.oid=con.confrelid
          CROSS JOIN LATERAL unnest(con.conkey, con.confkey)
            WITH ORDINALITY AS key_pair(child_attnum, parent_attnum, ordinality)
          JOIN pg_attribute child_col
            ON child_col.attrelid=child.oid AND child_col.attnum=key_pair.child_attnum
          JOIN pg_attribute parent_col
            ON parent_col.attrelid=parent.oid AND parent_col.attnum=key_pair.parent_attnum
         WHERE con.contype='f' AND child_ns.nspname='public'
         GROUP BY con.conname, child.relname, parent.relname
         ORDER BY child.relname, con.conname
        """
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["source_table"]), []).append(
            {
                "constraint": str(row["conname"]),
                "targetTable": str(row["target_table"]),
                "sourceColumns": [str(value) for value in row["source_columns"]],
                "targetColumns": [str(value) for value in row["target_columns"]],
            }
        )
    return {name: tuple(items) for name, items in grouped.items()}


def _tenant_count(
    conn: Any,
    *,
    name: str,
    tenant_columns: tuple[str, ...],
    org_id: str,
    project_id: str,
) -> int:
    values = [org_id]
    if len(tenant_columns) > 1:
        values.extend(project_id for _ in tenant_columns[1:])
    predicate = sql.SQL(" AND ").join(
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in tenant_columns
    )
    query = sql.SQL("SELECT COUNT(*) AS count FROM {} WHERE {}").format(
        sql.Identifier(name), predicate
    )
    return _scalar_count(conn, query, values)


def _distinct_tenant_groups(
    conn: Any, *, name: str, tenant_columns: tuple[str, ...]
) -> int:
    columns = sql.SQL(", ").join(sql.Identifier(column) for column in tenant_columns)
    query = sql.SQL(
        "SELECT COUNT(*) AS count FROM (SELECT 1 FROM {} GROUP BY {}) AS groups"
    ).format(sql.Identifier(name), columns)
    return _scalar_count(conn, query)


def _json_marker_count(conn: Any, *, table: str, column: str) -> int:
    keys = sql.SQL(", ").join(sql.Literal(key) for key in JSON_TENANT_KEYS)
    query = sql.SQL(
        "SELECT COUNT(*) AS count FROM {} WHERE COALESCE({}::jsonb, '{{}}'::jsonb) ?| ARRAY[{}]"
    ).format(sql.Identifier(table), sql.Identifier(column), keys)
    return _scalar_count(conn, query)


def _foreign_key_orphan_count(
    conn: Any, *, table: str, foreign_key: Mapping[str, Any]
) -> int:
    source_columns = [str(value) for value in foreign_key["sourceColumns"]]
    target_columns = [str(value) for value in foreign_key["targetColumns"]]
    join_predicate = sql.SQL(" AND ").join(
        sql.SQL("parent.{} = child.{}").format(
            sql.Identifier(target), sql.Identifier(source)
        )
        for source, target in zip(source_columns, target_columns, strict=True)
    )
    non_null_predicate = sql.SQL(" AND ").join(
        sql.SQL("child.{} IS NOT NULL").format(sql.Identifier(column))
        for column in source_columns
    )
    query = sql.SQL(
        "SELECT COUNT(*) AS count FROM {} AS child WHERE {} AND NOT EXISTS "
        "(SELECT 1 FROM {} AS parent WHERE {})"
    ).format(
        sql.Identifier(table),
        non_null_predicate,
        sql.Identifier(str(foreign_key["targetTable"])),
        join_predicate,
    )
    return _scalar_count(conn, query)


def _scalar_count(conn: Any, query: Any, params: list[str] | None = None) -> int:
    row = conn.execute(query, params or []).fetchone()
    return int((row or {}).get("count") or 0)


def _looks_like_tenant_key(key: str, known: set[tuple[str, str]]) -> bool:
    parts = key.split("/", 2)
    scope = (parts[0], parts[1]) if len(parts) >= 3 else ("", "")
    return bool(scope[0].strip()) and bool(scope[1].strip()) and (
        not known or scope in known
    )


def _assignment_name_value(node: ast.Assign | ast.AnnAssign) -> tuple[str, ast.AST | None]:
    if isinstance(node, ast.AnnAssign):
        return _target_name(node.target), node.value
    if len(node.targets) != 1:
        return "", node.value
    return _target_name(node.targets[0]), node.value


def _target_name(target: ast.AST) -> str:
    return target.id if isinstance(target, ast.Name) else ""


def _mutable_value_kind(value: ast.AST | None) -> str:
    if isinstance(value, ast.Dict):
        return "dict"
    if isinstance(value, ast.List):
        return "list"
    if isinstance(value, ast.Set):
        return "set"
    if isinstance(value, ast.Call):
        name = _call_name(value.func)
        if name in {"dict", "list", "set", "defaultdict", "Queue"}:
            return name
    return ""


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_singleton_assignment(node: ast.stmt) -> bool:
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return False
    name, _value = _assignment_name_value(node)
    return name in {"_instance", "instance"}


def postgres_scheduler_report(postgres_precheck: Mapping[str, Any]) -> dict[str, Any]:
    schedule = next(
        (
            item
            for item in postgres_precheck.get("tables") or []
            if item.get("name") == "meta_schedule"
        ),
        None,
    )
    if not schedule:
        return {"status": NOT_IMPLEMENTED, "backend": "meta_schedule", "itemCount": 0}
    return {
        "status": PROBED,
        "backend": "meta_schedule",
        "itemCount": int(schedule["rowCount"]),
        "testTenantItemCount": int(schedule["testTenantRowCount"]),
        "targetTenantItemCount": int(schedule["targetTenantRowCount"]),
        "unknownPrefixItemCount": int(schedule["unattributedRows"]),
    }
