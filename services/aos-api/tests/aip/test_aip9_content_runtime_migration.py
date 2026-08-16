from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from psycopg.rows import dict_row

from tests.aip._migration_test_support import isolated_aip_migration_database

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip9_001_content_runtime_authority.py"

TABLES = {
    "aip_media_job",
    "aip_media_job_event",
    "aip_media_job_receipt",
    "aip_avatar_session",
    "aip_avatar_session_event",
    "aip_avatar_session_receipt",
}

APPEND_ONLY = TABLES - {"aip_media_job", "aip_avatar_session"}


def _config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def test_00_content_runtime_is_linear_additive_and_zero_backfill() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip9_001"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip8_002"' in text
    assert "INSERT INTO" not in text
    assert "UPDATE aip_" not in text
    assert "DELETE FROM" not in text
    assert "AIP9_CONTENT_DOWNGRADE_REQUIRES_EMPTY_TABLES" in text
    for table in TABLES:
        assert f"CREATE TABLE {table}" in text
    assert "REFERENCES aip_task_run(org_id,project_id,run_id)" in text
    assert "REFERENCES aip_step_run(org_id,project_id,step_run_id)" in text
    command.upgrade(_config(), "head")


def test_content_runtime_forces_rls_and_least_privilege() -> None:
    with isolated_aip_migration_database("aip9_rls") as (_, database_url):
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
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
                   WHERE tablename=ANY(%s) AND policyname LIKE 'tenant_scope_%%_aip9'""",
                (list(TABLES),),
            ).fetchall()
            assert len(policies) == len(TABLES)
            assert all("aos_runtime" in row["roles"] for row in policies)
            assert all("aos.org_id" in row["qual"] for row in policies)
            assert all("aos.project_id" in row["with_check"] for row in policies)

            privileges = conn.execute(
                """SELECT table_name,privilege_type FROM information_schema.role_table_grants
                   WHERE grantee='aos_runtime' AND table_name=ANY(%s)""",
                (list(TABLES),),
            ).fetchall()
            by_table: dict[str, set[str]] = {}
            for row in privileges:
                by_table.setdefault(str(row["table_name"]), set()).add(
                    str(row["privilege_type"])
                )
            assert by_table["aip_media_job"] == {"SELECT", "INSERT", "UPDATE"}
            assert by_table["aip_avatar_session"] == {"SELECT", "INSERT", "UPDATE"}
            assert all(by_table[table] == {"SELECT", "INSERT"} for table in APPEND_ONLY)

            triggers = conn.execute(
                """SELECT c.relname,t.tgname FROM pg_trigger t
                   JOIN pg_class c ON c.oid=t.tgrelid
                   JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE n.nspname='public' AND NOT t.tgisinternal
                     AND c.relname=ANY(%s)""",
                (list(APPEND_ONLY),),
            ).fetchall()
            by_trigger_table: dict[str, set[str]] = {}
            for row in triggers:
                by_trigger_table.setdefault(str(row["relname"]), set()).add(
                    str(row["tgname"])
                )
            assert set(by_trigger_table) == APPEND_ONLY
            assert all(
                f"trg_{table}_append_only" in by_trigger_table[table]
                and f"trg_{table}_truncate_guard" in by_trigger_table[table]
                for table in APPEND_ONLY
            )


def test_content_events_and_receipts_are_append_only() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "guard_aip9_content_event_sequence" in text
    assert "AIP9_MEDIA_EVENT_AFTER_TERMINAL" in text
    assert "AIP9_AVATAR_EVENT_AFTER_TERMINAL" in text
    assert "trg_{table}_append_only" in text
    assert "trg_{table}_truncate_guard" in text


def test_z_content_runtime_empty_downgrade_upgrade_is_reversible() -> None:
    with isolated_aip_migration_database("aip9_reverse") as (config, database_url):
        command.downgrade(config, "aip8_002")
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM pg_class WHERE relname=ANY(%s)",
                (list(TABLES),),
            ).fetchone()["n"]
            assert count == 0
        command.upgrade(config, "head")
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            restored = conn.execute(
                "SELECT COUNT(*) AS n FROM pg_class WHERE relname=ANY(%s)",
                (list(TABLES),),
            ).fetchone()["n"]
            assert restored == len(TABLES)
