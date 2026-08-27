from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import command
from alembic.config import Config
from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti4_c1_schema_report

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti4c1_ecom_workspace_expand.py"
TABLES = (
    "ecom_ingest_receipt",
    "ecom_link",
    "ecom_object",
    "ecom_sync_checkpoint",
    "oauth_token_store",
)


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_dsn())
    return cfg


def _counts(conn) -> dict[str, int]:
    return {
        table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
        for table in TABLES
    }


def _fk_count(conn) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM pg_constraint "
        "WHERE conname = ANY(%s)",
        ([f"fk_{table}_workspace_ti4" for table in TABLES],),
    ).fetchone()
    return int(row["n"])


def test_migration_is_expand_only_and_uses_canonical_workspace_alias() -> None:
    spec = importlib.util.spec_from_file_location("ti4c1_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti4c1expand"
    assert module.down_revision == "228ti3e7contract"
    assert module.ECOM_WORKSPACE_TABLES == TABLES
    assert "FOREIGN KEY (org_id, workspace_id)" in source
    assert "REFERENCES twa_workspace(org_id, project_id) NOT VALID" in source
    assert "VALIDATE CONSTRAINT" not in source
    assert "INSERT INTO" not in source
    assert "UPDATE " not in source
    assert "DELETE FROM" not in source
    assert "ROW LEVEL SECURITY" not in source


def test_c1_schema_report_is_green_and_fks_remain_not_valid() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti4_c1_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
        "228ti4c1expand",
        "228ti4d1expand",
        "228ti4d4validate",
        "228ti4d6rls",
        "228ti4d7contract",
        "228ti4c3contract",
        "228ti4a1apollo",
        "228ti5a1aip",
        "228ti5a2kv",
        "228ti5a3lineage",
            "228ti5b1models",
            "228ti6bcontract",
            "228ti6cassets",
            "228ti6drelations",
            "228ti6edirectory",
            "biw8_001",
    }
    assert report["ti4EcomInvalidPrimaryKeys"] == []
    assert report["ti4EcomNullableScopeColumns"] == []
    assert report["ti4EcomInvalidWorkspaceForeignKeys"] == []
    assert report["ti4EcomPrematurelyValidatedForeignKeys"] == []
    assert report["ti4EcomWorkspaceForeignKeyCount"] == 5


def test_z_upgrade_downgrade_upgrade_preserves_all_rows() -> None:
    cfg = _config()
    with connect() as conn:
        before = _counts(conn)
        assert _fk_count(conn) == 5
    command.downgrade(cfg, "228ti3e7contract")
    with connect() as conn:
        assert _counts(conn) == before
        assert _fk_count(conn) == 0
    command.upgrade(cfg, "head")
    with connect() as conn:
        assert _counts(conn) == before
        assert _fk_count(conn) == 5
