import json
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from psycopg import DatabaseError

from aos_api.db import connect

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip5_005_agent_memory_projection.py"

TABLES = {
    "aip_memory_agent_projection",
    "aip_memory_agent_projection_recipient",
    "aip_memory_agent_projection_event",
    "aip_memory_agent_projection_receipt",
    "aip_memory_exposure",
    "aip_memory_improvement_observation",
}

APPEND_ONLY = TABLES - {"aip_memory_agent_projection"}


def _config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def test_00_e7_migration_is_single_head_additive_and_zero_backfill() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip5_005"' in text
    assert 'down_revision: str | Sequence[str] | None = "w2_004"' in text
    assert "INSERT INTO" not in text
    assert "UPDATE aip_" not in text
    assert "DELETE FROM" not in text
    assert "AIP5_E7_DOWNGRADE_REQUIRES_EMPTY_TABLES" in text
    assert "AIP5_E7_PROJECTION_STATUS_TRANSITION_INVALID" in text
    assert "NEW.content_hash" not in text.split("guard_aip5_e7_projection_identity", 1)[1].split("END $$", 1)[0]
    assert "payload" not in text.lower()
    for table in TABLES:
        assert f"CREATE TABLE {table}" in text
    command.upgrade(_config(), "head")


def test_e7_tables_force_rls_and_audit_tables_are_append_only() -> None:
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
               WHERE tablename=ANY(%s) AND policyname LIKE 'tenant_scope_%%_aip5e7'""",
            (list(TABLES),),
        ).fetchall()
        assert len(policies) == len(TABLES)
        assert all("aos_runtime" in row["roles"] for row in policies)
        assert all("aos.org_id" in row["qual"] for row in policies)
        assert all("aos.project_id" in row["with_check"] for row in policies)

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


def _set_runtime_scope(conn, org_id: str | None, project_id: str | None) -> None:
    conn.execute("RESET ROLE")
    conn.execute("SELECT set_config('aos.org_id',%s,true)", (org_id or "",))
    conn.execute("SELECT set_config('aos.project_id',%s,true)", (project_id or "",))
    conn.execute("SET LOCAL ROLE aos_runtime")


def test_e7_observation_is_tenant_isolated_fail_closed_and_append_only() -> None:
    suffix = uuid4().hex[:10]
    org_a, org_b = f"pytest-e7-a-{suffix}", f"pytest-e7-b-{suffix}"
    project_id = f"pytest-e7-project-{suffix}"
    template_id = f"pytest-e7-template-{suffix}"
    instance_id = f"pytest-e7-agent-{suffix}"
    hash_value = "a" * 64
    metric_ref = json.dumps(
        {"assetType": "MetricDefinition", "assetId": "task-success", "revision": 1, "contentHash": hash_value}
    )
    eval_ref = json.dumps(
        {"assetType": "EvalContract", "assetId": "eval-e7", "revision": 1, "contentHash": hash_value}
    )
    with connect() as conn:
        for org_id in (org_a, org_b):
            conn.execute(
                "INSERT INTO twa_org(id,name) VALUES (%s,%s)",
                (org_id, org_id),
            )
            conn.execute(
                "INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,%s)",
                (org_id, project_id, project_id),
            )
        conn.execute(
            """INSERT INTO aip_agent_template_revision
               (template_id,revision,display_name,role_key,lifecycle,source_ref,
                source_license,manifest,content_hash,created_by)
               VALUES (%s,1,'E7 Test','e7.test','published',
                 '{"resourceType":"Test","resourceId":"e7","revision":"1","authority":"pytest"}'::jsonb,
                 'internal','{}'::jsonb,%s,'pytest')""",
            (template_id, hash_value),
        )
        for org_id in (org_a, org_b):
            conn.execute(
                """INSERT INTO aip_agent_instance
                   (org_id,project_id,instance_id,template_id,template_revision,
                    status,overlay,version,created_by)
                   VALUES (%s,%s,%s,%s,1,'active','{}'::jsonb,1,'pytest')""",
                (org_id, project_id, instance_id, template_id),
            )
            conn.execute(
                """INSERT INTO aip_memory_improvement_observation
                   (org_id,project_id,observation_id,instance_id,instance_version,
                    instance_hash,metric_definition_ref,eval_contract_ref,
                    exposure_refs,metrics,quality,source_refs,cutoff_at,observed_at,
                    conclusion,limitations,observation_hash)
                   VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,%s::jsonb,
                     '[]'::jsonb,'[]'::jsonb,'unknown','[]'::jsonb,
                     NOW(),NOW(),'insufficient_evidence','["no comparable cohort"]'::jsonb,%s)""",
                (org_id, project_id, f"observation-{org_id}", instance_id, hash_value, metric_ref, eval_ref, hash_value),
            )

        _set_runtime_scope(conn, org_a, project_id)
        visible = conn.execute(
            "SELECT observation_id FROM aip_memory_improvement_observation ORDER BY observation_id"
        ).fetchall()
        assert [row["observation_id"] for row in visible] == [f"observation-{org_a}"]

        conn.execute("SAVEPOINT e7_append_only")
        with pytest.raises(DatabaseError) as error:
            conn.execute(
                "UPDATE aip_memory_improvement_observation SET conclusion='improved'"
            )
        assert error.value.sqlstate == "55000"
        conn.execute("ROLLBACK TO SAVEPOINT e7_append_only")
        conn.execute("RELEASE SAVEPOINT e7_append_only")

        _set_runtime_scope(conn, org_b, project_id)
        visible = conn.execute(
            "SELECT observation_id FROM aip_memory_improvement_observation ORDER BY observation_id"
        ).fetchall()
        assert [row["observation_id"] for row in visible] == [f"observation-{org_b}"]

        _set_runtime_scope(conn, None, None)
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM aip_memory_improvement_observation"
        ).fetchone()["n"] == 0
        conn.rollback()


def test_z_e7_empty_downgrade_upgrade_is_reversible_and_single_head() -> None:
    command.downgrade(_config(), "w2_004")
    with connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM pg_class WHERE relname=ANY(%s)",
            (list(TABLES),),
        ).fetchone()["n"]
        assert count == 0
    command.upgrade(_config(), "head")
    with connect() as conn:
        restored = conn.execute(
            "SELECT COUNT(*) AS n FROM pg_class WHERE relname=ANY(%s)",
            (list(TABLES),),
        ).fetchone()["n"]
        assert restored == len(TABLES)
