from __future__ import annotations

import importlib.util
from pathlib import Path


def _revision_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "228ti1e1_tenant_scope_expand.py"
    )
    spec = importlib.util.spec_from_file_location("ti1_e1_revision", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ti1_e1_upgrade_is_expand_only(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.upgrade()

    sql = "\n".join(statements).upper()
    assert revision.revision == "228ti1e1expand"
    assert revision.down_revision == "228assetintegration"
    assert len(statements) == 10
    assert sql.count("NOT VALID") == 7
    assert "ADD COLUMN ORG_ID TEXT" in sql
    assert "ADD COLUMN PROJECT_ID TEXT" in sql
    assert "CREATE INDEX IDX_AUTHZ_TUPLE_TENANT_LOOKUP" in sql
    assert all(token not in sql for token in (" UPDATE ", " DELETE ", " INSERT "))
    assert "ENABLE ROW LEVEL SECURITY" not in sql
    assert "FORCE ROW LEVEL SECURITY" not in sql


def test_ti1_e1_downgrade_reverses_only_e1_objects(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.downgrade()

    sql = "\n".join(statements).upper()
    assert len(statements) == 10
    assert sql.count("DROP CONSTRAINT IF EXISTS") == 7
    assert "DROP INDEX IF EXISTS IDX_AUTHZ_TUPLE_TENANT_LOOKUP" in sql
    assert "DROP COLUMN IF EXISTS PROJECT_ID" in sql
    assert "DROP COLUMN IF EXISTS ORG_ID" in sql
