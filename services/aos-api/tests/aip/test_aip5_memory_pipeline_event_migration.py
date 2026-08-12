from pathlib import Path

from aos_api.db import connect


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip5_003_memory_pipeline_events.py"
TABLES = {
    "aip_memory_pipeline_schedule_event",
    "aip_memory_pipeline_run_event",
}


def test_e5b_schedule_event_migration_is_linear_scoped_and_append_only() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip5_003"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip5_002"' in text
    for table in TABLES:
        assert f"CREATE TABLE {table}" in text
    assert "org_id TEXT NOT NULL, project_id TEXT NOT NULL" in text
    assert "REFERENCES aip_memory_pipeline_schedule" in text
    assert "REFERENCES aip_memory_pipeline_run" in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "guard_aip5_memory_append_only" in text
    assert "GRANT DELETE" not in text
    assert "INSERT INTO aip_memory_pipeline_schedule" not in text


def test_e5b_schedule_event_authority_is_live_and_single_head() -> None:
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.relrowsecurity,c.relforcerowsecurity
               FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname=ANY(%s)""",
            (list(TABLES),),
        ).fetchall()
        assert len(rows) == len(TABLES)
        assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
        triggers = conn.execute(
            """SELECT c.relname,t.tgname FROM pg_trigger t
               JOIN pg_class c ON c.oid=t.tgrelid
               WHERE c.relname=ANY(%s) AND NOT t.tgisinternal""",
            (list(TABLES),),
        ).fetchall()
        names: dict[str, set[str]] = {}
        for item in triggers:
            names.setdefault(str(item["relname"]), set()).add(str(item["tgname"]))
        assert set(names) == TABLES
        assert all(any(name.endswith("append_only") for name in value) for value in names.values())
        assert all(any(name.endswith("truncate_guard") for name in value) for value in names.values())
        assert conn.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()["version_num"] == "aip5_003"
