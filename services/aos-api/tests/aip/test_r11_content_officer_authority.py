from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = (
    ROOT / "scripts" / "aip" / "bootstrap_r11_content_officer_authority.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "bootstrap_r11_content_officer_authority", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r11_plan_is_dry_run_by_default_and_preserves_c02() -> None:
    module = _load_module()
    plan = module.build_plan()

    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["negativeCanary"] == {
        "orgId": "dev-org",
        "projectId": "dev-project",
    }
    assert plan["logicIds"] == ["C01", "C03", "C04", "C05", "C06", "C07", "C08"]
    assert plan["preservedAuthority"] == ["ecommerce.logic.C02"]
    assert plan["providerCalls"] == 0
    assert plan["agentRuns"] == 0
    assert plan["productionWrites"] == 0
    assert plan["mediaGenerations"] == 0
    assert "content publication" in plan["forbiddenSideEffects"]
    assert "media generation or rendering" in plan["forbiddenSideEffects"]


def test_r11_parser_requires_explicit_apply_for_writes() -> None:
    module = _load_module()
    assert module.parse_args([]).apply is False
    assert module.parse_args(["--apply"]).apply is True
