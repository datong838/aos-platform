from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from aos_api.apollo_catalog import ensure_seed
from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti4_a1_schema_report
from aos_api.tenant_scope import TenantScope
from psycopg.errors import InsufficientPrivilege

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti4a1_apollo_spoke_contract.py"
TEST_SCOPE = TenantScope("dev-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "prj-ops")


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_dsn())
    return cfg


def test_a1_migration_freezes_global_channel_and_scoped_spoke() -> None:
    spec = importlib.util.spec_from_file_location("ti4a1_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti4a1apollo"
    assert module.down_revision == "228ti4c3contract"
    assert "PRIMARY KEY (org_id,project_id,id)" in source
    assert "fk_apollo_spoke_workspace_ti4a1" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "ALTER TABLE apollo_channel ENABLE ROW LEVEL SECURITY" not in source


def test_a1_schema_report_is_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti4_a1_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
        "228ti4a1apollo",
        "228ti5a1aip",
        "228ti5a2kv",
        "228ti5a3lineage",
            "228ti5b1models",
            "228ti6bcontract",
            "228ti6cassets",
            "228ti6drelations",
            "228ti6edirectory",
    }
    assert report["ti4ApolloSpokePrimaryKeyValid"] is True
    assert report["ti4ApolloSpokeWorkspaceForeignKeyValid"] is True
    assert report["ti4ApolloSpokeRlsValid"] is True
    assert report["ti4ApolloSpokePolicyValid"] is True
    assert report["ti4ApolloSpokeWorkspaceOrphanCount"] == 0


def test_a1_same_spoke_id_isolated_across_workspaces() -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES ('dev-org','测试组织') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) VALUES "
            "('dev-org','dev-project','测试工作区'),"
            "('dev-org','prj-ops','运营工作区') "
            "ON CONFLICT (org_id,project_id) DO NOTHING"
        )
        conn.commit()
    ensure_seed()
    spoke_id = "ti4-a1-shared-spoke"
    for scope, name in ((TEST_SCOPE, "test"), (OTHER_SCOPE, "ops")):
        with connect(scope) as conn:
            conn.execute(
                "INSERT INTO apollo_spoke "
                "(org_id,project_id,id,name,kind,channel_id) "
                "VALUES (%s,%s,%s,%s,'lite','dev')",
                (*scope.key, spoke_id, name),
            )
            conn.commit()
    with connect(TEST_SCOPE) as conn:
        assert conn.execute(
            "SELECT name FROM apollo_spoke WHERE id=%s", (spoke_id,)
        ).fetchone()["name"] == "test"
    with connect(OTHER_SCOPE) as conn:
        assert conn.execute(
            "SELECT name FROM apollo_spoke WHERE id=%s", (spoke_id,)
        ).fetchone()["name"] == "ops"
        conn.execute("DELETE FROM apollo_spoke WHERE id=%s", (spoke_id,))
        conn.commit()
    with connect(TEST_SCOPE) as conn:
        assert conn.execute(
            "SELECT name FROM apollo_spoke WHERE id=%s", (spoke_id,)
        ).fetchone()["name"] == "test"
        conn.execute("DELETE FROM apollo_spoke WHERE id=%s", (spoke_id,))
        conn.commit()


def test_a1_no_scope_is_fail_closed() -> None:
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert int(
            conn.execute("SELECT COUNT(*) AS n FROM apollo_spoke").fetchone()["n"]
        ) == 0
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "INSERT INTO apollo_spoke "
                "(org_id,project_id,id,name,kind,channel_id) "
                "VALUES ('dev-org','dev-project','blocked','blocked','lite','dev')"
            )
        conn.rollback()


def test_z_a1_downgrade_upgrade_preserves_spokes() -> None:
    cfg = _config()
    with connect() as conn:
        before = int(conn.execute("SELECT COUNT(*) AS n FROM apollo_spoke").fetchone()["n"])
    command.downgrade(cfg, "228ti4c3contract")
    with connect() as conn:
        assert int(conn.execute("SELECT COUNT(*) AS n FROM apollo_spoke").fetchone()["n"]) == before
        assert conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='apollo_spoke' AND column_name='project_id'"
        ).fetchone() is None
    command.upgrade(cfg, "head")
    with connect() as conn:
        assert int(conn.execute("SELECT COUNT(*) AS n FROM apollo_spoke").fetchone()["n"]) == before
        assert build_ti4_a1_schema_report(conn)["ok"] is True
