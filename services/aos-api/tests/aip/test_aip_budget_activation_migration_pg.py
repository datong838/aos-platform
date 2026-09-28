"""Disposable-PG schema gate for immutable budget activation authority."""

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
TABLES = (
    "aip_budget_activation_preview",
    "aip_budget_activation_decision",
    "aip_budget_activation_revocation",
    "aip_budget_activation_receipt",
)


def test_budget_activation_tables_are_tenant_scoped_and_append_only() -> None:
    with connect(SCOPE) as conn:
        for table in TABLES:
            row = conn.execute(
                """SELECT c.relrowsecurity,c.relforcerowsecurity,
                    has_table_privilege(current_user,c.oid,'SELECT') AS can_select,
                    has_table_privilege(current_user,c.oid,'INSERT') AS can_insert,
                    has_table_privilege(current_user,c.oid,'UPDATE') AS can_update,
                    has_table_privilege(current_user,c.oid,'DELETE') AS can_delete
                   FROM pg_class c WHERE c.oid=to_regclass(%s)""",
                (f"public.{table}",),
            ).fetchone()
            assert row is not None, table
            assert row == {
                "relrowsecurity": True, "relforcerowsecurity": True,
                "can_select": True, "can_insert": True,
                "can_update": False, "can_delete": False,
            }
            triggers = conn.execute(
                """SELECT count(*) AS n FROM pg_trigger
                   WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal""",
                (f"public.{table}",),
            ).fetchone()["n"]
            assert triggers >= 2, table
        constraints = conn.execute(
            """SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint
               WHERE conrelid=to_regclass('public.aip_budget_activation_preview')"""
        ).fetchall()
        assert any("external_usage_proven = false" in row["definition"]
                   for row in constraints)
