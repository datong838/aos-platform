from __future__ import annotations

import importlib.util
from pathlib import Path


def _revision_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "228ti1e3_execution_events.py"
    )
    spec = importlib.util.spec_from_file_location("ti1_e3_exec_revision", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_execution_event_upgrade_is_append_only(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.upgrade()

    sql = "\n".join(statements).upper()
    assert revision.revision == "228ti1e3exec"
    assert revision.down_revision == "228ti1e3ledger"
    assert "CREATE TABLE TENANT_OWNERSHIP_DECISION_EVENT" in sql
    assert "ADD COLUMN ACTOR_HASH" in sql
    assert "USER_KEY" not in sql
    assert "OBJECT_KEY" not in sql
    assert "INSERT INTO" not in sql


def test_execution_event_downgrade_fails_closed(monkeypatch) -> None:
    revision = _revision_module()
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)

    revision.downgrade()

    assert "archive tenant E3 execution events before downgrade" in statements[0]
    assert statements[-1] == (
        "ALTER TABLE tenant_backfill_batch_event DROP COLUMN actor_hash"
    )
