"""Read-only TI-1 E1 schema lint."""

from __future__ import annotations

from typing import Any

TI1_E1_REVISION = "228ti1e1expand"
TI1_E2_REVISION = "228ti1e2dual"
TI1_E3_REVISION = "228ti1e3ledger"
TI1_E3_EXEC_REVISION = "228ti1e3exec"
TI2_E1_REVISION = "228ti2e1expand"
TI2_E4_REVISION = "228ti2e4validate"
TI2_E6_REVISION = "228ti2e6rls"
TI2_E7_REVISION = "228ti2e7contract"
TI3_E1_REVISION = "228ti3e1expand"
TI3_E4_REVISION = "228ti3e4validate"
TI3_E6_REVISION = "228ti3e6rls"
TI3_E7_REVISION = "228ti3e7contract"
TI4_C1_REVISION = "228ti4c1expand"
TI4_D1_REVISION = "228ti4d1expand"
TI4_D4_REVISION = "228ti4d4validate"
TI4_D6_REVISION = "228ti4d6rls"
TI4_D7_REVISION = "228ti4d7contract"
TI4_C3_REVISION = "228ti4c3contract"
TI4_A1_REVISION = "228ti4a1apollo"
TI5_A1_REVISION = "228ti5a1aip"
TI5_A2_REVISION = "228ti5a2kv"
TI5_A3_REVISION = "228ti5a3lineage"
# The B1 contract remains required; schema reports accept the current TI-6 head.
TI5_B1_REVISION = "228ti6edirectory"
# Later domain migrations preserve the sealed TI-4/TI-5 tenant contracts.  Keep
# this exact instead of accepting arbitrary unknown descendants.
CURRENT_SCHEMA_HEAD_REVISION = "biw8_001"
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
    revision_row = conn.execute("SELECT version_num FROM alembic_version").fetchone()

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
    if rls_table_count and revision not in {
        TI2_E6_REVISION,
        TI2_E7_REVISION,
        TI3_E1_REVISION,
        TI3_E4_REVISION,
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("RLS_ENABLED_BEFORE_E6")
    if revision not in {
        TI1_E1_REVISION,
        TI1_E2_REVISION,
        TI1_E3_REVISION,
        TI1_E3_EXEC_REVISION,
        TI2_E1_REVISION,
        TI2_E4_REVISION,
        TI2_E6_REVISION,
        TI2_E7_REVISION,
        TI3_E1_REVISION,
        TI3_E4_REVISION,
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
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
        "org_id",
        "project_id",
        "batch_id",
        "environment_hash",
        "source_snapshot_hash",
        "code_commit",
        "mode",
        "status",
        "created_at",
        "approved_at",
        "completed_at",
    },
    "tenant_backfill_batch_event": {
        "org_id",
        "project_id",
        "event_id",
        "batch_id",
        "status",
        "evidence_hash",
        "actor_role",
        "actor_hash",
        "created_at",
    },
    "tenant_ownership_decision": {
        "org_id",
        "project_id",
        "decision_id",
        "batch_id",
        "resource",
        "key_hash",
        "decision",
        "evidence_grade",
        "evidence_hash",
        "candidate_count",
        "target_org_id",
        "target_project_id",
        "before_hash",
        "after_hash",
        "reason_code",
        "created_at",
    },
    "tenant_ownership_decision_event": {
        "org_id",
        "project_id",
        "event_id",
        "batch_id",
        "resource",
        "key_hash",
        "event_type",
        "before_hash",
        "after_hash",
        "evidence_hash",
        "actor_role",
        "actor_hash",
        "created_at",
    },
    "tenant_quarantine_record": {
        "org_id",
        "project_id",
        "quarantine_id",
        "batch_id",
        "resource",
        "key_hash",
        "reason_code",
        "candidate_scope_hashes",
        "source_snapshot_hash",
        "review_status",
        "created_at",
    },
}


def build_ti1_e3_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti1_e2_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI1_E3_EXEC_REVISION,
        TI2_E1_REVISION,
        TI2_E4_REVISION,
        TI2_E6_REVISION,
        TI2_E7_REVISION,
        TI3_E1_REVISION,
        TI3_E4_REVISION,
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
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
        columns = {str(row["column_name"]): str(row["is_nullable"]) for row in rows}
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


TI2_MODULE_COLUMNS = {
    "meta_module": {
        "module_pk",
        "module_id",
        "template_id",
        "template_version",
        "installation_id",
        "active_overlay_revision",
        "effective_config_hash",
        "deleted_at",
    },
    "module_canvas_config": {"module_pk"},
    "module_deployment": {"module_pk"},
    "module_events": {"module_pk"},
    "module_interface": {"module_pk"},
    "module_query": {"module_pk"},
    "module_variable": {"module_pk"},
    "module_widget_instance": {"module_pk"},
}

TI2_HISTORY_TABLES = {
    "module_organization_profile",
    "module_instance_overlay",
    "module_user_view_preference",
}

TI2_NOT_VALID_FOREIGN_KEYS = {
    "fk_meta_module_installation_ti2",
    "fk_meta_module_active_overlay_ti2",
    "fk_module_canvas_config_module_ti2",
    "fk_module_deployment_module_ti2",
    "fk_module_events_module_ti2",
    "fk_module_interface_module_ti2",
    "fk_module_query_module_ti2",
    "fk_module_variable_module_ti2",
    "fk_module_widget_instance_module_ti2",
    "fk_module_instance_overlay_module_ti2",
    "fk_module_user_view_preference_module_ti2",
}


