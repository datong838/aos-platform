from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg
import pytest
from aos_api.db import connect


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "alembic" / "versions" / "a0v_001_meta_schedule_run_managed_schema.py"
)


def _revision_module():
    spec = importlib.util.spec_from_file_location("a0v_001_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a0v_001_is_single_additive_managed_table() -> None:
    module = _revision_module()
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "a0v_001"
    assert module.down_revision == "ar2_018"
    assert module.TABLE == "meta_schedule_run"
    assert "CREATE TABLE IF NOT EXISTS meta_schedule_run" in source
    assert "meta_schedule_run schema drift blocks managed adoption" in source
    assert "meta_schedule_run key contract blocks managed adoption" in source
    assert "meta_schedule_run unknown policy blocks managed adoption" in source
    assert "meta_schedule_run history index drift blocks managed adoption" in source
    assert "ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY" in source
    assert "ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY" in source
    assert "USING (" in source and "WITH CHECK (" in source
    assert "REVOKE ALL ON {TABLE} FROM PUBLIC,aos_runtime" in source
    assert "GRANT SELECT,INSERT,UPDATE ON {TABLE} TO aos_runtime" in source
    assert "DELETE FROM" not in source
    assert "UPDATE meta_schedule_run" not in source


def test_a0v_001_downgrade_is_data_loss_guarded(monkeypatch) -> None:
    module = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(module.op, "execute", statements.append)

    module.downgrade()

    assert "IF EXISTS (SELECT 1 FROM meta_schedule_run LIMIT 1)" in statements[0]
    assert "meta_schedule_run downgrade blocked: run history exists" in statements[0]
    assert statements[-1] == "DROP TABLE meta_schedule_run"


def test_a0v_001_upgrade_emits_security_after_shape_guards(monkeypatch) -> None:
    module = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(module.op, "execute", statements.append)

    module.upgrade()

    sql = "\n".join(statements)
    shape_guard = sql.index("schema drift blocks managed adoption")
    table_create = sql.index("CREATE TABLE IF NOT EXISTS meta_schedule_run")
    policy_create = sql.index("CREATE POLICY")
    grant = sql.index("GRANT SELECT,INSERT,UPDATE")
    assert shape_guard < table_create < policy_create < grant


def test_a0v_001_runtime_contract_and_tenant_isolation() -> None:
    first = ("a0v-org-a", "a0v-project", "a0v-run-a")
    second = ("a0v-org-b", "a0v-project", "a0v-run-b")
    with connect(inherit_scope=False) as conn:
        relation = conn.execute(
            """
            SELECT relrowsecurity,relforcerowsecurity
              FROM pg_class
             WHERE oid='public.meta_schedule_run'::regclass
            """
        ).fetchone()
        assert relation == {"relrowsecurity": True, "relforcerowsecurity": True}
        privileges = conn.execute(
            """
            SELECT has_table_privilege('aos_runtime','meta_schedule_run','SELECT') AS select_ok,
                   has_table_privilege('aos_runtime','meta_schedule_run','INSERT') AS insert_ok,
                   has_table_privilege('aos_runtime','meta_schedule_run','UPDATE') AS update_ok,
                   has_table_privilege('aos_runtime','meta_schedule_run','DELETE') AS delete_ok
            """
        ).fetchone()
        assert privileges == {
            "select_ok": True,
            "insert_ok": True,
            "update_ok": True,
            "delete_ok": False,
        }
        policy = conn.execute(
            """
            SELECT cmd,roles,qual,with_check
              FROM pg_policies
             WHERE schemaname='public' AND tablename='meta_schedule_run'
               AND policyname='tenant_scope_meta_schedule_run_a0v001'
            """
        ).fetchone()
        assert policy is not None
        assert policy["cmd"] == "ALL"
        assert policy["roles"] == ["aos_runtime"]
        assert "aos.org_id" in policy["qual"] and "aos.project_id" in policy["qual"]
        assert policy["qual"] == policy["with_check"]

        conn.execute("SET LOCAL ROLE aos_runtime")
        for org_id, project_id, run_id in (first, second):
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (project_id,))
            conn.execute(
                """
                INSERT INTO meta_schedule_run(
                  id,org_id,project_id,schedule_id,scheduled_for,trigger,status
                ) VALUES(%s,%s,%s,'a0v-schedule',clock_timestamp(),'manual','succeeded')
                """,
                (run_id, org_id, project_id),
            )

        conn.execute("SELECT set_config('aos.org_id',%s,true)", (first[0],))
        conn.execute("SELECT set_config('aos.project_id',%s,true)", (first[1],))
        visible = conn.execute(
            "SELECT id FROM meta_schedule_run WHERE id LIKE 'a0v-run-%' ORDER BY id"
        ).fetchall()
        assert visible == [{"id": first[2]}]
        assert (
            conn.execute(
                "UPDATE meta_schedule_run SET status='failed' WHERE id=%s", (second[2],)
            ).rowcount
            == 0
        )
        conn.execute("SAVEPOINT cross_tenant_insert")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                """
                INSERT INTO meta_schedule_run(
                  id,org_id,project_id,schedule_id,scheduled_for,trigger,status
                ) VALUES('a0v-run-cross',%s,%s,'a0v-schedule',clock_timestamp(),
                         'manual','succeeded')
                """,
                (second[0], second[1]),
            )
        conn.execute("ROLLBACK TO SAVEPOINT cross_tenant_insert")

        conn.execute("RESET ROLE")
        for org_id, project_id, run_id in (first, second):
            conn.execute("SELECT set_config('aos.org_id',%s,true)", (org_id,))
            conn.execute("SELECT set_config('aos.project_id',%s,true)", (project_id,))
            conn.execute("DELETE FROM meta_schedule_run WHERE id=%s", (run_id,))
        conn.commit()
