from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from psycopg.rows import dict_row

from tests.aip._migration_test_support import isolated_aip_migration_database

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip9_002_content_event_guard_privileges.py"


def _config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def test_00_guard_fix_is_linear_fixed_path_and_least_privilege() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip9_002"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip9_001"' in text
    assert "SECURITY DEFINER SET search_path = pg_catalog, public" in text
    assert "FROM public.aip_media_job_event" in text
    assert "FROM public.aip_avatar_session_event" in text
    assert "REVOKE ALL ON FUNCTION guard_aip9_content_event_sequence() FROM PUBLIC" in text
    assert "GRANT EXECUTE ON FUNCTION guard_aip9_content_event_sequence() TO aos_runtime" in text
    assert "'mark_unknown','reconcile'" in text
    assert "previous_status IN ('succeeded','failed','cancelled')" in text
    assert "previous_status IN ('closed','failed','killed')" in text
    command.upgrade(_config(), "head")


def test_guard_fix_upgrade_and_downgrade_restore_security_mode() -> None:
    with isolated_aip_migration_database("aip9_guard") as (config, database_url):
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            row = conn.execute(
                """SELECT p.prosecdef,p.proconfig FROM pg_proc p
                   WHERE p.proname='guard_aip9_content_event_sequence'"""
            ).fetchone()
            assert row["prosecdef"] is True
            assert "search_path=pg_catalog, public" in row["proconfig"]
        command.downgrade(config, "aip9_001")
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            row = conn.execute(
                "SELECT prosecdef FROM pg_proc WHERE proname='guard_aip9_content_event_sequence'"
            ).fetchone()
            assert row["prosecdef"] is False
        command.upgrade(config, "head")
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            assert conn.execute(
                "SELECT prosecdef FROM pg_proc WHERE proname='guard_aip9_content_event_sequence'"
            ).fetchone()["prosecdef"] is True
