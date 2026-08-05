from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import command
from alembic.config import Config
from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti4_d1_schema_report

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti4d1_data_os_expand.py"
EXPAND_TABLES = (
    "meta_dataset",
    "meta_dataset_history",
    "meta_pipeline",
    "meta_sync",
    "phase5_pipeline_graph",
)
TABLES = (*EXPAND_TABLES, "meta_schedule", "meta_source")


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
        "SELECT COUNT(*) AS n FROM pg_constraint WHERE conname = ANY(%s)",
        ([f"fk_{table}_workspace_ti4d1" for table in TABLES],),
    ).fetchone()
    return int(row["n"])


def test_d1_migration_is_nullable_expand_only() -> None:
    spec = importlib.util.spec_from_file_location("ti4d1_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti4d1expand"
    assert module.down_revision == "228ti4c1expand"
    assert module.DATA_OS_EXPAND_TABLES == EXPAND_TABLES
    assert module.DATA_OS_TENANT_TABLES == TABLES
    assert source.count("ADD COLUMN org_id TEXT NULL") == 1
    assert source.count("ADD COLUMN project_id TEXT NULL") == 1
    assert "REFERENCES twa_workspace(org_id, project_id) NOT VALID" in source
    assert "VALIDATE CONSTRAINT" not in source
    assert "INSERT INTO" not in source
    assert "UPDATE " not in source
    assert "DELETE FROM" not in source
    assert "ROW LEVEL SECURITY" not in source


def test_d1_schema_report_is_green_and_preserves_frozen_counts() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti4_d1_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
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
    }
    assert report["ti4DataOsMissingScopeColumns"] == []
    assert report["ti4DataOsNonNullableExpandColumns"] == []
    assert report["ti4DataOsInvalidWorkspaceForeignKeys"] == []
    assert report["ti4DataOsPrematurelyValidatedForeignKeys"] == []
    assert report["ti4DataOsWorkspaceForeignKeyCount"] == 7
    assert set(report["ti4DataOsRowCounts"]) == set(TABLES)


def test_z_d1_upgrade_downgrade_upgrade_preserves_all_rows() -> None:
    cfg = _config()
    with connect() as conn:
        before = _counts(conn)
        assert _fk_count(conn) == 7
    command.downgrade(cfg, "228ti4c1expand")
    with connect() as conn:
        assert _counts(conn) == before
        assert _fk_count(conn) == 0
    command.upgrade(cfg, "head")
    with connect() as conn:
        assert _counts(conn) == before
        assert _fk_count(conn) == 7
