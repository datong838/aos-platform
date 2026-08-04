"""Read-only TI-1 E1 schema lint."""
from __future__ import annotations

from typing import Any

TI1_E1_REVISION = "228ti1e1expand"
TI1_E2_REVISION = "228ti1e2dual"
TI1_E3_REVISION = "228ti1e3ledger"
TI1_E3_EXEC_REVISION = "228ti1e3exec"
AUTHZ_COLUMNS = frozenset({"org_id", "project_id"})
EXPECTED_FOREIGN_KEYS = frozenset(
    {
        "fk_meta_workspace_org_ti1",
        "fk_meta_membership_workspace_ti1",
        "fk_twa_ws_member_workspace_ti1",
        "fk_twa_invite_workspace_ti1",
        "fk_twa_join_request_workspace_ti1",
        "fk_twa_audit_workspace_ti1",
        "fk_authz_tuple_workspace_ti1",
    }
)


def build_ti1_e1_schema_report(conn: Any) -> dict[str, Any]:
    column_rows = conn.execute(
        """
        SELECT column_name, is_nullable
          FROM information_schema.columns
         WHERE table_schema='public' AND table_name='authz_tuple'
           AND column_name IN ('org_id', 'project_id')
         ORDER BY column_name
        """
    ).fetchall()
    constraint_rows = conn.execute(
        """
        SELECT conname, convalidated
          FROM pg_constraint
         WHERE conname LIKE 'fk_%_ti1'
         ORDER BY conname
        """
    ).fetchall()
    rls_row = conn.execute(
        """
        SELECT COUNT(*) AS count
          FROM pg_class c
          JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='public' AND c.relkind='r'
           AND (c.relrowsecurity OR c.relforcerowsecurity)
        """
    ).fetchone()
    revision_row = conn.execute(
        "SELECT version_num FROM alembic_version"
    ).fetchone()

    columns = {str(row["column_name"]): row for row in column_rows}
    constraints = {str(row["conname"]): row for row in constraint_rows}
    missing_columns = sorted(AUTHZ_COLUMNS - set(columns))
    non_nullable_columns = sorted(
        name for name, row in columns.items() if row["is_nullable"] != "YES"
    )
    missing_constraints = sorted(EXPECTED_FOREIGN_KEYS - set(constraints))
    prematurely_validated = sorted(
        name for name, row in constraints.items() if bool(row["convalidated"])
    )
    rls_table_count = int((rls_row or {}).get("count") or 0)
    revision = str((revision_row or {}).get("version_num") or "")
    issues: list[str] = []
    if missing_columns:
        issues.append("AUTHZ_TENANT_COLUMNS_MISSING")
    if non_nullable_columns:
        issues.append("AUTHZ_TENANT_COLUMNS_NOT_NULLABLE")
    if missing_constraints:
        issues.append("TI1_FOREIGN_KEYS_MISSING")
    if prematurely_validated:
        issues.append("TI1_FOREIGN_KEYS_PREMATURELY_VALIDATED")
    if rls_table_count:
        issues.append("RLS_ENABLED_BEFORE_E6")
    if revision not in {
        TI1_E1_REVISION,
        TI1_E2_REVISION,
        TI1_E3_REVISION,
        TI1_E3_EXEC_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")
    return {
        "stage": "TI-1-E1",
        "mode": "READ_ONLY_SCHEMA_LINT",
        "ok": not issues,
        "issues": issues,
        "alembicRevision": revision,
        "authzTenantColumns": sorted(columns),
        "authzNonNullableColumns": non_nullable_columns,
        "foreignKeyCount": len(constraints),
        "missingForeignKeys": missing_constraints,
        "prematurelyValidatedForeignKeys": prematurely_validated,
        "rlsEnabledOrForcedTableCount": rls_table_count,
    }


def build_ti1_e2_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti1_e1_schema_report(conn)
    column_rows = conn.execute(
        """
        SELECT column_name, is_nullable
          FROM information_schema.columns
         WHERE table_schema='public'
           AND table_name='tenant_dual_write_ledger'
         ORDER BY ordinal_position
        """
    ).fetchall()
    columns = {str(row["column_name"]): str(row["is_nullable"]) for row in column_rows}
    required = {
        "org_id",
        "project_id",
        "ledger_id",
        "resource",
        "operation",
        "key_hash",
        "observed_org_id",
        "observed_project_id",
        "status",
        "created_at",
    }
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] != TI1_E2_REVISION:
        issues.append("ALEMBIC_REVISION_MISMATCH")
    missing = sorted(required - set(columns))
    if missing:
        issues.append("DUAL_WRITE_LEDGER_COLUMNS_MISSING")
    unexpectedly_nullable = sorted(
        name
        for name in required - {"observed_org_id", "observed_project_id"}
        if columns.get(name) == "YES"
    )
    if unexpectedly_nullable:
        issues.append("DUAL_WRITE_LEDGER_REQUIRED_COLUMNS_NULLABLE")
    return {
        **report,
        "stage": "TI-1-E2",
        "ok": not issues,
        "issues": issues,
        "dualWriteLedgerColumns": sorted(columns),
        "dualWriteLedgerMissingColumns": missing,
        "dualWriteLedgerUnexpectedlyNullableColumns": unexpectedly_nullable,
    }