def build_ti2_e1_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti1_e3_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI2_E1_REVISION,
        TI2_E4_REVISION,
        TI2_E6_REVISION,
        TI2_E7_REVISION,
        TI3_E1_REVISION,
        TI3_E4_REVISION,
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    missing_columns: dict[str, list[str]] = {}
    non_nullable_columns: dict[str, list[str]] = {}
    for table, expected in TI2_MODULE_COLUMNS.items():
        rows = conn.execute(
            """
            SELECT column_name, is_nullable
              FROM information_schema.columns
             WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        ).fetchall()
        columns = {str(row["column_name"]): str(row["is_nullable"]) for row in rows}
        missing = sorted(expected - set(columns))
        if missing:
            missing_columns[table] = missing
        non_nullable = sorted(name for name in expected if columns.get(name) == "NO")
        if non_nullable:
            non_nullable_columns[table] = non_nullable

    table_rows = conn.execute(
        """
        SELECT table_name
          FROM information_schema.tables
         WHERE table_schema='public' AND table_name = ANY(%s)
        """,
        (sorted(TI2_HISTORY_TABLES),),
    ).fetchall()
    present_tables = {str(row["table_name"]) for row in table_rows}
    missing_tables = sorted(TI2_HISTORY_TABLES - present_tables)

    fk_rows = conn.execute(
        """
        SELECT conname, convalidated
          FROM pg_constraint
         WHERE contype='f' AND conname LIKE '%_ti2'
        """
    ).fetchall()
    foreign_keys = {str(row["conname"]): bool(row["convalidated"]) for row in fk_rows}
    missing_foreign_keys = sorted(TI2_NOT_VALID_FOREIGN_KEYS - set(foreign_keys))
    prematurely_validated = (
        sorted(
            name
            for name in TI2_NOT_VALID_FOREIGN_KEYS
            if foreign_keys.get(name) is True
        )
        if report["alembicRevision"] == TI2_E1_REVISION
        else []
    )

    trigger_rows = conn.execute(
        """
        SELECT c.relname AS table_name, t.tgname AS trigger_name
          FROM pg_trigger t
          JOIN pg_class c ON c.oid=t.tgrelid
          JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='public' AND NOT t.tgisinternal
           AND c.relname = ANY(%s)
        """,
        (sorted(TI2_HISTORY_TABLES),),
    ).fetchall()
    triggers = {
        (str(row["table_name"]), str(row["trigger_name"])) for row in trigger_rows
    }
    expected_triggers = {
        (table, f"trg_{table}_{suffix}")
        for table in TI2_HISTORY_TABLES
        for suffix in ("immutable", "truncate_guard")
    }
    missing_triggers = sorted(
        f"{table}.{trigger}" for table, trigger in expected_triggers - triggers
    )

    if missing_columns:
        issues.append("TI2_MODULE_COLUMNS_MISSING")
    # E1 is an expand-only gate. E7 intentionally freezes the canonical
    # identities as NOT NULL, so the earlier warning is no longer an issue.
    if non_nullable_columns and report["alembicRevision"] not in {
        TI2_E7_REVISION,
        TI3_E1_REVISION,
        TI3_E4_REVISION,
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("TI2_EXPAND_COLUMNS_NOT_NULLABLE")
    if missing_tables:
        issues.append("TI2_HISTORY_TABLES_MISSING")
    if missing_foreign_keys:
        issues.append("TI2_FOREIGN_KEYS_MISSING")
    if prematurely_validated:
        issues.append("TI2_FOREIGN_KEYS_PREMATURELY_VALIDATED")
    if missing_triggers:
        issues.append("TI2_APPEND_ONLY_TRIGGERS_MISSING")
    return {
        **report,
        "stage": "TI-2-E1",
        "ok": not issues,
        "issues": issues,
        "ti2MissingColumns": missing_columns,
        "ti2NonNullableExpandColumns": (
            {}
            if report["alembicRevision"]
            in {
                TI2_E7_REVISION,
                TI3_E1_REVISION,
                TI3_E4_REVISION,
                TI3_E6_REVISION,
                TI3_E7_REVISION,
                TI4_C1_REVISION,
                TI4_D1_REVISION,
                TI4_D4_REVISION,
                TI4_D6_REVISION,
                TI4_D7_REVISION,
                TI4_C3_REVISION,
                TI4_A1_REVISION,
                TI5_A1_REVISION,
                TI5_A2_REVISION,
                TI5_A3_REVISION,
                TI5_B1_REVISION,
                CURRENT_SCHEMA_HEAD_REVISION,
            }
            else non_nullable_columns
        ),
        "ti2MissingHistoryTables": missing_tables,
        "ti2MissingForeignKeys": missing_foreign_keys,
        "ti2PrematurelyValidatedForeignKeys": prematurely_validated,
        "ti2MissingAppendOnlyTriggers": missing_triggers,
    }


def build_ti2_e4_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti2_e1_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI2_E4_REVISION,
        TI2_E6_REVISION,
        TI2_E7_REVISION,
        TI3_E1_REVISION,
        TI3_E4_REVISION,
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")
    rows = conn.execute(
        "SELECT conname, convalidated FROM pg_constraint WHERE conname = ANY(%s)",
        (sorted(TI2_NOT_VALID_FOREIGN_KEYS),),
    ).fetchall()
    validated = {str(row["conname"]): bool(row["convalidated"]) for row in rows}
    not_validated = sorted(
        name for name in TI2_NOT_VALID_FOREIGN_KEYS if not validated.get(name, False)
    )
    if not_validated:
        issues.append("TI2_FOREIGN_KEYS_NOT_VALIDATED")
    return {
        **report,
        "stage": "TI-2-E4",
        "ok": not issues,
        "issues": issues,
        "ti2NotValidatedForeignKeys": not_validated,
        "ti2ValidatedForeignKeyCount": sum(validated.values()),
    }


TI2_E6_SCOPED_TABLES = {
    "meta_module",
    "module_canvas_config",
    "module_deployment",
    "module_events",
    "module_interface",
    "module_query",
    "module_variable",
    "module_widget_instance",
    "module_instance_overlay",
    "module_user_view_preference",
}
TI2_E6_ORG_TABLES = {"module_organization_profile"}
TI2_E6_TABLES = TI2_E6_SCOPED_TABLES | TI2_E6_ORG_TABLES


def build_ti2_e6_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti2_e4_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI2_E6_REVISION,
        TI2_E7_REVISION,
        TI3_E1_REVISION,
        TI3_E4_REVISION,
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    role = conn.execute(
        "SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_roles "
        "WHERE rolname='aos_runtime'"
    ).fetchone()
    role_safe = bool(role) and not any(
        bool(role[name]) for name in ("rolcanlogin", "rolsuper", "rolbypassrls")
    )
    if not role_safe:
        issues.append("TI2_RUNTIME_ROLE_UNSAFE_OR_MISSING")

    rows = conn.execute(
        "SELECT c.relname AS table_name, c.relrowsecurity, c.relforcerowsecurity, "
        "pg_get_userbyid(c.relowner) AS table_owner "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname = ANY(%s)",
        (sorted(TI2_E6_TABLES),),
    ).fetchall()
    tables = {str(row["table_name"]): row for row in rows}
    missing_tables = sorted(TI2_E6_TABLES - set(tables))
    unprotected = sorted(
        table
        for table, row in tables.items()
        if not bool(row["relrowsecurity"]) or not bool(row["relforcerowsecurity"])
    )
    runtime_owned = sorted(
        table for table, row in tables.items() if row["table_owner"] == "aos_runtime"
    )
    if missing_tables:
        issues.append("TI2_RLS_TABLES_MISSING")
    if unprotected:
        issues.append("TI2_RLS_NOT_ENABLED_AND_FORCED")
    if runtime_owned:
        issues.append("TI2_RUNTIME_ROLE_OWNS_TABLE")

    policy_rows = conn.execute(
        "SELECT tablename, policyname, roles, qual, with_check FROM pg_policies "
        "WHERE schemaname='public' AND tablename = ANY(%s)",
        (sorted(TI2_E6_TABLES),),
    ).fetchall()
    policies = {str(row["tablename"]): row for row in policy_rows}
    invalid_policies: list[str] = []
    for table in sorted(TI2_E6_TABLES):
        row = policies.get(table)
        expressions = (
            f"{(row or {}).get('qual', '')} {(row or {}).get('with_check', '')}"
        )
        roles = list((row or {}).get("roles") or [])
        valid = (
            row is not None
            and row["policyname"] == f"tenant_scope_{table}_ti2"
            and "aos_runtime" in roles
            and expressions.count("aos.org_id") == 2
        )
        if table in TI2_E6_SCOPED_TABLES:
            valid = valid and expressions.count("aos.project_id") == 2
        else:
            valid = valid and "aos.project_id" not in expressions
        if not valid:
            invalid_policies.append(table)
    if invalid_policies:
        issues.append("TI2_RLS_POLICY_INVALID")

    return {
        **report,
        "stage": "TI-2-E6",
        "ok": not issues,
        "issues": issues,
        "ti2RuntimeRoleSafe": role_safe,
        "ti2RlsTableCount": len(tables),
        "ti2RlsMissingTables": missing_tables,
        "ti2RlsUnprotectedTables": unprotected,
        "ti2RuntimeOwnedTables": runtime_owned,
        "ti2RlsInvalidPolicies": invalid_policies,
    }


TI2_E7_PRIMARY_KEYS = {
    "meta_module": "PRIMARY KEY (org_id, project_id, module_pk)",
    "module_canvas_config": "PRIMARY KEY (org_id, project_id, module_pk)",
    "module_interface": "PRIMARY KEY (org_id, project_id, module_pk)",
    "module_deployment": "PRIMARY KEY (org_id, project_id, id)",
    "module_events": "PRIMARY KEY (org_id, project_id, id)",
    "module_query": "PRIMARY KEY (org_id, project_id, id)",
    "module_variable": "PRIMARY KEY (org_id, project_id, id)",
    "module_widget_instance": "PRIMARY KEY (org_id, project_id, id)",
}


def build_ti2_e7_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti2_e6_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI2_E7_REVISION,
        TI3_E1_REVISION,
        TI3_E4_REVISION,
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    pk_rows = conn.execute(
        "SELECT conrelid::regclass::text AS table_name, "
        "pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE contype='p' AND conrelid::regclass::text = ANY(%s)",
        (sorted(TI2_E7_PRIMARY_KEYS),),
    ).fetchall()
    primary_keys = {str(row["table_name"]): str(row["definition"]) for row in pk_rows}
    invalid_primary_keys = sorted(
        table
        for table, expected in TI2_E7_PRIMARY_KEYS.items()
        if primary_keys.get(table) != expected
    )
    if invalid_primary_keys:
        issues.append("TI2_CONTRACT_PRIMARY_KEY_INVALID")

    nullable_rows = conn.execute(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema='public' AND column_name='module_pk' "
        "AND table_name = ANY(%s) AND is_nullable='YES'",
        (sorted(TI2_E7_PRIMARY_KEYS),),
    ).fetchall()
    nullable_module_pk = sorted(str(row["table_name"]) for row in nullable_rows)
    module_id_row = conn.execute(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='meta_module' "
        "AND column_name='module_id'"
    ).fetchone()
    if nullable_module_pk or not module_id_row or module_id_row["is_nullable"] != "NO":
        issues.append("TI2_CONTRACT_IDENTITY_NULLABLE")

    quarantine = conn.execute(
        "SELECT to_regclass('public.module_event_orphan_quarantine')::text AS name"
    ).fetchone()
    quarantine_exists = bool(quarantine and quarantine["name"])
    quarantine_count = 0
    runtime_quarantine_access = False
    if quarantine_exists:
        quarantine_count = int(
            conn.execute(
                "SELECT COUNT(*) AS count FROM module_event_orphan_quarantine"
            ).fetchone()["count"]
        )
        runtime_quarantine_access = bool(
            conn.execute(
                "SELECT has_table_privilege('aos_runtime', "
                "'module_event_orphan_quarantine', "
                "'SELECT,INSERT,UPDATE,DELETE') AS allowed"
            ).fetchone()["allowed"]
        )
    active_null_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM module_events WHERE module_pk IS NULL"
        ).fetchone()["count"]
    )
    if not quarantine_exists or active_null_count:
        issues.append("TI2_ORPHAN_QUARANTINE_INVALID")
    if runtime_quarantine_access:
        issues.append("TI2_RUNTIME_CAN_ACCESS_ORPHAN_QUARANTINE")

    return {
        **report,
        "stage": "TI-2-E7",
        "ok": not issues,
        "issues": issues,
        "ti2ContractInvalidPrimaryKeys": invalid_primary_keys,
        "ti2ContractNullableModulePkTables": nullable_module_pk,
        "ti2OrphanQuarantineExists": quarantine_exists,
        "ti2OrphanQuarantineCount": quarantine_count,
        "ti2ActiveNullModulePkEventCount": active_null_count,
        "ti2RuntimeQuarantineAccess": runtime_quarantine_access,
    }


TI3_E1_EXPAND_TABLES = {
    "funnel_status",
    "graph_edge",
    "meta_branch",
    "obj_branch_overlay",
    "obj_instance",
}
TI3_E1_SCOPED_TABLES = TI3_E1_EXPAND_TABLES | {
    "object_lifecycle",
    "draft_dataset",
    "wiki_page",
    "wiki_page_version",
}
TI3_E1_TEMPLATE_TABLES = {"meta_action_type", "meta_link_type", "meta_object_type"}


def build_ti3_e1_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti2_e7_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI3_E1_REVISION,
        TI3_E4_REVISION,
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    rows = conn.execute(
        "SELECT table_name, column_name, is_nullable "
        "FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name = ANY(%s) AND column_name IN ('org_id','project_id')",
        (sorted(TI3_E1_SCOPED_TABLES | TI3_E1_TEMPLATE_TABLES),),
    ).fetchall()
    columns: dict[str, dict[str, str]] = {}
    for row in rows:
        columns.setdefault(str(row["table_name"]), {})[str(row["column_name"])] = str(
            row["is_nullable"]
        )
    missing_columns = sorted(
        table
        for table in TI3_E1_SCOPED_TABLES
        if set(columns.get(table, {})) != {"org_id", "project_id"}
    )
    expand_not_nullable = sorted(
        table
        for table in TI3_E1_EXPAND_TABLES
        if any(value != "YES" for value in columns.get(table, {}).values())
    )
    templates_with_scope = sorted(
        table for table in TI3_E1_TEMPLATE_TABLES if columns.get(table)
    )
    if missing_columns:
        issues.append("TI3_TENANT_COLUMNS_MISSING")
    if expand_not_nullable and report["alembicRevision"] not in {
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("TI3_EXPAND_COLUMNS_NOT_NULLABLE")
    if templates_with_scope:
        issues.append("TI3_TEMPLATE_SCOPE_DRIFT")

    fk_rows = conn.execute(
        "SELECT conname, convalidated FROM pg_constraint WHERE conname = ANY(%s)",
        ([f"fk_{table}_workspace_ti3" for table in sorted(TI3_E1_SCOPED_TABLES)],),
    ).fetchall()
    foreign_keys = {str(row["conname"]): bool(row["convalidated"]) for row in fk_rows}
    expected_fks = {f"fk_{table}_workspace_ti3" for table in TI3_E1_SCOPED_TABLES}
    missing_fks = sorted(expected_fks - set(foreign_keys))
    prematurely_validated = (
        sorted(name for name, validated in foreign_keys.items() if validated)
        if report["alembicRevision"] == TI3_E1_REVISION
        else []
    )
    if missing_fks:
        issues.append("TI3_FOREIGN_KEYS_MISSING")
    if prematurely_validated:
        issues.append("TI3_FOREIGN_KEYS_PREMATURELY_VALIDATED")

    return {
        **report,
        "stage": "TI-3-E1",
        "ok": not issues,
        "issues": issues,
        "ti3MissingTenantColumns": missing_columns,
        "ti3ExpandColumnsNotNullable": (
            []
            if report["alembicRevision"]
            in {
                TI3_E7_REVISION,
                TI4_C1_REVISION,
                TI4_D1_REVISION,
                TI4_D4_REVISION,
                TI4_D6_REVISION,
                TI4_D7_REVISION,
                TI4_C3_REVISION,
                TI4_A1_REVISION,
                TI5_A1_REVISION,
                TI5_A2_REVISION,
                TI5_A3_REVISION,
                TI5_B1_REVISION,
                CURRENT_SCHEMA_HEAD_REVISION,
            }
            else expand_not_nullable
        ),
        "ti3TemplatesWithTenantScope": templates_with_scope,
        "ti3MissingForeignKeys": missing_fks,
        "ti3PrematurelyValidatedForeignKeys": prematurely_validated,
    }


def build_ti3_e6_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti3_e1_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI3_E6_REVISION,
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    role = conn.execute(
        "SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_roles "
        "WHERE rolname='aos_runtime'"
    ).fetchone()
    role_safe = bool(role) and not any(
        bool(role[name]) for name in ("rolcanlogin", "rolsuper", "rolbypassrls")
    )
    if not role_safe:
        issues.append("TI3_RUNTIME_ROLE_UNSAFE_OR_MISSING")

    rows = conn.execute(
        "SELECT c.relname AS table_name, c.relrowsecurity, c.relforcerowsecurity, "
        "pg_get_userbyid(c.relowner) AS table_owner "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname = ANY(%s)",
        (sorted(TI3_E1_SCOPED_TABLES),),
    ).fetchall()
    tables = {str(row["table_name"]): row for row in rows}
    missing_tables = sorted(TI3_E1_SCOPED_TABLES - set(tables))
    unprotected = sorted(
        table
        for table, row in tables.items()
        if not bool(row["relrowsecurity"]) or not bool(row["relforcerowsecurity"])
    )
    runtime_owned = sorted(
        table for table, row in tables.items() if row["table_owner"] == "aos_runtime"
    )
    if missing_tables:
        issues.append("TI3_RLS_TABLES_MISSING")
    if unprotected:
        issues.append("TI3_RLS_NOT_ENABLED_AND_FORCED")
    if runtime_owned:
        issues.append("TI3_RUNTIME_ROLE_OWNS_TABLE")

    policy_rows = conn.execute(
        "SELECT tablename, policyname, roles, qual, with_check FROM pg_policies "
        "WHERE schemaname='public' AND tablename = ANY(%s) "
        "AND policyname LIKE 'tenant_scope_%%_ti3'",
        (sorted(TI3_E1_SCOPED_TABLES),),
    ).fetchall()
    policies = {str(row["tablename"]): row for row in policy_rows}
    invalid_policies: list[str] = []
    for table in sorted(TI3_E1_SCOPED_TABLES):
        row = policies.get(table)
        expressions = (
            f"{(row or {}).get('qual', '')} {(row or {}).get('with_check', '')}"
        )
        roles = list((row or {}).get("roles") or [])
        valid = (
            row is not None
            and row["policyname"] == f"tenant_scope_{table}_ti3"
            and "aos_runtime" in roles
            and expressions.count("aos.org_id") == 2
            and expressions.count("aos.project_id") == 2
        )
        if not valid:
            invalid_policies.append(table)
    if invalid_policies:
        issues.append("TI3_RLS_POLICY_INVALID")

    return {
        **report,
        "stage": "TI-3-E6",
        "ok": not issues,
        "issues": issues,
        "ti3RuntimeRoleSafe": role_safe,
        "ti3RlsTableCount": len(tables),
        "ti3RlsMissingTables": missing_tables,
        "ti3RlsUnprotectedTables": unprotected,
        "ti3RuntimeOwnedTables": runtime_owned,
        "ti3RlsInvalidPolicies": invalid_policies,
    }


TI3_E7_PRIMARY_KEYS = {
    "funnel_status": "PRIMARY KEY (org_id, project_id, object_type)",
    "graph_edge": (
        "PRIMARY KEY (org_id, project_id, src_type, src_id, rel, dst_type, dst_id)"
    ),
    "meta_branch": "PRIMARY KEY (org_id, project_id, id)",
    "obj_branch_overlay": (
        "PRIMARY KEY (org_id, project_id, branch_id, object_type, object_id)"
    ),
    "obj_instance": "PRIMARY KEY (org_id, project_id, object_type, object_id)",
    "object_lifecycle": "PRIMARY KEY (org_id, project_id, object_type, object_id)",
    "draft_dataset": "PRIMARY KEY (org_id, project_id, id)",
    "wiki_page": "PRIMARY KEY (org_id, project_id, object_type, object_id)",
    "wiki_page_version": "PRIMARY KEY (org_id, project_id, id)",
}


def build_ti3_e7_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti3_e6_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI3_E7_REVISION,
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    pk_rows = conn.execute(
        "SELECT conrelid::regclass::text AS table_name, "
        "pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE contype='p' AND conrelid::regclass::text = ANY(%s)",
        (sorted(TI3_E7_PRIMARY_KEYS),),
    ).fetchall()
    primary_keys = {str(row["table_name"]): str(row["definition"]) for row in pk_rows}
    invalid_primary_keys = sorted(
        table
        for table, expected in TI3_E7_PRIMARY_KEYS.items()
        if primary_keys.get(table) != expected
    )
    if invalid_primary_keys:
        issues.append("TI3_CONTRACT_PRIMARY_KEY_INVALID")

    nullable_rows = conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name = ANY(%s) "
        "AND column_name IN ('org_id','project_id') AND is_nullable='YES'",
        (sorted(TI3_E7_PRIMARY_KEYS),),
    ).fetchall()
    nullable_scope = sorted(
        f"{row['table_name']}.{row['column_name']}" for row in nullable_rows
    )
    if nullable_scope:
        issues.append("TI3_CONTRACT_SCOPE_NULLABLE")

    branch_fk = conn.execute(
        "SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE conrelid='obj_branch_overlay'::regclass "
        "AND conname='fk_obj_branch_overlay_branch_ti3' "
        "/* schema lint for org_id/project_id contract */"
    ).fetchone()
    expected_branch_fk = (
        "FOREIGN KEY (org_id, project_id, branch_id) "
        "REFERENCES meta_branch(org_id, project_id, id) ON DELETE CASCADE"
    )
    branch_fk_valid = bool(branch_fk) and branch_fk["definition"] == expected_branch_fk
    if not branch_fk_valid:
        issues.append("TI3_SCOPED_BRANCH_FOREIGN_KEY_INVALID")

    quarantine = conn.execute(
        "SELECT to_regclass('public.object_runtime_orphan_quarantine')::text AS name"
    ).fetchone()
    quarantine_exists = bool(quarantine and quarantine["name"])
    quarantine_count = 0
    runtime_quarantine_access = False
    quarantine_trigger_count = 0
    if quarantine_exists:
        quarantine_count = int(
            conn.execute(
                "SELECT COUNT(*) AS count FROM object_runtime_orphan_quarantine"
            ).fetchone()["count"]
        )
        runtime_quarantine_access = bool(
            conn.execute(
                "SELECT has_table_privilege('aos_runtime', "
                "'object_runtime_orphan_quarantine', "
                "'SELECT,INSERT,UPDATE,DELETE') AS allowed"
            ).fetchone()["allowed"]
        )
        quarantine_trigger_count = int(
            conn.execute(
                "SELECT COUNT(*) AS count FROM pg_trigger "
                "WHERE tgrelid='object_runtime_orphan_quarantine'::regclass "
                "AND NOT tgisinternal AND tgname IN ("
                "'trg_object_runtime_orphan_quarantine_immutable',"
                "'trg_object_runtime_orphan_quarantine_truncate_guard')"
            ).fetchone()["count"]
        )
    active_null_count = 0
    for table in TI3_E7_PRIMARY_KEYS:
        row = conn.execute(
            f"SELECT COUNT(*) AS count FROM {table} "
            "WHERE org_id IS NULL OR project_id IS NULL"
        ).fetchone()
        active_null_count += int(row["count"])
    if not quarantine_exists or active_null_count or quarantine_trigger_count != 2:
        issues.append("TI3_ORPHAN_QUARANTINE_INVALID")
    if runtime_quarantine_access:
        issues.append("TI3_RUNTIME_CAN_ACCESS_ORPHAN_QUARANTINE")

    return {
        **report,
        "stage": "TI-3-E7",
        "ok": not issues,
        "issues": issues,
        "ti3ContractInvalidPrimaryKeys": invalid_primary_keys,
        "ti3ContractNullableScopeColumns": nullable_scope,
        "ti3ScopedBranchForeignKeyValid": branch_fk_valid,
        "ti3OrphanQuarantineExists": quarantine_exists,
        "ti3OrphanQuarantineCount": quarantine_count,
        "ti3ActiveNullScopeCount": active_null_count,
        "ti3RuntimeQuarantineAccess": runtime_quarantine_access,
        "ti3QuarantineGuardTriggerCount": quarantine_trigger_count,
    }


TI4_C1_PRIMARY_KEYS = {
    "ecom_ingest_receipt": (
        "PRIMARY KEY (org_id, workspace_id, platform, shop_or_marketplace_id, "
        "stream, idempotency_key)"
    ),
    "ecom_link": (
        "PRIMARY KEY (org_id, workspace_id, link_type, source_platform, "
        "source_shop_or_marketplace_id, source_object_type, source_external_id, "
        "target_platform, target_shop_or_marketplace_id, target_object_type, "
        "target_external_id)"
    ),
    "ecom_object": (
        "PRIMARY KEY (org_id, workspace_id, platform, shop_or_marketplace_id, "
        "object_type, external_id)"
    ),
    "ecom_sync_checkpoint": (
        "PRIMARY KEY (org_id, workspace_id, platform, shop_or_marketplace_id, stream)"
    ),
    "oauth_token_store": (
        "PRIMARY KEY (org_id, workspace_id, platform, external_account_id)"
    ),
}


def build_ti4_c1_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti3_e7_schema_report(conn)
    revision = report["alembicRevision"]
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI4_C1_REVISION,
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    pk_rows = conn.execute(
        "SELECT conrelid::regclass::text AS table_name, "
        "pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE contype='p' AND conrelid::regclass::text = ANY(%s)",
        (sorted(TI4_C1_PRIMARY_KEYS),),
    ).fetchall()
    primary_keys = {str(row["table_name"]): str(row["definition"]) for row in pk_rows}
    invalid_primary_keys = sorted(
        table
        for table, expected in TI4_C1_PRIMARY_KEYS.items()
        if primary_keys.get(table) != expected
    )
    if invalid_primary_keys:
        issues.append("TI4_ECOM_PRIMARY_KEY_INVALID")

    nullable_rows = conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name = ANY(%s) "
        "AND column_name IN ('org_id','workspace_id') AND is_nullable='YES'",
        (sorted(TI4_C1_PRIMARY_KEYS),),
    ).fetchall()
    nullable_scope = sorted(
        f"{row['table_name']}.{row['column_name']}" for row in nullable_rows
    )
    if nullable_scope:
        issues.append("TI4_ECOM_SCOPE_NULLABLE")

    fk_rows = conn.execute(
        "SELECT conrelid::regclass::text AS table_name, conname, convalidated, "
        "pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE conname = ANY(%s)",
        ([f"fk_{table}_workspace_ti4" for table in sorted(TI4_C1_PRIMARY_KEYS)],),
    ).fetchall()
    foreign_keys = {str(row["table_name"]): row for row in fk_rows}
    expected_fk = (
        "FOREIGN KEY (org_id, workspace_id) "
        "REFERENCES twa_workspace(org_id, project_id)"
    )
    if revision not in {
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        expected_fk += " NOT VALID"
    invalid_foreign_keys = sorted(
        table
        for table in TI4_C1_PRIMARY_KEYS
        if table not in foreign_keys or foreign_keys[table]["definition"] != expected_fk
    )
    prematurely_validated = (
        sorted(
            table for table, row in foreign_keys.items() if bool(row["convalidated"])
        )
        if revision
        not in {
            TI4_C3_REVISION,
            TI4_A1_REVISION,
            TI5_A1_REVISION,
            TI5_A2_REVISION,
            TI5_A3_REVISION,
            TI5_B1_REVISION,
            CURRENT_SCHEMA_HEAD_REVISION,
        }
        else []
    )
    if invalid_foreign_keys:
        issues.append("TI4_ECOM_WORKSPACE_FOREIGN_KEY_INVALID")
    if prematurely_validated:
        issues.append("TI4_ECOM_WORKSPACE_FOREIGN_KEY_PREMATURELY_VALIDATED")

    return {
        **report,
        "stage": "TI-4-C1",
        "ok": not issues,
        "issues": issues,
        "ti4EcomInvalidPrimaryKeys": invalid_primary_keys,
        "ti4EcomNullableScopeColumns": nullable_scope,
        "ti4EcomInvalidWorkspaceForeignKeys": invalid_foreign_keys,
        "ti4EcomPrematurelyValidatedForeignKeys": prematurely_validated,
        "ti4EcomWorkspaceForeignKeyCount": len(foreign_keys),
    }


TI4_D1_EXPAND_TABLES = (
    "meta_dataset",
    "meta_dataset_history",
    "meta_pipeline",
    "meta_sync",
    "phase5_pipeline_graph",
)
TI4_D1_TENANT_TABLES = (*TI4_D1_EXPAND_TABLES, "meta_schedule", "meta_source")


def build_ti4_d1_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti4_c1_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    revision = report["alembicRevision"]
    if revision not in {
        TI4_D1_REVISION,
        TI4_D4_REVISION,
        TI4_D6_REVISION,
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    column_rows = conn.execute(
        "SELECT table_name,column_name,is_nullable FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name = ANY(%s) "
        "AND column_name IN ('org_id','project_id')",
        (list(TI4_D1_TENANT_TABLES),),
    ).fetchall()
    columns = {
        (str(row["table_name"]), str(row["column_name"])): str(row["is_nullable"])
        for row in column_rows
    }
    missing_columns = sorted(
        f"{table}.{column}"
        for table in TI4_D1_TENANT_TABLES
        for column in ("org_id", "project_id")
        if (table, column) not in columns
    )
    non_nullable_expand_columns = sorted(
        f"{table}.{column}"
        for table in TI4_D1_EXPAND_TABLES
        for column in ("org_id", "project_id")
        if columns.get((table, column)) != "YES"
    )
    if missing_columns:
        issues.append("TI4_DATA_OS_SCOPE_COLUMNS_MISSING")
    if non_nullable_expand_columns and revision not in {
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("TI4_DATA_OS_EXPAND_COLUMNS_NOT_NULLABLE")

    expected_names = [f"fk_{table}_workspace_ti4d1" for table in TI4_D1_TENANT_TABLES]
    fk_rows = conn.execute(
        "SELECT conrelid::regclass::text AS table_name,conname,convalidated,"
        "pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE conname = ANY(%s)",
        (expected_names,),
    ).fetchall()
    foreign_keys = {str(row["table_name"]): row for row in fk_rows}
    expected_fk = (
        "FOREIGN KEY (org_id, project_id) REFERENCES twa_workspace(org_id, project_id)"
    )
    if revision == TI4_D1_REVISION:
        expected_fk += " NOT VALID"
    invalid_foreign_keys = sorted(
        table
        for table in TI4_D1_TENANT_TABLES
        if table not in foreign_keys
        or str(foreign_keys[table]["definition"]) != expected_fk
    )
    prematurely_validated = (
        sorted(
            table for table, row in foreign_keys.items() if bool(row["convalidated"])
        )
        if revision == TI4_D1_REVISION
        else []
    )
    if invalid_foreign_keys:
        issues.append("TI4_DATA_OS_WORKSPACE_FOREIGN_KEY_INVALID")
    if prematurely_validated:
        issues.append("TI4_DATA_OS_WORKSPACE_FOREIGN_KEY_PREMATURELY_VALIDATED")

    row_counts = {
        table: int(
            conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
        )
        for table in TI4_D1_TENANT_TABLES
    }
    return {
        **report,
        "stage": "TI-4-D1",
        "ok": not issues,
        "issues": issues,
        "ti4DataOsMissingScopeColumns": missing_columns,
        "ti4DataOsNonNullableExpandColumns": (
            []
            if revision
            in {
                TI4_D7_REVISION,
                TI4_C3_REVISION,
                TI4_A1_REVISION,
                TI5_A1_REVISION,
                TI5_A2_REVISION,
                TI5_A3_REVISION,
                TI5_B1_REVISION,
                CURRENT_SCHEMA_HEAD_REVISION,
            }
            else non_nullable_expand_columns
        ),
        "ti4DataOsInvalidWorkspaceForeignKeys": invalid_foreign_keys,
        "ti4DataOsPrematurelyValidatedForeignKeys": prematurely_validated,
        "ti4DataOsWorkspaceForeignKeyCount": len(foreign_keys),
        "ti4DataOsRowCounts": row_counts,
        "ti4DataOsTotalRows": sum(row_counts.values()),
    }


TI4_D7_PRIMARY_KEYS = {
    "meta_source": ["org_id", "project_id", "id"],
    "meta_pipeline": ["org_id", "project_id", "id"],
    "meta_dataset": ["org_id", "project_id", "rid"],
    "meta_dataset_history": ["org_id", "project_id", "id"],
    "meta_sync": ["org_id", "project_id", "id"],
    "meta_schedule": ["org_id", "project_id", "id"],
    "phase5_pipeline_graph": ["org_id", "project_id", "pipeline_id"],
}
TI4_D7_PARENT_FOREIGN_KEYS = {
    "fk_meta_pipeline_source_ti4d7": (
        "meta_pipeline",
        (
            "FOREIGN KEY (org_id, project_id, source_id) "
            "REFERENCES meta_source(org_id, project_id, id)"
        ),
    ),
    "fk_meta_dataset_source_ti4d7": (
        "meta_dataset",
        (
            "FOREIGN KEY (org_id, project_id, source_id) "
            "REFERENCES meta_source(org_id, project_id, id)"
        ),
    ),
    "fk_meta_dataset_pipeline_ti4d7": (
        "meta_dataset",
        (
            "FOREIGN KEY (org_id, project_id, pipeline_id) "
            "REFERENCES meta_pipeline(org_id, project_id, id)"
        ),
    ),
    "fk_meta_dataset_history_dataset_ti4d7": (
        "meta_dataset_history",
        (
            "FOREIGN KEY (org_id, project_id, dataset_rid) "
            "REFERENCES meta_dataset(org_id, project_id, rid)"
        ),
    ),
    "fk_meta_sync_source_ti4d7": (
        "meta_sync",
        (
            "FOREIGN KEY (org_id, project_id, source_id) "
            "REFERENCES meta_source(org_id, project_id, id)"
        ),
    ),
    "fk_meta_schedule_pipeline_ti4d7": (
        "meta_schedule",
        (
            "FOREIGN KEY (org_id, project_id, pipeline_id) "
            "REFERENCES meta_pipeline(org_id, project_id, id)"
        ),
    ),
}


def build_ti4_d7_schema_report(conn: Any) -> dict[str, Any]:
    report = build_ti4_d1_schema_report(conn)
    issues = [
        issue
        for issue in report["issues"]
        if issue not in {"ALEMBIC_REVISION_MISMATCH"}
    ]
    if report["alembicRevision"] not in {
        TI4_D7_REVISION,
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    pk_rows = conn.execute(
        "SELECT c.relname AS table_name, "
        "array_agg(a.attname::text ORDER BY k.ordinality) AS columns "
        "FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid "
        "JOIN unnest(p.conkey) WITH ORDINALITY k(attnum, ordinality) ON TRUE "
        "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum "
        "WHERE p.contype='p' AND c.relnamespace='public'::regnamespace "
        "AND c.relname=ANY(%s) GROUP BY c.relname",
        (list(TI4_D7_PRIMARY_KEYS),),
    ).fetchall()
    primary_keys = {
        str(row["table_name"]): list(row["columns"] or []) for row in pk_rows
    }
    invalid_primary_keys = sorted(
        table
        for table, expected in TI4_D7_PRIMARY_KEYS.items()
        if primary_keys.get(table) != expected
    )
    if invalid_primary_keys:
        issues.append("TI4_DATA_OS_PRIMARY_KEY_INVALID")

    nullable_rows = conn.execute(
        "SELECT table_name,column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=ANY(%s) "
        "AND column_name IN ('org_id','project_id') AND is_nullable='YES'",
        (list(TI4_D7_PRIMARY_KEYS),),
    ).fetchall()
    nullable_scope = sorted(
        f"{row['table_name']}.{row['column_name']}" for row in nullable_rows
    )
    if nullable_scope:
        issues.append("TI4_DATA_OS_SCOPE_NULLABLE")

    fk_rows = conn.execute(
        "SELECT conname,conrelid::regclass::text AS table_name,convalidated,"
        "pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE conname=ANY(%s)",
        (list(TI4_D7_PARENT_FOREIGN_KEYS),),
    ).fetchall()
    foreign_keys = {str(row["conname"]): row for row in fk_rows}
    invalid_parent_foreign_keys = sorted(
        name
        for name, (table, definition) in TI4_D7_PARENT_FOREIGN_KEYS.items()
        if name not in foreign_keys
        or foreign_keys[name]["table_name"] != table
        or foreign_keys[name]["definition"] != definition
        or not bool(foreign_keys[name]["convalidated"])
    )
    if invalid_parent_foreign_keys:
        issues.append("TI4_DATA_OS_PARENT_FOREIGN_KEY_INVALID")

    quarantine = conn.execute(
        "SELECT to_regclass('public.data_os_orphan_quarantine') IS NOT NULL AS exists, "
        "COALESCE(has_table_privilege('aos_runtime', "
        "'public.data_os_orphan_quarantine', 'SELECT'), false) AS runtime_select"
    ).fetchone()
    guard_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM pg_trigger "
            "WHERE tgrelid=to_regclass('public.data_os_orphan_quarantine') "
            "AND NOT tgisinternal"
        ).fetchone()["count"]
    )
    if not bool(quarantine["exists"]):
        issues.append("TI4_DATA_OS_QUARANTINE_MISSING")
    if bool(quarantine["runtime_select"]):
        issues.append("TI4_DATA_OS_QUARANTINE_RUNTIME_VISIBLE")
    if guard_count != 2:
        issues.append("TI4_DATA_OS_QUARANTINE_GUARD_INVALID")

    active_null_count = sum(
        int(
            conn.execute(
                f"SELECT COUNT(*) AS count FROM {table} "
                "WHERE org_id IS NULL OR project_id IS NULL"
            ).fetchone()["count"]
        )
        for table in TI4_D7_PRIMARY_KEYS
    )
    if active_null_count:
        issues.append("TI4_DATA_OS_ACTIVE_NULL_SCOPE")

    return {
        **report,
        "stage": "TI-4-D7",
        "ok": not issues,
        "issues": issues,
        "ti4DataOsContractInvalidPrimaryKeys": invalid_primary_keys,
        "ti4DataOsContractNullableScope": nullable_scope,
        "ti4DataOsContractInvalidParentForeignKeys": invalid_parent_foreign_keys,
        "ti4DataOsQuarantineExists": bool(quarantine["exists"]),
        "ti4DataOsRuntimeQuarantineAccess": bool(quarantine["runtime_select"]),
        "ti4DataOsQuarantineGuardCount": guard_count,
        "ti4DataOsActiveNullScopeCount": active_null_count,
    }


TI4_C3_SCOPED_TABLES = frozenset(TI4_C1_PRIMARY_KEYS)


def build_ti4_c3_schema_report(conn: Any) -> dict[str, Any]:
    """Verify the contracted e-commerce Connector tenant boundary."""
    report = build_ti4_d7_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI4_C3_REVISION,
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    fk_rows = conn.execute(
        "SELECT conrelid::regclass::text AS table_name,convalidated "
        "FROM pg_constraint WHERE conname = ANY(%s)",
        ([f"fk_{table}_workspace_ti4" for table in sorted(TI4_C3_SCOPED_TABLES)],),
    ).fetchall()
    validated_tables = {
        str(row["table_name"]) for row in fk_rows if bool(row["convalidated"])
    }
    unvalidated_foreign_keys = sorted(TI4_C3_SCOPED_TABLES - validated_tables)
    if unvalidated_foreign_keys:
        issues.append("TI4_ECOM_WORKSPACE_FOREIGN_KEY_NOT_VALIDATED")

    role = conn.execute(
        "SELECT rolcanlogin,rolsuper,rolbypassrls FROM pg_roles "
        "WHERE rolname='aos_runtime'"
    ).fetchone()
    role_safe = bool(role) and not any(
        bool(role[name]) for name in ("rolcanlogin", "rolsuper", "rolbypassrls")
    )
    if not role_safe:
        issues.append("TI4_ECOM_RUNTIME_ROLE_UNSAFE_OR_MISSING")

    table_rows = conn.execute(
        "SELECT c.relname AS table_name,c.relrowsecurity,c.relforcerowsecurity,"
        "pg_get_userbyid(c.relowner) AS table_owner FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname = ANY(%s)",
        (sorted(TI4_C3_SCOPED_TABLES),),
    ).fetchall()
    tables = {str(row["table_name"]): row for row in table_rows}
    missing_tables = sorted(TI4_C3_SCOPED_TABLES - set(tables))
    unprotected_tables = sorted(
        table
        for table, row in tables.items()
        if not bool(row["relrowsecurity"]) or not bool(row["relforcerowsecurity"])
    )
    runtime_owned_tables = sorted(
        table for table, row in tables.items() if row["table_owner"] == "aos_runtime"
    )
    if missing_tables:
        issues.append("TI4_ECOM_RLS_TABLES_MISSING")
    if unprotected_tables:
        issues.append("TI4_ECOM_RLS_NOT_ENABLED_AND_FORCED")
    if runtime_owned_tables:
        issues.append("TI4_ECOM_RUNTIME_ROLE_OWNS_TABLE")

    policy_rows = conn.execute(
        "SELECT tablename,policyname,roles,qual,with_check FROM pg_policies "
        "WHERE schemaname='public' AND tablename = ANY(%s) "
        "AND policyname LIKE 'tenant_scope_%%_ti4c3'",
        (sorted(TI4_C3_SCOPED_TABLES),),
    ).fetchall()
    policies = {str(row["tablename"]): row for row in policy_rows}
    invalid_policies: list[str] = []
    for table in sorted(TI4_C3_SCOPED_TABLES):
        row = policies.get(table)
        expressions = (
            f"{(row or {}).get('qual', '')} {(row or {}).get('with_check', '')}"
        )
        roles = list((row or {}).get("roles") or [])
        if not (
            row is not None
            and row["policyname"] == f"tenant_scope_{table}_ti4c3"
            and "aos_runtime" in roles
            and expressions.count("aos.org_id") == 2
            and expressions.count("aos.project_id") == 2
        ):
            invalid_policies.append(table)
    if invalid_policies:
        issues.append("TI4_ECOM_RLS_POLICY_INVALID")

    return {
        **report,
        "stage": "TI-4-C3",
        "ok": not issues,
        "issues": issues,
        "ti4EcomUnvalidatedWorkspaceForeignKeys": unvalidated_foreign_keys,
        "ti4EcomRuntimeRoleSafe": role_safe,
        "ti4EcomRlsTableCount": len(tables),
        "ti4EcomRlsMissingTables": missing_tables,
        "ti4EcomRlsUnprotectedTables": unprotected_tables,
        "ti4EcomRuntimeOwnedTables": runtime_owned_tables,
        "ti4EcomRlsInvalidPolicies": invalid_policies,
    }


def build_ti4_a1_schema_report(conn: Any) -> dict[str, Any]:
    """Verify Apollo Spoke as a scoped instance beneath global Channels."""
    report = build_ti4_c3_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI4_A1_REVISION,
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    primary_key = conn.execute(
        "SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE conrelid='apollo_spoke'::regclass AND contype='p'"
    ).fetchone()
    primary_key_valid = bool(primary_key) and primary_key["definition"] == (
        "PRIMARY KEY (org_id, project_id, id)"
    )
    if not primary_key_valid:
        issues.append("TI4_APOLLO_SPOKE_PRIMARY_KEY_INVALID")

    fk = conn.execute(
        "SELECT convalidated,pg_get_constraintdef(oid) AS definition "
        "FROM pg_constraint WHERE conname='fk_apollo_spoke_workspace_ti4a1'"
    ).fetchone()
    foreign_key_valid = (
        bool(fk)
        and bool(fk["convalidated"])
        and fk["definition"]
        == (
            "FOREIGN KEY (org_id, project_id) "
            "REFERENCES twa_workspace(org_id, project_id)"
        )
    )
    if not foreign_key_valid:
        issues.append("TI4_APOLLO_SPOKE_WORKSPACE_FK_INVALID")

    table = conn.execute(
        "SELECT relrowsecurity,relforcerowsecurity,"
        "pg_get_userbyid(relowner) AS table_owner FROM pg_class "
        "WHERE oid='apollo_spoke'::regclass"
    ).fetchone()
    rls_valid = (
        bool(table)
        and bool(table["relrowsecurity"])
        and bool(table["relforcerowsecurity"])
    )
    if not rls_valid:
        issues.append("TI4_APOLLO_SPOKE_RLS_INVALID")
    if table and table["table_owner"] == "aos_runtime":
        issues.append("TI4_APOLLO_SPOKE_RUNTIME_OWNS_TABLE")

    policy = conn.execute(
        "SELECT roles,qual,with_check FROM pg_policies "
        "WHERE schemaname='public' AND tablename='apollo_spoke' "
        "AND policyname='tenant_scope_apollo_spoke_ti4a1'"
    ).fetchone()
    expressions = (
        f"{(policy or {}).get('qual', '')} {(policy or {}).get('with_check', '')}"
    )
    policy_valid = (
        policy is not None
        and "public" in list(policy["roles"] or [])
        and expressions.count("aos.org_id") == 2
        and expressions.count("aos.project_id") == 2
    )
    if not policy_valid:
        issues.append("TI4_APOLLO_SPOKE_POLICY_INVALID")

    orphan_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM apollo_spoke child "
            "LEFT JOIN twa_workspace parent ON parent.org_id=child.org_id "
            "AND parent.project_id=child.project_id WHERE parent.org_id IS NULL"
        ).fetchone()["count"]
    )
    if orphan_count:
        issues.append("TI4_APOLLO_SPOKE_WORKSPACE_ORPHAN")

    return {
        **report,
        "stage": "TI-4-A1",
        "ok": not issues,
        "issues": issues,
        "ti4ApolloSpokePrimaryKeyValid": primary_key_valid,
        "ti4ApolloSpokeWorkspaceForeignKeyValid": foreign_key_valid,
        "ti4ApolloSpokeRlsValid": rls_valid,
        "ti4ApolloSpokePolicyValid": policy_valid,
        "ti4ApolloSpokeWorkspaceOrphanCount": orphan_count,
    }


TI5_A1_TABLES = frozenset(
    {
        "aip_logic_graph",
        "aip_logic_graph_revision",
        "aip_logic_graph_runs",
        "aip_logic_graph_run_nodes",
        "aip_eval_suite",
        "aip_eval_report",
        "aip_logic_publication",
    }
)


def build_ti5_a1_schema_report(conn: Any) -> dict[str, Any]:
    """Verify the existing tenant-scoped AIP runtime contract."""
    report = build_ti4_a1_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI5_A1_REVISION,
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    fk_rows = conn.execute(
        "SELECT conrelid::regclass::text AS table_name,convalidated "
        "FROM pg_constraint WHERE conname = ANY(%s)",
        ([f"fk_{table}_workspace_ti5a1" for table in sorted(TI5_A1_TABLES)],),
    ).fetchall()
    valid_fk_tables = {
        str(row["table_name"]) for row in fk_rows if bool(row["convalidated"])
    }
    invalid_foreign_keys = sorted(TI5_A1_TABLES - valid_fk_tables)
    if invalid_foreign_keys:
        issues.append("TI5_AIP_WORKSPACE_FOREIGN_KEY_INVALID")

    table_rows = conn.execute(
        "SELECT c.relname AS table_name,c.relrowsecurity,c.relforcerowsecurity,"
        "pg_get_userbyid(c.relowner) AS table_owner FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname = ANY(%s)",
        (sorted(TI5_A1_TABLES),),
    ).fetchall()
    tables = {str(row["table_name"]): row for row in table_rows}
    unprotected_tables = sorted(
        table
        for table, row in tables.items()
        if not bool(row["relrowsecurity"]) or not bool(row["relforcerowsecurity"])
    )
    runtime_owned_tables = sorted(
        table for table, row in tables.items() if row["table_owner"] == "aos_runtime"
    )
    if set(tables) != TI5_A1_TABLES:
        issues.append("TI5_AIP_TABLES_MISSING")
    if unprotected_tables:
        issues.append("TI5_AIP_RLS_INVALID")
    if runtime_owned_tables:
        issues.append("TI5_AIP_RUNTIME_OWNS_TABLE")

    policy_rows = conn.execute(
        "SELECT tablename,roles,qual,with_check FROM pg_policies "
        "WHERE schemaname='public' AND tablename = ANY(%s) "
        "AND policyname LIKE 'tenant_scope_%%_ti5a1'",
        (sorted(TI5_A1_TABLES),),
    ).fetchall()
    policies = {str(row["tablename"]): row for row in policy_rows}
    invalid_policies: list[str] = []
    for table in sorted(TI5_A1_TABLES):
        row = policies.get(table)
        expressions = (
            f"{(row or {}).get('qual', '')} {(row or {}).get('with_check', '')}"
        )
        if not (
            row is not None
            and "public" in list(row["roles"] or [])
            and expressions.count("aos.org_id") == 2
            and expressions.count("aos.project_id") == 2
        ):
            invalid_policies.append(table)
    if invalid_policies:
        issues.append("TI5_AIP_RLS_POLICY_INVALID")

    orphan_count = 0
    for table in sorted(TI5_A1_TABLES):
        orphan_count += int(
            conn.execute(
                f"SELECT COUNT(*) AS count FROM {table} child "
                "LEFT JOIN twa_workspace parent ON parent.org_id=child.org_id "
                "AND parent.project_id=child.project_id WHERE parent.org_id IS NULL"
            ).fetchone()["count"]
        )
    if orphan_count:
        issues.append("TI5_AIP_WORKSPACE_ORPHAN")

    return {
        **report,
        "stage": "TI-5-A1",
        "ok": not issues,
        "issues": issues,
        "ti5AipWorkspaceForeignKeysInvalid": invalid_foreign_keys,
        "ti5AipRlsUnprotectedTables": unprotected_tables,
        "ti5AipRuntimeOwnedTables": runtime_owned_tables,
        "ti5AipInvalidPolicies": invalid_policies,
        "ti5AipWorkspaceOrphanCount": orphan_count,
    }


def build_ti5_a2_schema_report(conn: Any) -> dict[str, Any]:
    """Verify tenant-scoped AIP KV ownership and runtime boundary."""
    report = build_ti5_a1_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI5_A2_REVISION,
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    columns = {
        str(row["column_name"]): row
        for row in conn.execute(
            "SELECT column_name,is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='meta_aip_kv'"
        ).fetchall()
    }
    scope_valid = all(
        columns.get(name) and columns[name]["is_nullable"] == "NO"
        for name in ("org_id", "project_id")
    )
    if not scope_valid:
        issues.append("TI5_AIP_KV_SCOPE_INVALID")

    primary_key = conn.execute(
        "SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE conrelid='meta_aip_kv'::regclass AND contype='p'"
    ).fetchone()
    primary_key_valid = bool(primary_key) and primary_key["definition"] == (
        "PRIMARY KEY (org_id, project_id, key)"
    )
    if not primary_key_valid:
        issues.append("TI5_AIP_KV_PRIMARY_KEY_INVALID")

    fk = conn.execute(
        "SELECT convalidated FROM pg_constraint "
        "WHERE conname='fk_meta_aip_kv_workspace_ti5a2'"
    ).fetchone()
    foreign_key_valid = bool(fk) and bool(fk["convalidated"])
    if not foreign_key_valid:
        issues.append("TI5_AIP_KV_WORKSPACE_FK_INVALID")

    table = conn.execute(
        "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
        "WHERE oid='meta_aip_kv'::regclass"
    ).fetchone()
    rls_valid = (
        bool(table)
        and bool(table["relrowsecurity"])
        and bool(table["relforcerowsecurity"])
    )
    if not rls_valid:
        issues.append("TI5_AIP_KV_RLS_INVALID")

    policy = conn.execute(
        "SELECT roles,qual,with_check FROM pg_policies "
        "WHERE schemaname='public' AND tablename='meta_aip_kv' "
        "AND policyname='tenant_scope_meta_aip_kv_ti5a2'"
    ).fetchone()
    expressions = (
        f"{(policy or {}).get('qual', '')} {(policy or {}).get('with_check', '')}"
    )
    policy_valid = (
        policy is not None
        and "public" in list(policy["roles"] or [])
        and expressions.count("aos.org_id") == 2
        and expressions.count("aos.project_id") == 2
    )
    if not policy_valid:
        issues.append("TI5_AIP_KV_POLICY_INVALID")

    row_count = int(
        conn.execute("SELECT COUNT(*) AS count FROM meta_aip_kv").fetchone()["count"]
    )
    ledger_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM aip_kv_ownership_ledger"
        ).fetchone()["count"]
    )
    ledger_orphan_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM aip_kv_ownership_ledger ledger "
            "LEFT JOIN meta_aip_kv kv ON md5(kv.key)=ledger.key_hash "
            "AND kv.org_id=ledger.org_id AND kv.project_id=ledger.project_id "
            "WHERE ledger.decision='ASSIGN_TEST_ORG' AND kv.key IS NULL"
        ).fetchone()["count"]
    )
    null_scope_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM meta_aip_kv "
            "WHERE org_id IS NULL OR project_id IS NULL"
        ).fetchone()["count"]
    )
    if ledger_orphan_count:
        issues.append("TI5_AIP_KV_LEDGER_ORPHAN")
    if null_scope_count:
        issues.append("TI5_AIP_KV_NULL_SCOPE")

    return {
        **report,
        "stage": "TI-5-A2",
        "ok": not issues,
        "issues": issues,
        "ti5AipKvScopeValid": scope_valid,
        "ti5AipKvPrimaryKeyValid": primary_key_valid,
        "ti5AipKvWorkspaceForeignKeyValid": foreign_key_valid,
        "ti5AipKvRlsValid": rls_valid,
        "ti5AipKvPolicyValid": policy_valid,
        "ti5AipKvRowCount": row_count,
        "ti5AipKvLedgerCount": ledger_count,
        "ti5AipKvLedgerOrphanCount": ledger_orphan_count,
        "ti5AipKvNullScopeCount": null_scope_count,
    }


def build_ti5_a3_schema_report(conn: Any) -> dict[str, Any]:
    """Verify decision lineage ownership, scoped contract, and quarantine."""
    report = build_ti5_a2_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI5_A3_REVISION,
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    columns = {
        str(row["column_name"]): row
        for row in conn.execute(
            "SELECT column_name,is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='decision_lineage'"
        ).fetchall()
    }
    scope_valid = all(
        columns.get(name) and columns[name]["is_nullable"] == "NO"
        for name in ("org_id", "project_id")
    )
    if not scope_valid:
        issues.append("TI5_DECISION_LINEAGE_SCOPE_INVALID")

    primary_key = conn.execute(
        "SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint "
        "WHERE conrelid='decision_lineage'::regclass AND contype='p'"
    ).fetchone()
    primary_key_valid = bool(primary_key) and primary_key["definition"] == (
        "PRIMARY KEY (org_id, project_id, id)"
    )
    if not primary_key_valid:
        issues.append("TI5_DECISION_LINEAGE_PRIMARY_KEY_INVALID")

    foreign_keys = {
        str(row["conname"]): bool(row["convalidated"])
        for row in conn.execute(
            "SELECT conname,convalidated FROM pg_constraint WHERE conname = ANY(%s)",
            (
                [
                    "fk_decision_lineage_workspace_ti5a3",
                    "fk_decision_lineage_draft_ti5a3",
                ],
            ),
        ).fetchall()
    }
    foreign_keys_valid = all(
        foreign_keys.get(name) is True
        for name in (
            "fk_decision_lineage_workspace_ti5a3",
            "fk_decision_lineage_draft_ti5a3",
        )
    )
    if not foreign_keys_valid:
        issues.append("TI5_DECISION_LINEAGE_FK_INVALID")

    table = conn.execute(
        "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
        "WHERE oid='decision_lineage'::regclass"
    ).fetchone()
    rls_valid = (
        bool(table)
        and bool(table["relrowsecurity"])
        and bool(table["relforcerowsecurity"])
    )
    if not rls_valid:
        issues.append("TI5_DECISION_LINEAGE_RLS_INVALID")

    policy = conn.execute(
        "SELECT roles,qual,with_check FROM pg_policies "
        "WHERE schemaname='public' AND tablename='decision_lineage' "
        "AND policyname='tenant_scope_decision_lineage_ti5a3'"
    ).fetchone()
    expressions = (
        f"{(policy or {}).get('qual', '')} {(policy or {}).get('with_check', '')}"
    )
    policy_valid = (
        policy is not None
        and "public" in list(policy["roles"] or [])
        and expressions.count("aos.org_id") == 2
        and expressions.count("aos.project_id") == 2
    )
    if not policy_valid:
        issues.append("TI5_DECISION_LINEAGE_POLICY_INVALID")

    row_count = int(
        conn.execute("SELECT COUNT(*) AS count FROM decision_lineage").fetchone()[
            "count"
        ]
    )
    assigned_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM decision_lineage_ownership_ledger "
            "WHERE decision='ASSIGN_FROM_DRAFT'"
        ).fetchone()["count"]
    )
    quarantine_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM decision_lineage_orphan_quarantine"
        ).fetchone()["count"]
    )
    parent_orphan_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM decision_lineage lineage "
            "LEFT JOIN draft_dataset draft ON draft.org_id=lineage.org_id "
            "AND draft.project_id=lineage.project_id AND draft.id=lineage.draft_id "
            "WHERE draft.id IS NULL"
        ).fetchone()["count"]
    )
    ledger_orphan_count = int(
        conn.execute(
            "SELECT COUNT(*) AS count FROM decision_lineage_ownership_ledger ledger "
            "LEFT JOIN decision_lineage lineage "
            "ON md5(lineage.id)=ledger.lineage_id_hash "
            "AND lineage.org_id=ledger.org_id AND lineage.project_id=ledger.project_id "
            "WHERE ledger.decision='ASSIGN_FROM_DRAFT' AND lineage.id IS NULL"
        ).fetchone()["count"]
    )
    if parent_orphan_count:
        issues.append("TI5_DECISION_LINEAGE_PARENT_ORPHAN")
    if ledger_orphan_count:
        issues.append("TI5_DECISION_LINEAGE_LEDGER_ORPHAN")

    return {
        **report,
        "stage": "TI-5-A3",
        "ok": not issues,
        "issues": issues,
        "ti5DecisionLineageScopeValid": scope_valid,
        "ti5DecisionLineagePrimaryKeyValid": primary_key_valid,
        "ti5DecisionLineageForeignKeysValid": foreign_keys_valid,
        "ti5DecisionLineageRlsValid": rls_valid,
        "ti5DecisionLineagePolicyValid": policy_valid,
        "ti5DecisionLineageRowCount": row_count,
        "ti5DecisionLineageAssignedCount": assigned_count,
        "ti5DecisionLineageQuarantineCount": quarantine_count,
        "ti5DecisionLineageParentOrphanCount": parent_orphan_count,
        "ti5DecisionLineageLedgerOrphanCount": ledger_orphan_count,
    }


def build_ti5_b1_schema_report(conn: Any) -> dict[str, Any]:
    """Verify the seven model-management tenant contracts."""
    report = build_ti5_a3_schema_report(conn)
    issues = [
        issue for issue in report["issues"] if issue != "ALEMBIC_REVISION_MISMATCH"
    ]
    if report["alembicRevision"] not in {
        TI5_B1_REVISION,
        CURRENT_SCHEMA_HEAD_REVISION,
    }:
        issues.append("ALEMBIC_REVISION_MISMATCH")

    tables = (
        "capacity_limits",
        "capacity_usage",
        "model_catalog",
        "model_provider",
        "model_route",
        "provider_health",
        "registered_models",
    )
    table_rows = {
        str(row["relname"]): row
        for row in conn.execute(
            "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class "
            "WHERE relname = ANY(%s)",
            (list(tables),),
        ).fetchall()
    }
    primary_keys = {
        str(row["table_name"]): str(row["definition"])
        for row in conn.execute(
            "SELECT conrelid::regclass::text AS table_name,"
            "pg_get_constraintdef(oid) AS definition FROM pg_constraint "
            "WHERE contype='p' AND conrelid::regclass::text = ANY(%s)",
            (list(tables),),
        ).fetchall()
    }
    scope_columns = {
        (str(row["table_name"]), str(row["column_name"])): row["is_nullable"]
        for row in conn.execute(
            "SELECT table_name,column_name,is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name = ANY(%s) "
            "AND column_name IN ('org_id','project_id')",
            (list(tables),),
        ).fetchall()
    }
    policies = {
        str(row["tablename"]): row
        for row in conn.execute(
            "SELECT tablename,roles,qual,with_check FROM pg_policies "
            "WHERE schemaname='public' AND tablename = ANY(%s)",
            (list(tables),),
        ).fetchall()
    }
    foreign_keys = {
        str(row["conname"]): bool(row["convalidated"])
        for row in conn.execute(
            "SELECT conname,convalidated FROM pg_constraint "
            "WHERE conname LIKE 'fk_%_ti5b1'"
        ).fetchall()
    }

    table_contracts_valid = True
    for table in tables:
        table_row = table_rows.get(table) or {}
        policy = policies.get(table) or {}
        expressions = f"{policy.get('qual', '')} {policy.get('with_check', '')}"
        valid = (
            primary_keys.get(table) == "PRIMARY KEY (org_id, project_id, id)"
            and scope_columns.get((table, "org_id")) == "NO"
            and scope_columns.get((table, "project_id")) == "NO"
            and bool(table_row.get("relrowsecurity"))
            and bool(table_row.get("relforcerowsecurity"))
            and "public" in list(policy.get("roles") or [])
            and expressions.count("aos.org_id") == 2
            and expressions.count("aos.project_id") == 2
            and foreign_keys.get(f"fk_{table}_workspace_ti5b1") is True
        )
        table_contracts_valid = table_contracts_valid and valid
    if not table_contracts_valid:
        issues.append("TI5_MODEL_MANAGEMENT_TABLE_CONTRACT_INVALID")

    child_foreign_keys_valid = all(
        foreign_keys.get(name) is True
        for name in (
            "fk_provider_health_provider_ti5b1",
            "fk_registered_models_catalog_ti5b1",
        )
    )
    if not child_foreign_keys_valid:
        issues.append("TI5_MODEL_MANAGEMENT_CHILD_FK_INVALID")

    return {
        **report,
        "stage": "TI-5-B1",
        "ok": not issues,
        "issues": issues,
        "ti5ModelManagementTables": list(tables),
        "ti5ModelManagementTableContractsValid": table_contracts_valid,
        "ti5ModelManagementChildForeignKeysValid": child_foreign_keys_valid,
    }
