from __future__ import annotations

import importlib.util
from pathlib import Path


def _revision_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "228ti2e1_module_instance_expand.py"
    )
    spec = importlib.util.spec_from_file_location("ti2_e1_revision", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ti2_e1_upgrade_is_expand_only(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.upgrade()

    sql = "\n".join(statements).upper()
    assert revision.revision == "228ti2e1expand"
    assert revision.down_revision == "228ti1e3exec"
    assert "ADD COLUMN MODULE_PK UUID" in sql
    assert "CREATE TABLE MODULE_INSTANCE_OVERLAY" in sql
    assert "CREATE TABLE MODULE_ORGANIZATION_PROFILE" in sql
    assert "CREATE TABLE MODULE_USER_VIEW_PREFERENCE" in sql
    assert "NOT VALID" in sql
    assert "VALIDATE CONSTRAINT" not in sql
    assert "INSERT INTO" not in sql
    assert "UPDATE META_MODULE" not in sql
    assert "DELETE FROM" not in sql
    assert "DROP COLUMN" not in sql


def test_ti2_e1_downgrade_fails_closed(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.downgrade()

    assert "archive TI-2 module expand data before downgrade" in statements[0]
    assert statements[-1].startswith("ALTER TABLE meta_module")
