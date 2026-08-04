from __future__ import annotations

import importlib.util
from pathlib import Path


def _revision_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "228ti1e2_authz_dual_write.py"
    )
    spec = importlib.util.spec_from_file_location("ti1_e2_revision", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ti1_e2_upgrade_adds_redacted_ledger_only(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.upgrade()

    sql = "\n".join(statements).upper()
    assert revision.revision == "228ti1e2dual"
    assert revision.down_revision == "228ti1e1expand"
    assert len(statements) == 2
    assert "CREATE TABLE TENANT_DUAL_WRITE_LEDGER" in sql
    assert "KEY_HASH" in sql
    assert "USER_KEY" not in sql
    assert "OBJECT_KEY" not in sql
    assert all(token not in sql for token in (" UPDATE ", " DELETE ", "ALTER TABLE AUTHZ_TUPLE"))


def test_ti1_e2_downgrade_drops_only_new_ledger(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.downgrade()

    assert statements == ["DROP TABLE IF EXISTS tenant_dual_write_ledger"]
