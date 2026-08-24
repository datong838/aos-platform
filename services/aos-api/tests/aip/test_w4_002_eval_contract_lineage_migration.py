from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


def _module():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/w4_002_eval_contract_run_lineage.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_w4_002_adds_exact_eval_contract_lineage_without_rewriting_history() -> None:
    module = _module()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    joined = "\n".join(statements)
    assert module.down_revision == "w3_018"
    assert "ALTER TABLE aip_eval_run ADD COLUMN eval_contract_ref JSONB" in joined
    assert "ALTER TABLE aip_eval_report_revision ADD COLUMN eval_contract_ref JSONB" in joined
    assert "resourceType'='EvalContractRevision" in joined
    assert "eval_contract_ref IS NULL" in joined


def test_w4_002_downgrade_fails_closed_when_bound_lineage_exists() -> None:
    module = _module()
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.downgrade()
    assert "cannot downgrade w4_002" in statements[0]
    assert statements[-1] == "ALTER TABLE aip_eval_run DROP COLUMN eval_contract_ref"
