from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from aos_api.aip_kv_store import get_payload, put_payload
from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti5_a2_schema_report
from aos_api.tenant_scope import TenantScope

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti5a2_aip_kv_contract.py"
SCOPE_A = TenantScope("dev-org", "dev-project")
SCOPE_B = TenantScope("dev-org", "prj-kv-ops")


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
            "('dev-org','prj-kv-ops','KV运营工作区') "
            "ON CONFLICT (org_id,project_id) DO NOTHING"
        )
        conn.commit()


def test_a2_migration_freezes_allowlist_and_scoped_contract() -> None:
    spec = importlib.util.spec_from_file_location("ti5a2_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti5a2kv"
    assert module.down_revision == "228ti5a1aip"
    assert len(module.TEST_ORG_KEYS) == 23
    assert "ASSIGN_TEST_ORG" in source
    assert "PRIMARY KEY (org_id,project_id,key)" in source
    assert "FORCE ROW LEVEL SECURITY" in source


def test_a2_schema_report_is_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti5_a2_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
        "228ti5a2kv",
        "228ti5a3lineage",
        "228ti5b1models",
        "228ti6bcontract",
        "228ti6cassets",
        "228ti6drelations",
        "228ti6edirectory",
    }
    assert report["ti5AipKvScopeValid"] is True
    assert report["ti5AipKvPrimaryKeyValid"] is True
    assert report["ti5AipKvWorkspaceForeignKeyValid"] is True
    assert report["ti5AipKvRlsValid"] is True
    assert report["ti5AipKvPolicyValid"] is True
    assert report["ti5AipKvLedgerOrphanCount"] == 0
    assert report["ti5AipKvNullScopeCount"] == 0


def test_a2_same_key_isolated_across_workspaces() -> None:
    _ensure_workspaces()
    key = "ti5-a2-shared-key"
    put_payload(key, {"owner": "test"}, SCOPE_A)
    put_payload(key, {"owner": "ops"}, SCOPE_B)
    assert get_payload(key, SCOPE_A) == {"owner": "test"}
    assert get_payload(key, SCOPE_B) == {"owner": "ops"}
    with connect(SCOPE_A) as conn:
        conn.execute("DELETE FROM meta_aip_kv WHERE key=%s", (key,))
        conn.commit()
    assert get_payload(key, SCOPE_A) is None
    assert get_payload(key, SCOPE_B) == {"owner": "ops"}
    with connect(SCOPE_B) as conn:
        conn.execute("DELETE FROM meta_aip_kv WHERE key=%s", (key,))
        conn.commit()


def test_a2_no_scope_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="tenant scope is required"):
        get_payload("model_routes")
    with pytest.raises(RuntimeError, match="tenant scope is required"):
        put_payload("blocked", {})
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert (
            int(conn.execute("SELECT COUNT(*) AS n FROM meta_aip_kv").fetchone()["n"])
            == 0
        )


def test_z_a2_downgrade_upgrade_preserves_kv() -> None:
    cfg = _config()
    with connect() as conn:
        before = int(
            conn.execute("SELECT COUNT(*) AS n FROM meta_aip_kv").fetchone()["n"]
        )
    command.downgrade(cfg, "228ti5a1aip")
    with connect() as conn:
        assert (
            int(conn.execute("SELECT COUNT(*) AS n FROM meta_aip_kv").fetchone()["n"])
            == before
        )
        assert (
            conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='meta_aip_kv' AND column_name='project_id'"
            ).fetchone()
            is None
        )
    command.upgrade(cfg, "head")
    with connect() as conn:
        assert (
            int(conn.execute("SELECT COUNT(*) AS n FROM meta_aip_kv").fetchone()["n"])
            == before
        )
        assert build_ti5_a2_schema_report(conn)["ok"] is True
