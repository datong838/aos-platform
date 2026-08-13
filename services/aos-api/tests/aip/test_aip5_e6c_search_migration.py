from pathlib import Path

from aos_api.db import connect


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip5_004_memory_search_projection.py"
TABLES = {"aip_memory_search_reference", "aip_memory_search_capability"}


def test_e6c_migration_is_linear_reference_only_and_extension_free() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip5_004"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip5_003"' in text
    assert "CREATE EXTENSION" not in text
    assert "payload_ref" not in text
    assert "embedding" not in text
    assert "to_tsvector('simple', search_text)" in text
    assert "REFERENCES aip_memory_item_revision" in text
    assert "ON DELETE CASCADE" in text


def test_e6c_tables_force_scope_and_have_no_content_columns() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute(
            """SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
               FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname=ANY(%s)""",
            (list(TABLES),),
        ).fetchall()
        assert {str(row["relname"]) for row in rows} == TABLES
        assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
        policies = conn.execute(
            """SELECT tablename,roles,qual,with_check FROM pg_policies
               WHERE tablename=ANY(%s) AND policyname LIKE 'tenant_scope_%%_aip5'""",
            (list(TABLES),),
        ).fetchall()
        assert len(policies) == 2
        assert all("aos_runtime" in row["roles"] for row in policies)
        columns = conn.execute(
            """SELECT table_name,column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name=ANY(%s)""",
            (list(TABLES),),
        ).fetchall()
        names = {str(row["column_name"]) for row in columns}
        assert {"payload_ref", "content", "body", "embedding"}.isdisjoint(names)


def test_e6c_no_scope_is_zero_visible() -> None:
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        for table in TABLES:
            assert conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"] == 0
