from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


def _module():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/w4_003_review_return_lineage.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_w4_003_adds_tenant_rule_event_payload_and_return_impact() -> None:
    module = _module()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    sql = "\n".join(statements)
    assert module.down_revision == "w4_002"
    assert "CREATE TABLE aip_review_rule_revision" in sql
    assert "TO aos_runtime" in sql
    assert "guard_aip4_append_only" in sql
    assert "aip_review_issue_event ADD COLUMN payload JSONB" in sql
    assert "aip_return_decision ADD COLUMN impact_decisions JSONB" in sql


def test_w4_003_downgrade_refuses_to_erase_review_lineage() -> None:
    module = _module()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    assert "cannot downgrade w4_003" in statements[0]
    assert statements[-1] == "DROP TABLE aip_review_rule_revision"
