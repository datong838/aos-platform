from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts"
    / "aip"
    / "bootstrap_r10_campaign_planner_skill_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r10_campaign_planner_skill_authority", SCRIPT
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_plan_is_exact_and_side_effect_free() -> None:
    plan = module.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["schemaHead"] == "aip13_001"
    assert plan["logicIds"] == ["A01", "A03", "A04", "A05", "A06"]
    assert plan["preservedAuthority"] == ["ecommerce.skill.A02@r2"]
    assert plan["providerCalls"] == 0
    assert plan["secretPayloadReads"] == 0
    assert "AgentRun" in plan["forbiddenSideEffects"]
    assert "SkillBinding" in plan["forbiddenSideEffects"]
    assert "campaign-planner external action" in plan["forbiddenSideEffects"]


def test_expected_results_are_independent_and_complete() -> None:
    expected_counts = {"A01": 8, "A03": 10, "A04": 8, "A05": 8, "A06": 10}
    for logic_id in module.CAMPAIGN_PLANNER_LOGIC_IDS:
        values = module._expected_results(logic_id)
        assert len(values) == expected_counts[logic_id]
        assert values[f"{logic_id.lower()}-positive"]["production_written"] is False
        assert values[f"{logic_id.lower()}-unauthorized"]["code"] == f"{logic_id}_EXTERNAL_ACTION_DENIED"
    assert module._expected_results("A03")["a03-over-budget"]["code"] == "A03_BUDGET_EXCEEDED"
    assert module._expected_results("A06")["a06-memory-promotion"]["code"] == "A06_MEMORY_PROMOTION_DENIED"


def test_default_entrypoint_never_applies(monkeypatch, capsys) -> None:
    monkeypatch.setattr(module, "apply", lambda: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type("Args", (), {"apply": False})(),
    )
    assert module.main() == 0
    assert '"status": "planned"' in capsys.readouterr().out
