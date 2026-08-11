from pathlib import Path

from aos_api.db import connect


def test_e1b_migration_is_linear_and_additive() -> None:
    path = Path(__file__).parents[2] / "alembic/versions/aip4_003_eval_report_revision.py"
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "aip4_003"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip4_002"' in text
    assert "CREATE TABLE aip_eval_report_revision" in text
    assert "ALTER TABLE aip_eval_report " not in text
    assert "DROP TABLE aip_eval_report " not in text


def test_e1b_report_table_is_rls_and_append_only() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute(
            """SELECT c.relrowsecurity,c.relforcerowsecurity FROM pg_class c
               JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname='aip_eval_report_revision'"""
        ).fetchone()
        assert row is not None and row["relrowsecurity"] and row["relforcerowsecurity"]
        names = {r["tgname"] for r in conn.execute(
            """SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
               JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
               AND c.relname='aip_eval_report_revision' AND NOT t.tgisinternal"""
        ).fetchall()}
        assert "trg_aip_eval_report_revision_append_only" in names
        assert "trg_aip_eval_report_revision_truncate_guard" in names