E3_REQUIRED_COLUMNS = {
    "tenant_backfill_batch": {
        "org_id", "project_id", "batch_id", "environment_hash",
        "source_snapshot_hash", "code_commit", "mode", "status",
        "created_at", "approved_at", "completed_at",
    },
    "tenant_backfill_batch_event": {
        "org_id", "project_id", "event_id", "batch_id", "status",
        "evidence_hash", "actor_role", "actor_hash", "created_at",
    },
    "tenant_ownership_decision": {
        "org_id", "project_id", "decision_id", "batch_id", "resource",
        "key_hash", "decision", "evidence_grade", "evidence_hash",
        "candidate_count", "target_org_id", "target_project_id",
        "before_hash", "after_hash", "reason_code", "created_at",
    },
    "tenant_ownership_decision_event": {
        "org_id", "project_id", "event_id", "batch_id", "resource",
        "key_hash", "event_type", "before_hash", "after_hash",
        "evidence_hash", "actor_role", "actor_hash", "created_at",
    },
    "tenant_quarantine_record": {
        "org_id", "project_id", "quarantine_id", "batch_id", "resource",
        "key_hash", "reason_code", "candidate_scope_hashes",
        "source_snapshot_hash", "review_status", "created_at",
    },
}


def build_ti1_e3_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti1_e2_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] != TI1_E3_EXEC_REVISION:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    missing_by_table: dict[str, list[str]] = {}
    nullable_scope_by_table: dict[str, list[str]] = {}
    for table, required in E3_REQUIRED_COLUMNS.items():
        rows = conn.execute(
            f"""
            SELECT column_name, is_nullable
              FROM information_schema.columns
             WHERE table_schema='public' AND table_name='{table}'
             ORDER BY ordinal_position
            """
        ).fetchall()
        columns = {
            str(row["column_name"]): str(row["is_nullable"]) for row in rows
        }
        missing = sorted(required - set(columns))
        if missing:
            missing_by_table[table] = missing
        nullable_scope = sorted(
            name for name in ("org_id", "project_id") if columns.get(name) == "YES"
        )
        if nullable_scope:
            nullable_scope_by_table[table] = nullable_scope

    trigger_rows = conn.execute(
        """
        SELECT c.relname AS table_name, t.tgname AS trigger_name
          FROM pg_trigger t
          JOIN pg_class c ON c.oid=t.tgrelid
          JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='public' AND NOT t.tgisinternal
           AND c.relname IN (
             'tenant_backfill_batch', 'tenant_backfill_batch_event',
             'tenant_ownership_decision', 'tenant_ownership_decision_event',
             'tenant_quarantine_record'
           )
         ORDER BY c.relname, t.tgname
        """
    ).fetchall()
    triggers = {
        (str(row["table_name"]), str(row["trigger_name"])) for row in trigger_rows
    }
    expected_triggers = {
        (table, f"trg_{table}_{suffix}")
        for table in E3_REQUIRED_COLUMNS
        for suffix in ("immutable", "truncate_guard")
    }
    missing_triggers = sorted(
        f"{table}.{trigger}" for table, trigger in expected_triggers - triggers
    )
    if missing_by_table:
        issues.append("E3_LEDGER_COLUMNS_MISSING")
    if nullable_scope_by_table:
        issues.append("E3_LEDGER_SCOPE_NULLABLE")
    if missing_triggers:
        issues.append("E3_APPEND_ONLY_TRIGGERS_MISSING")
    return {
        **report,
        "stage": "TI-1-E3-1",
        "ok": not issues,
        "issues": issues,
        "e3MissingColumnsByTable": missing_by_table,
        "e3NullableScopeByTable": nullable_scope_by_table,
        "e3MissingAppendOnlyTriggers": missing_triggers,
    }
