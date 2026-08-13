from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg.errors import CheckViolation, ForeignKeyViolation

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip6_001_agent_skill_registry.py"
SCOPED = {
    "aip_agent_instance",
    "aip_skill_binding",
    "aip_capability_binding",
    "aip_agent_run",
    "aip_handoff_envelope",
    "aip_handoff_event",
}


def _config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def _insert_template(template_id: str = "template-a") -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO aip_agent_template_revision
               (template_id,revision,display_name,role_key,lifecycle,source_ref,
                source_license,manifest,content_hash,created_by)
               VALUES (%s,1,'内容官','content_officer','published',
                 '{"type":"SolutionPack","id":"ecommerce"}'::jsonb,
                 'internal','{}'::jsonb,%s,'pytest')
               ON CONFLICT DO NOTHING""",
            (template_id, "a" * 64),
        )
        conn.commit()


def _insert_instance(scope: TenantScope, instance_id: str, template_id: str = "template-a") -> None:
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_agent_instance
               (org_id,project_id,instance_id,template_id,template_revision,
                status,overlay,created_by)
               VALUES (%s,%s,%s,%s,1,'active','{}'::jsonb,'pytest')""",
            (*scope.key, instance_id, template_id),
        )
        conn.commit()


def test_a6b_migration_is_linear_additive_and_secret_ref_only() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip6_001"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip5_004"' in text
    assert "DELETE FROM " not in text
    assert "api_key" not in text
    assert "secret_ref ~ '^(vault|secret|keychain)://'" in text
    assert "REFERENCES aip_task(org_id,project_id,task_id)" in text
    assert "REFERENCES aip_task_run(org_id,project_id,run_id)" in text


def test_a6b_scoped_tables_force_rls_and_no_scope_is_empty() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = conn.execute(
            """SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
               FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relname=ANY(%s)""",
            (list(SCOPED),),
        ).fetchall()
        assert {str(row["relname"]) for row in rows} == SCOPED
        assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        for table in SCOPED:
            assert conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"] == 0


def test_a6b_append_only_facts_have_update_delete_and_truncate_guards() -> None:
    tables = {"aip_agent_template_revision", "aip_skill_template_revision", "aip_handoff_event"}
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.relname,t.tgname FROM pg_trigger t
               JOIN pg_class c ON c.oid=t.tgrelid
               JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND NOT t.tgisinternal
                 AND c.relname=ANY(%s)""",
            (list(tables),),
        ).fetchall()
    names: dict[str, set[str]] = {}
    for row in rows:
        names.setdefault(str(row["relname"]), set()).add(str(row["tgname"]))
    assert set(names) == tables
    assert all(any(name.endswith("append_only") for name in value) for value in names.values())
    assert all(any(name.endswith("truncate_guard") for name in value) for value in names.values())


def test_a6b_handoff_stores_only_token_hash_and_minimal_context() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "token_hash TEXT NOT NULL" in text
    assert "token TEXT" not in text
    assert "allowed_context_fields JSONB NOT NULL" in text
    assert "sender_instance_id <> receiver_instance_id" in text


def test_a6b_instances_are_isolated_and_secret_ref_is_enforced() -> None:
    primary = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    _insert_template()
    _insert_instance(primary, "agent-primary")
    _insert_instance(canary, "agent-canary")
    with connect(primary) as conn:
        rows = conn.execute(
            """SELECT instance_id FROM aip_agent_instance
               WHERE instance_id IN ('agent-primary','agent-canary')"""
        ).fetchall()
        assert [row["instance_id"] for row in rows] == ["agent-primary"]
        with pytest.raises(CheckViolation):
            conn.execute(
                """INSERT INTO aip_capability_binding
                   (org_id,project_id,binding_id,capability_ref,secret_ref,health,
                    network_policy_revision,quota_policy_revision,timeout_ms,
                    max_concurrency,status)
                   VALUES (%s,%s,'bad-secret','{}'::jsonb,'plain-secret','unknown',
                    'network-1','quota-1',1000,1,'active')""",
                primary.key,
            )
        conn.rollback()


def test_a6b_cross_tenant_handoff_foreign_keys_fail_closed() -> None:
    primary = TenantScope("org-org", "dev-project")
    with connect(primary) as conn:
        with pytest.raises(ForeignKeyViolation):
            conn.execute(
                """INSERT INTO aip_handoff_envelope
                   (org_id,project_id,handoff_id,task_id,task_run_id,
                    sender_instance_id,receiver_instance_id,object_refs,
                    artifact_refs,evidence_refs,context_payload,
                    allowed_context_fields,markings,token_hash,status,expires_at)
                   VALUES (%s,%s,'handoff-cross','missing-task','missing-run',
                    'agent-primary','agent-canary','[]'::jsonb,'[]'::jsonb,
                    '[]'::jsonb,'{}'::jsonb,'[]'::jsonb,'["internal"]'::jsonb,
                    %s,'issued',NOW()+INTERVAL '10 minutes')""",
                (*primary.key, "c" * 64),
            )
        conn.rollback()


def test_z_a6b_downgrade_upgrade_preserves_existing_authorities() -> None:
    preserved = ("aip_task", "aip_memory_item", "aip_eval_run")
    with connect() as conn:
        before = {
            table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in preserved
        }
    command.downgrade(_config(), "aip5_004")
    with connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM pg_class WHERE relname=ANY(%s)",
            (list(SCOPED | {"aip_agent_template_revision", "aip_skill_template_revision"}),),
        ).fetchone()["n"] == 0
        assert {
            table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in preserved
        } == before
    command.upgrade(_config(), "head")
    with connect() as conn:
        assert {
            table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in preserved
        } == before
