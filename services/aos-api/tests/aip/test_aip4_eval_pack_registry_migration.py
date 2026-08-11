from pathlib import Path

from aos_api.db import connect


def test_e1a_migration_is_linear_and_additive() -> None:
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/aip4_002_eval_pack_registry.py"
    )
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "aip4_002"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip4_001"' in text
    assert "CREATE TABLE aip_eval_suite_revision" in text
    for legacy in ("aip_eval_suite", "aip_eval_report", "aip_logic_publication"):
        assert f"ALTER TABLE {legacy} " not in text
        assert f"DROP TABLE {legacy} " not in text


def test_e1a_suite_registry_is_rls_and_append_only() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute(
            """SELECT c.relrowsecurity,c.relforcerowsecurity
               FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname='aip_eval_suite_revision'"""
        ).fetchone()
        assert row is not None
        assert bool(row["relrowsecurity"])
        assert bool(row["relforcerowsecurity"])
        triggers = conn.execute(
            """SELECT t.tgname FROM pg_trigger t
               JOIN pg_class c ON c.oid=t.tgrelid
               JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname='aip_eval_suite_revision'
                 AND NOT t.tgisinternal"""
        ).fetchall()
        names = {str(item["tgname"]) for item in triggers}
        assert "trg_aip_eval_suite_revision_append_only" in names
        assert "trg_aip_eval_suite_revision_truncate_guard" in names
