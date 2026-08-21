from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts"
    / "aip"
    / "bootstrap_r07_private_domain_manager_skill_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r07_private_domain_manager_skill_authority", SCRIPT
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_plan_is_exact_and_side_effect_free() -> None:
    plan = module.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["schemaHead"] == "aip13_001"
    assert plan["logicIds"] == ["P01", "P03", "P04", "P05"]
    assert plan["preservedAuthority"] == ["ecommerce.skill.P02@r2"]
    assert plan["providerCalls"] == 0
    assert plan["secretPayloadReads"] == 0
    assert "AgentRun" in plan["forbiddenSideEffects"]
    assert "SkillBinding" in plan["forbiddenSideEffects"]
    assert "customer contact" in plan["forbiddenSideEffects"]


def test_expected_results_are_independent_and_complete() -> None:
    for logic_id in module.PRIVATE_DOMAIN_MANAGER_LOGIC_IDS:
        values = module._expected_results(logic_id)
        assert len(values) == 9
        assert values[f"{logic_id.lower()}-positive"]["production_written"] is False
        assert (
            values[f"{logic_id.lower()}-consent-denied"]["code"]
            == f"{logic_id}_CONSENT_REQUIRED"
        )
        assert (
            values[f"{logic_id.lower()}-frequency-exceeded"]["code"]
            == f"{logic_id}_FREQUENCY_CAP_EXCEEDED"
        )


def test_default_entrypoint_never_applies(monkeypatch, capsys) -> None:
    monkeypatch.setattr(module, "apply", lambda: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type("Args", (), {"apply": False})(),
    )
    assert module.main() == 0
    assert '"status": "planned"' in capsys.readouterr().out
