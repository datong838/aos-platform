"""Static migration contract for the additive W6-01 exact snapshots."""

from importlib import util
from pathlib import Path
from unittest.mock import patch

MIGRATION = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "w6_001_exact_assignee_resolution.py"
)


def _load():
    spec = util.spec_from_file_location("w6_001_exact_assignee_resolution", MIGRATION)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_w6_001_is_single_head_additive_and_preserves_append_only_receipts() -> None:
    module = _load()
    assert module.revision == "w6_001"
    assert module.down_revision == "w5_006"
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)

    assert "ALTER TABLE aip_tool_binding" in sql
    assert "ALTER TABLE aip_assignee_resolution_receipt" in sql
    assert "required_capability_refs JSONB" in sql
    assert "candidate_decisions JSONB" in sql
    assert "snapshot_hash CHAR(64)" in sql
    assert "expires_at TIMESTAMPTZ" in sql
    assert "GRANT UPDATE" not in sql
    assert "CREATE TABLE" not in sql


def test_w6_001_downgrade_only_removes_additive_columns() -> None:
    module = _load()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    sql = "\n".join(statements)

    assert "DROP TABLE" not in sql
    assert "DROP COLUMN IF EXISTS snapshot_hash" in sql
    assert "DROP COLUMN IF EXISTS capability_binding_ids" in sql
