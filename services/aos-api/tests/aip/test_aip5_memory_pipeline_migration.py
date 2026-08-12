from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg.errors import InsufficientPrivilege

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip5_002_memory_pipeline_control.py"

TABLES = {
    "aip_memory_pipeline_schedule",
    "aip_memory_pipeline_run",
    "aip_memory_pipeline_receipt",
    "aip_memory_pipeline_receipt_candidate",
    "aip_memory_pipeline_checkpoint_revision",
    "aip_memory_pipeline_alert",
}

APPEND_ONLY = {
    "aip_memory_pipeline_receipt",
    "aip_memory_pipeline_receipt_candidate",
    "aip_memory_pipeline_checkpoint_revision",
    "aip_memory_pipeline_alert",
}

PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")


def _config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def test_e5a_migration_is_linear_additive_and_does_not_seed_real_schedules() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip5_002"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip5_001"' in text
    assert "INSERT INTO aip_memory_pipeline_schedule" not in text
    assert "org-org" not in text
    assert "dev-org" not in text
    assert "meta_schedule_run" not in text
    for table in TABLES:
        assert f"CREATE TABLE {table}" in text


def test_e5a_authority_is_scoped_and_facts_are_append_only() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")' in text
    assert 'op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")' in text
    for table in APPEND_ONLY:
        assert table in text
    assert "GRANT DELETE" not in text
    assert "REFERENCES aip_task(org_id,project_id,task_id)" in text
    assert "REFERENCES aip_task_run(org_id,project_id,run_id)" in text
    assert "REFERENCES aip_memory_candidate(org_id,project_id,candidate_id)" in text


def test_e5a_schema_freezes_idempotency_cas_and_checkpoint_rules() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "UNIQUE (org_id,project_id,idempotency_key)" in text
    assert "expected_checkpoint_version" in text
    assert "checkpoint_before_version" in text
    assert "checkpoint_after_version" in text
    assert "CHECK (checkpoint_after_version >= checkpoint_before_version)" in text
    assert "CHECK (status IN ('queued','running','paused','succeeded','partial','failed','cancelled','unknown'))" in text
    assert "CHECK (pipeline_kind IN (" in text
    for kind in (
        "seed_import",
        "operational_learning",
        "network_learning",
        "competitor_analysis",
        "professional_database",
        "customer_feedback",
        "human_experience",
    ):
        assert f"'{kind}'" in text


def _insert_schedule(scope: TenantScope, schedule_id: str) -> None:
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_memory_pipeline_schedule (
               org_id,project_id,schedule_id,pipeline_kind,trigger,config_ref,
               status,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,'seed_import','manual',%s::jsonb,'paused',%s,%s,'pytest')""",
            (
                *scope.key,
                schedule_id,
                '{"artifactId":"config-1","artifactType":"knowledge_pipeline_config",'
                '"revision":"1","contentHash":"' + "a" * 64 + '"}',
                schedule_id,
                "b" * 64,
            ),
        )
        conn.commit()


def test_e5a_runtime_scope_is_fail_closed_and_workspace_isolated() -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES ('org-org','栖月汇商贸有限公司') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
               VALUES ('org-org','dev-project','默认工作区')
               ON CONFLICT (org_id,project_id) DO NOTHING"""
        )
        conn.commit()

    _insert_schedule(PRIMARY, "schedule-primary")
    _insert_schedule(CANARY, "schedule-canary")
    with connect(PRIMARY) as conn:
        rows = conn.execute(
            """SELECT schedule_id FROM aip_memory_pipeline_schedule
               WHERE schedule_id IN ('schedule-primary','schedule-canary')
               ORDER BY schedule_id"""
        ).fetchall()
        assert [row["schedule_id"] for row in rows] == ["schedule-primary"]
    with connect(CANARY) as conn:
        rows = conn.execute(
            """SELECT schedule_id FROM aip_memory_pipeline_schedule
               WHERE schedule_id IN ('schedule-primary','schedule-canary')
               ORDER BY schedule_id"""
        ).fetchall()
        assert [row["schedule_id"] for row in rows] == ["schedule-canary"]

    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM aip_memory_pipeline_schedule"
        ).fetchone()["n"] == 0
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                """INSERT INTO aip_memory_pipeline_schedule (
                   org_id,project_id,schedule_id,pipeline_kind,trigger,config_ref,
                   status,idempotency_key,request_hash,created_by)
                   VALUES ('dev-org','dev-project','blocked','seed_import','manual',
                   '{}'::jsonb,'paused','blocked',%s,'pytest')""",
                ("f" * 64,),
            )
        conn.rollback()


def test_e5a_tables_force_rls_and_append_only_facts() -> None:
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
        triggers = conn.execute(
            """SELECT c.relname,t.tgname FROM pg_trigger t
               JOIN pg_class c ON c.oid=t.tgrelid
               JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND NOT t.tgisinternal
                 AND c.relname=ANY(%s)""",
            (list(APPEND_ONLY),),
        ).fetchall()
        names: dict[str, set[str]] = {}
        for row in triggers:
            names.setdefault(str(row["relname"]), set()).add(str(row["tgname"]))
        assert set(names) == APPEND_ONLY
        assert all(any(name.endswith("append_only") for name in value) for value in names.values())
        assert all(any(name.endswith("truncate_guard") for name in value) for value in names.values())


def test_z_e5a_downgrade_upgrade_preserves_existing_authorities() -> None:
    preserved_tables = ("aip_task", "aip_memory_candidate", "aip_eval_run")
    with connect() as conn:
        before = {
            table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in preserved_tables
        }
    command.downgrade(_config(), "aip5_001")
    with connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM pg_class WHERE relname=ANY(%s)",
            (list(TABLES),),
        ).fetchone()["n"] == 0
        assert {
            table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in preserved_tables
        } == before
    command.upgrade(_config(), "head")
    with connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM pg_class WHERE relname=ANY(%s)",
            (list(TABLES),),
        ).fetchone()["n"] == len(TABLES)
        assert {
            table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in preserved_tables
        } == before
