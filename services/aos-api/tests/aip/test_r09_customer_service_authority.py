from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = (
    ROOT / "scripts" / "aip" / "bootstrap_r09_customer_service_authority.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "bootstrap_r09_customer_service_authority", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r09_plan_is_dry_run_by_default_and_preserves_s04() -> None:
    module = _load_module()
    plan = module.build_plan()

    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["negativeCanary"] == {
        "orgId": "dev-org",
        "projectId": "dev-project",
    }
    assert plan["logicIds"] == ["S01", "S02", "S03", "S05", "S06"]
    assert plan["preservedAuthority"] == ["ecommerce.logic.S04"]
    assert plan["providerCalls"] == 0
    assert plan["agentRuns"] == 0
    assert plan["productionWrites"] == 0


def test_r09_parser_requires_explicit_apply_for_writes() -> None:
    module = _load_module()
    assert module.parse_args([]).apply is False
    assert module.parse_args(["--apply"]).apply is True


