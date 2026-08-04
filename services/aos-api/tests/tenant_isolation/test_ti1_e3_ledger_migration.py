from __future__ import annotations

import importlib.util
from pathlib import Path


def _revision_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "228ti1e3_ownership_quarantine.py"
    )
    spec = importlib.util.spec_from_file_location("ti1_e3_revision", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_e3_upgrade_is_append_only_schema_expand(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.upgrade()

    sql = "\n".join(statements).upper()
    assert revision.revision == "228ti1e3ledger"
    assert revision.down_revision == "228ti1e2dual"
    for table in revision._TABLES:
        assert f"CREATE TABLE {table.upper()}" in sql
        assert f"TRG_{table.upper()}_IMMUTABLE" in sql
        assert f"TRG_{table.upper()}_TRUNCATE_GUARD" in sql
    assert "USER_KEY" not in sql
    assert "OBJECT_KEY" not in sql
    assert "INSERT INTO" not in sql
    assert "INSERT SELECT" not in sql
    assert "ALTER TABLE AUTHZ_TUPLE" not in sql


def test_e3_downgrade_refuses_to_drop_nonempty_history(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.downgrade()

    assert "archive tenant E3 ledger before downgrade" in statements[0]
    assert statements[-1] == (
        "DROP FUNCTION IF EXISTS guard_tenant_e3_history_immutable()"
    )

