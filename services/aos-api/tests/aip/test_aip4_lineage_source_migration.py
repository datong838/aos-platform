from pathlib import Path

from aos_api.db import connect


def test_e3a_migration_is_linear_and_additive() -> None:
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/aip4_004_lineage_source_authority.py"
    )
    text = path.read_text(encoding="utf-8")
    assert 'revision: str = "aip4_004"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip4_003"' in text
    assert "DROP TABLE" not in text
    assert "source_kind" in text
    assert "source_id" in text
    assert "source_hash" in text


def test_e3a_lineage_source_authority_is_scoped_and_append_only() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        columns = conn.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema='public' AND table_name='aip_lineage_event'"""
        ).fetchall()
        assert {row["column_name"] for row in columns} >= {
            "source_kind",
            "source_id",
            "source_hash",
        }
        table = conn.execute(
            """SELECT relrowsecurity,relforcerowsecurity FROM pg_class c
               JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname='aip_lineage_event'"""
        ).fetchone()
        assert table is not None
        assert bool(table["relrowsecurity"])
        assert bool(table["relforcerowsecurity"])
        indexes = conn.execute(
            """SELECT indexname FROM pg_indexes
               WHERE schemaname='public' AND tablename='aip_lineage_event'"""
        ).fetchall()
        names = {row["indexname"] for row in indexes}
        assert "aip_lineage_event_source_uq" in names
        assert "aip_lineage_event_root_timeline_idx" in names
        triggers = conn.execute(
            """SELECT tgname FROM pg_trigger t
               JOIN pg_class c ON c.oid=t.tgrelid
               WHERE c.relname='aip_lineage_event' AND NOT t.tgisinternal"""
        ).fetchall()
        trigger_names = {row["tgname"] for row in triggers}
        assert "trg_aip_lineage_event_append_only" in trigger_names
        assert "trg_aip_lineage_event_truncate_guard" in trigger_names
