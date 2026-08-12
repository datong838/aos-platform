from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg.errors import InsufficientPrivilege

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "aip5_001_memory_authority.py"

TABLES = {
    "aip_memory_source_revision",
    "aip_memory_candidate",
    "aip_memory_candidate_event",
    "aip_memory_item",
    "aip_memory_item_revision",
}

APPEND_ONLY = {
    "aip_memory_source_revision",
    "aip_memory_candidate_event",
    "aip_memory_item_revision",
}


def _config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def test_e1a_migration_is_linear_and_additive() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "aip5_001"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip4_008"' in text
    assert "DELETE FROM " not in text
    for existing_table in (
        "aip_task",
        "aip_task_run",
        "aip_eval_run",
        "aip_lineage_event",
        "aip_logic_graph",
    ):
        assert f"ALTER TABLE {existing_table} " not in text
    for table in TABLES:
        assert f"CREATE TABLE {table}" in text


def test_e1a_tables_force_scope_and_append_only_facts() -> None:
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
               WHERE tablename=ANY(%s) AND policyname LIKE 'tenant_scope_%%_aip5'""",
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


def _insert_source(scope: TenantScope, source_id: str, content_hash: str) -> None:
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_memory_source_revision
               (org_id,project_id,source_id,revision,source_kind,source_uri,
                observed_at,freshness_expires_at,license_id,usage_policy,
                content_hash,provider,provider_version,applicability,created_by)
               VALUES (%s,%s,%s,1,'authorized_document',%s,NOW(),
                 NOW()+INTERVAL '1 day','internal','summary-and-citation',%s,
                 'test','1','[\"vertical:ecommerce\"]'::jsonb,'pytest')""",
            (*scope.key, source_id, f"urn:test:{source_id}", content_hash),
        )
        conn.commit()


def test_e1a_runtime_scope_is_fail_closed_and_workspace_isolated() -> None:
    primary = TenantScope("org-org", "dev-project")
    canary = TenantScope("dev-org", "dev-project")
    with connect() as conn:
        conn.execute(
            """INSERT INTO twa_org(id,name) VALUES ('org-org','栖月汇商贸有限公司')
               ON CONFLICT (id) DO NOTHING"""
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
               VALUES ('org-org','dev-project','默认工作区')
               ON CONFLICT (org_id,project_id) DO NOTHING"""
        )
        conn.commit()

    _insert_source(primary, "source-a", "a" * 64)
    _insert_source(canary, "source-b", "b" * 64)
    with connect(primary) as conn:
        ids = conn.execute(
            """SELECT source_id FROM aip_memory_source_revision
               WHERE source_id IN ('source-a','source-b') ORDER BY source_id"""
        ).fetchall()
        assert [row["source_id"] for row in ids] == ["source-a"]
    with connect(canary) as conn:
        ids = conn.execute(
            """SELECT source_id FROM aip_memory_source_revision
               WHERE source_id IN ('source-a','source-b') ORDER BY source_id"""
        ).fetchall()
        assert [row["source_id"] for row in ids] == ["source-b"]

    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM aip_memory_source_revision"
        ).fetchone()["n"] == 0
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                """INSERT INTO aip_memory_source_revision
                   (org_id,project_id,source_id,revision,source_kind,source_uri,
                    observed_at,freshness_expires_at,license_id,usage_policy,
                    content_hash,provider,provider_version,applicability,created_by)
                   VALUES ('dev-org','dev-project','blocked',1,
                     'authorized_document','urn:test:blocked',NOW(),
                     NOW()+INTERVAL '1 day','internal','summary',%s,'test','1',
                     '[\"vertical:ecommerce\"]'::jsonb,'pytest')""",
                ("f" * 64,),
            )
        conn.rollback()


def test_e1a_schema_rejects_working_and_ungoverned_approval() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "CHECK (memory_layer IN ('episodic','semantic'))" in text
    assert "eval_report_ref IS NOT NULL AND draft_ref IS NOT NULL" in text
    assert "AND approval_event_ref IS NOT NULL" in text
    assert "REFERENCES aip_task(org_id,project_id,task_id)" in text
    assert "REFERENCES aip_task_run(org_id,project_id,run_id)" in text
    assert "aip_memory_item_current_revision_fk" in text
    assert "DEFERRABLE INITIALLY DEFERRED" in text


def test_z_e1a_downgrade_upgrade_preserves_existing_authorities() -> None:
    preserved_tables = ("aip_logic_graph", "aip_eval_run", "aip_lineage_event")
    with connect() as conn:
        before = {
            table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in preserved_tables
        }

    command.downgrade(_config(), "aip4_008")
    with connect() as conn:
        missing = conn.execute(
            "SELECT COUNT(*) AS n FROM pg_class WHERE relname=ANY(%s)",
            (list(TABLES),),
        ).fetchone()["n"]
        assert missing == 0
        after_down = {
            table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in preserved_tables
        }
        assert after_down == before

    command.upgrade(_config(), "head")
    with connect() as conn:
        after_up = {
            table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
            for table in preserved_tables
        }
        assert after_up == before
        restored = conn.execute(
            "SELECT COUNT(*) AS n FROM pg_class WHERE relname=ANY(%s)",
            (list(TABLES),),
        ).fetchone()["n"]
        assert restored == len(TABLES)
