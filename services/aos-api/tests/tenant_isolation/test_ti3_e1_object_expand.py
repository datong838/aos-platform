from __future__ import annotations

import importlib.util
from pathlib import Path

from aos_api.db import connect
from aos_api.tenant_schema_lint import build_ti3_e1_schema_report

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti3e1_object_expand.py"


def test_ti3_e1_migration_is_expand_only_and_reversible() -> None:
    spec = importlib.util.spec_from_file_location("ti3e1_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti3e1expand"
    assert module.down_revision == "228ti2e7contract"
    assert source.count("ADD COLUMN org_id TEXT NULL") == 1
    assert "NOT VALID" in source
    assert "VALIDATE CONSTRAINT" not in source
    assert "UPDATE " not in source
    assert "ENABLE ROW LEVEL SECURITY" not in source


def test_ti3_e1_real_schema_lint_is_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti3_e1_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {"228ti3e1expand", "228ti3e4validate"}
    assert report["ti3MissingTenantColumns"] == []
    assert report["ti3ExpandColumnsNotNullable"] == []
    assert report["ti3TemplatesWithTenantScope"] == []
    assert report["ti3MissingForeignKeys"] == []
    assert report["ti3PrematurelyValidatedForeignKeys"] == []
