from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts"
    / "aip"
    / "bootstrap_r09_customer_service_skill_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r09_customer_service_skill_authority", SCRIPT
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_plan_is_exact_and_side_effect_free() -> None:
    plan = module.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["schemaHead"] == "aip13_001"
    assert plan["logicIds"] == ["S01", "S02", "S03", "S05", "S06"]
    assert plan["preservedAuthority"] == ["ecommerce.skill.S04@r2"]
    assert plan["providerCalls"] == 0
    assert plan["secretPayloadReads"] == 0
    assert "AgentRun" in plan["forbiddenSideEffects"]
    assert "SkillBinding" in plan["forbiddenSideEffects"]
    assert "customer-service external action" in plan["forbiddenSideEffects"]


def test_expected_results_are_independent_and_complete() -> None:
    expected_counts = {"S01": 7, "S02": 10, "S03": 10, "S05": 10, "S06": 11}
    for logic_id in module.CUSTOMER_SERVICE_LOGIC_IDS:
        values = module._expected_results(logic_id)
        assert len(values) == expected_counts[logic_id]
        assert values[f"{logic_id.lower()}-positive"]["production_written"] is False
        assert values[f"{logic_id.lower()}-unauthorized"]["code"] == f"{logic_id}_EXTERNAL_ACTION_DENIED"
    assert module._expected_results("S02")["s02-field-overreach"]["code"] == "S02_FIELD_ALLOWLIST_DENIED"
    assert module._expected_results("S06")["s06-survey-send"]["code"] == "S06_SURVEY_SEND_DENIED"


def test_default_entrypoint_never_applies(monkeypatch, capsys) -> None:
    monkeypatch.setattr(module, "apply", lambda: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type("Args", (), {"apply": False})(),
    )
    assert module.main() == 0
    assert '"status": "planned"' in capsys.readouterr().out

