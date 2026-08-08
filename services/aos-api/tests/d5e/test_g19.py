"""
G19 baseline — read-only RLS configuration check for D5-E0.

Checks that all tenant tables have ENABLE + FORCE ROW LEVEL SECURITY.
No canary writes, no temporary scope creation.
"""

import pytest
from sqlalchemy import text

from .conftest import TENANT_SCOPE, collect_evidence_metadata, save_evidence


# Tables that should have RLS
RLS_TABLES = [
    "ecom_object",
    "ecom_link",
    "obj_instance",
    "graph_edge",
    "checkpoint",
    "receipt",
]


class TestG19Baseline:
    """D5-E0: G19 read-only RLS configuration check."""

    def test_g19_rls_config(self, db_conn, evidence_meta):
        """Check RLS + FORCE on all known tenant tables."""
        results = {"tables": {}, "status": "PASS"}

        for table_name in RLS_TABLES:
            try:
                r = db_conn.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity "
                        "FROM pg_class c "
                        "JOIN pg_namespace n ON n.oid = c.relnamespace "
                        "WHERE n.nspname = 'public' AND relname = :tname"
                    ),
                    {"tname": table_name},
                )
                row = r.fetchone()
                if row is None:
                    results["tables"][table_name] = {
                        "exists": False,
                        "rls": False,
                        "force": False,
                        "status": "MISSING",
                    }
                    results["status"] = "RED"
                else:
                    rls_ok = row[0]
                    force_ok = row[1]
                    t_status = "PASS" if (rls_ok and force_ok) else "RED"
                    if t_status == "RED":
                        results["status"] = "RED"
                    results["tables"][table_name] = {
                        "exists": True,
                        "rls": rls_ok,
                        "force": force_ok,
                        "status": t_status,
                    }
            except Exception as e:
                results["tables"][table_name] = {
                    "exists": "ERROR",
                    "error": str(type(e).__name__),
                    "status": "RED",
                }
                results["status"] = "RED"

        save_evidence("G19", "D5-E0", results, evidence_meta)

    def test_g19_guc_variables(self, db_conn, evidence_meta):
        """Check GUC variable names match expected (aos.org_id / aos.project_id)."""
        results = {"guc_check": {}, "status": "PASS"}

        # Check by testing a SET LOCAL in a transaction
        try:
            with db_conn.begin():  # Will auto-rollback if test assertion fails
                db_conn.execute(text("SET LOCAL aos.org_id = 'test-org'"))
                db_conn.execute(text("SET LOCAL aos.project_id = 'test-project'"))

                r = db_conn.execute(text("SELECT current_setting('aos.org_id')"))
                org_val = r.scalar()
                r2 = db_conn.execute(text("SELECT current_setting('aos.project_id')"))
                proj_val = r2.scalar()

                results["guc_check"]["aos.org_id"] = org_val == "test-org"
                results["guc_check"]["aos.project_id"] = proj_val == "test-project"
                results["guc_check"]["correct_names"] = True

            # Transaction auto-committed; use a new one to rollback
        except Exception as e:
            results["guc_check"]["error"] = str(type(e).__name__)
            results["status"] = "RED"

        save_evidence("G19", "D5-E0", results, evidence_meta)

    def test_g19_tenant_scope_summary(self, db_conn, evidence_meta):
        """Summary of current tenant scope state."""
        results = {"tenant_scope": TENANT_SCOPE.copy()}

        # Count records in key tables for this tenant
        for table, scope_cols in [
            ("ecom_object", ("org_id", "workspace_id")),
            ("ecom_link", ("org_id", "workspace_id")),
            ("obj_instance", ("org_id", "project_id")),
            ("graph_edge", ("org_id", "project_id")),
        ]:
            try:
                sql = f"SELECT count(*) FROM {table} WHERE {scope_cols[0]} = :org AND {scope_cols[1]} = :ws"
                r = db_conn.execute(
                    text(sql),
                    {"org": TENANT_SCOPE["org_id"], "ws": TENANT_SCOPE["workspace_id"]},
                )
                results[f"{table}_count"] = r.scalar()
            except Exception as e:
                results[f"{table}_count"] = f"ERROR: {type(e).__name__}"

        # Check if there are any other org_ids in the system
        try:
            r = db_conn.execute(text(
                "SELECT DISTINCT org_id FROM ecom_object WHERE org_id != 'org-org'"
            ))
            other_orgs = [row[0] for row in r]
            results["other_orgs_in_ecom_object"] = other_orgs
        except Exception:
            results["other_orgs_in_ecom_object"] = "ERROR"

        save_evidence("G19", "D5-E0", results, evidence_meta)
