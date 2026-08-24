"""Static and captured-SQL tests for W3-11 authority migration."""

from __future__ import annotations

from importlib import util
from pathlib import Path
from unittest.mock import patch


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "w3_011_content_campaign_authority.py"
)


def _load():
    spec = util.spec_from_file_location(
        "w3_011_content_campaign_authority", MIGRATION
    )
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_extends_current_single_head_and_freezes_tenant_security() -> None:
    module = _load()
    assert module.revision == "w3_011"
    assert module.down_revision == "d0_after_001"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    for table in module.TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
        assert f"tenant_scope_{table}_w3_011" in sql
    for table in module.APPEND_ONLY_TABLES:
        assert f"REVOKE UPDATE,DELETE,TRUNCATE ON {table}" in sql
        assert f"trg_{table}_append_only" in sql
        assert f"trg_{table}_truncate_guard" in sql
    assert "resolved_start<resolved_end" in sql
    assert "UNIQUE(org_id,project_id,operation,idempotency_key)" in sql


def test_downgrade_rejects_nonempty_canonical_history_before_reverse_drop() -> None:
    module = _load()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    assert "cannot downgrade w3_011" in statements[0]
    assert "ERRCODE = '55000'" in statements[0]
    for table in module.TABLES:
        assert f"EXISTS (SELECT 1 FROM {table} LIMIT 1)" in statements[0]
    drops = [item for item in statements if item.startswith("DROP TABLE")]
    assert drops == [
        f"DROP TABLE IF EXISTS {table} CASCADE"
        for table in reversed(module.TABLES)
    ]
