from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti5_a1_schema_report
from aos_api.tenant_scope import TenantScope
from psycopg.errors import InsufficientPrivilege

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti5a1_aip_runtime_contract.py"
SCOPE_A = TenantScope("dev-org", "dev-project")
SCOPE_B = TenantScope("dev-org", "prj-aip-ops")


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_dsn())
    return cfg


def _ensure_workspaces() -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES ('dev-org','测试组织') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) VALUES "
            "('dev-org','dev-project','测试工作区'),"
            "('dev-org','prj-aip-ops','AIP运营工作区') "
            "ON CONFLICT (org_id,project_id) DO NOTHING"
        )
        conn.commit()


def test_a1_migration_contracts_all_aip_runtime_tables() -> None:
    spec = importlib.util.spec_from_file_location("ti5a1_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti5a1aip"
    assert module.down_revision == "228ti4a1apollo"
    assert len(module.AIP_TABLES) == 7
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "REFERENCES twa_workspace(org_id,project_id)" in source


def test_a1_schema_report_is_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti5_a1_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
        "228ti5a1aip",
        "228ti5a2kv",
        "228ti5a3lineage",
            "228ti5b1models",
            "228ti6bcontract",
            "228ti6cassets",
    }
    assert report["ti5AipWorkspaceForeignKeysInvalid"] == []
    assert report["ti5AipRlsUnprotectedTables"] == []
    assert report["ti5AipInvalidPolicies"] == []
    assert report["ti5AipWorkspaceOrphanCount"] == 0


def test_a1_same_graph_id_isolated_across_workspaces() -> None:
    _ensure_workspaces()
    graph_id = "ti5-a1-shared-graph"
    payload = '{"name":"shared"}'
    for scope in (SCOPE_A, SCOPE_B):
        with connect(scope) as conn:
            conn.execute(
                "INSERT INTO aip_logic_graph "
                "(org_id,project_id,graph_id,name,graph_hash,payload) "
                "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                (*scope.key, graph_id, scope.project_id, "0" * 64, payload),
            )
            conn.commit()

    with connect(SCOPE_A) as conn:
        row = conn.execute(
            "SELECT name FROM aip_logic_graph WHERE graph_id=%s", (graph_id,)
        ).fetchone()
        assert row["name"] == "dev-project"
        conn.execute("DELETE FROM aip_logic_graph WHERE graph_id=%s", (graph_id,))
        conn.commit()
    with connect(SCOPE_B) as conn:
        row = conn.execute(
            "SELECT name FROM aip_logic_graph WHERE graph_id=%s", (graph_id,)
        ).fetchone()
        assert row["name"] == "prj-aip-ops"
        conn.execute("DELETE FROM aip_logic_graph WHERE graph_id=%s", (graph_id,))
        conn.commit()


def test_a1_no_scope_is_fail_closed() -> None:
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert (
            int(
                conn.execute("SELECT COUNT(*) AS n FROM aip_logic_graph").fetchone()[
                    "n"
                ]
            )
            == 0
        )
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "INSERT INTO aip_logic_graph "
                "(org_id,project_id,graph_id,name,graph_hash,payload) VALUES "
                "('dev-org','dev-project','blocked','blocked',%s,'{}'::jsonb)",
                ("0" * 64,),
            )
        conn.rollback()


def test_z_a1_downgrade_upgrade_preserves_aip_rows() -> None:
    cfg = _config()
    with connect() as conn:
        before = {
            table: int(
                conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            )
            for table in (
                "aip_logic_graph",
                "aip_logic_graph_revision",
                "aip_logic_graph_runs",
                "aip_logic_graph_run_nodes",
                "aip_eval_suite",
                "aip_eval_report",
                "aip_logic_publication",
            )
        }
    command.downgrade(cfg, "228ti4a1apollo")
    with connect() as conn:
        assert all(
            not bool(row["relrowsecurity"])
            for row in conn.execute(
                "SELECT relrowsecurity FROM pg_class WHERE relname LIKE 'aip_%'"
            ).fetchall()
        )
    command.upgrade(cfg, "head")
    with connect() as conn:
        after = {
            table: int(
                conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            )
            for table in before
        }
        assert after == before
        assert build_ti5_a1_schema_report(conn)["ok"] is True
