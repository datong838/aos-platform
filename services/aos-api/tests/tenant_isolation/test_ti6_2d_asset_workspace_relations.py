from __future__ import annotations

import importlib.util
from pathlib import Path

from aos_api.db import connect

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti6d_asset_workspace_relations.py"


def _migration_module():
    spec = importlib.util.spec_from_file_location("ti6_2d_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ti6_2d_relation_migration_is_frozen() -> None:
    module = _migration_module()

    assert module.revision == "228ti6drelations"
    assert module.down_revision == "228ti6cassets"
    assert set(module.RELATIONS) == {
        "bundle_composition",
        "bundle_installation_command",
        "integration_case",
    }


def test_ti6_2d_asset_roots_have_validated_workspace_relations() -> None:
    module = _migration_module()
    with connect() as conn:
        rows = conn.execute(
            "SELECT conrelid::regclass::text AS table_name,conname,convalidated,"
            "pg_get_constraintdef(oid) AS definition FROM pg_constraint "
            "WHERE conname=ANY(%s) ORDER BY conname",
            (list(module.RELATIONS.values()),),
        ).fetchall()

    assert len(rows) == 3
    assert all(row["convalidated"] for row in rows)
    assert {row["table_name"] for row in rows} == set(module.RELATIONS)
    assert all(
        "FOREIGN KEY (org_id, project_id)" in row["definition"]
        and "REFERENCES meta_workspace(org_id, project_id)" in row["definition"]
        for row in rows
    )
