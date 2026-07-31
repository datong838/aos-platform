"""Alembic asset tests for the isolated ecommerce consistency tables."""
from __future__ import annotations

import importlib.util
from pathlib import Path


REVISION = "b7e2c4a92283_ecom_core_consistency.py"
LINK_GUARD_REVISION = "228ec03_link_guard_constraints.py"


def load_revision(filename: str = REVISION):
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location("ecom_core_revision", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_only_isolated_tenant_safe_tables(monkeypatch) -> None:
    revision = load_revision()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)
    revision.upgrade()
    sql = "\n".join(statements)
    assert revision.down_revision == "228ec02oauth"
    assert len(statements) == 7
    for table in (
        "ecom_object",
        "ecom_link",
        "ecom_sync_checkpoint",
        "ecom_ingest_receipt",
    ):
        assert f"CREATE TABLE {table}" in sql
    assert "org_id" in sql and "workspace_id" in sql
    assert "FOREIGN KEY" in sql
    assert "ck_ecom_link_same_shop" not in sql
    assert "ck_ecom_link_endpoint_types" not in sql
    assert "obj_instance" not in sql and "graph_edge" not in sql


def test_downgrade_drops_only_ecom_tables_in_dependency_order(monkeypatch) -> None:
    revision = load_revision()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)
    revision.downgrade()
    assert statements == [
        "DROP TABLE IF EXISTS ecom_ingest_receipt",
        "DROP TABLE IF EXISTS ecom_sync_checkpoint",
        "DROP TABLE IF EXISTS ecom_link",
        "DROP TABLE IF EXISTS ecom_object",
    ]


def test_link_guards_upgrade_from_existing_core_revision(monkeypatch) -> None:
    revision = load_revision(LINK_GUARD_REVISION)
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)
    revision.upgrade()
    sql = "\n".join(statements)
    assert revision.down_revision == "b7e2c4a92283"
    assert len(statements) == 2
    assert "ADD CONSTRAINT ck_ecom_link_same_shop" in sql
    assert "ADD CONSTRAINT ck_ecom_link_endpoint_types" in sql


def test_link_guards_downgrade_only_its_constraints(monkeypatch) -> None:
    revision = load_revision(LINK_GUARD_REVISION)
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)
    revision.downgrade()
    assert statements == [
        "ALTER TABLE ecom_link DROP CONSTRAINT IF EXISTS ck_ecom_link_endpoint_types",
        "ALTER TABLE ecom_link DROP CONSTRAINT IF EXISTS ck_ecom_link_same_shop",
    ]
