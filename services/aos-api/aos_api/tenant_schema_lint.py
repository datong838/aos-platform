"""Read-only TI-1 E1 schema lint."""
from __future__ import annotations

from typing import Any

TI1_E1_REVISION = "228ti1e1expand"
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
    if revision != TI1_E1_REVISION:
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
