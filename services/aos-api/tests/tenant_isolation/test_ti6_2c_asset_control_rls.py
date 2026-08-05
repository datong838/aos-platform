from __future__ import annotations

import importlib.util
from pathlib import Path

from aos_api.db import connect

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti6c_asset_control_rls.py"


def test_ti6_2c_asset_rls_migration_is_frozen() -> None:
    spec = importlib.util.spec_from_file_location("ti6_2c_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "228ti6cassets"
    assert module.down_revision == "228ti6bcontract"
    assert len(module.TABLES) == 15


def test_ti6_2c_all_asset_tables_force_rls_with_scoped_policies() -> None:
    spec = importlib.util.spec_from_file_location("ti6_2c_schema", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with connect() as conn:
        protected = conn.execute(
            "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class "
            "WHERE relname=ANY(%s)",
            (list(module.TABLES),),
        ).fetchall()
        policies = conn.execute(
            "SELECT tablename,roles,qual,with_check FROM pg_policies "
            "WHERE tablename=ANY(%s) AND policyname LIKE 'tenant_scope_%%_ti6'",
            (list(module.TABLES),),
        ).fetchall()

    assert len(protected) == 15
    assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in protected)
    assert len(policies) == 15
    assert all("aos_runtime" in row["roles"] for row in policies)
    assert all("aos.org_id" in row["qual"] and "aos.project_id" in row["with_check"] for row in policies)


def test_ti6_2c_runtime_without_scope_sees_no_asset_rows() -> None:
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        counts = [
            int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in ("bundle_composition", "bundle_installation", "integration_case")
        ]

    assert counts == [0, 0, 0]
