from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts"
    / "aip"
    / "bootstrap_r11_content_officer_skill_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r11_content_officer_skill_authority", SCRIPT
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_plan_is_exact_and_side_effect_free() -> None:
    plan = module.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["schemaHead"] == "aip13_001"
    assert plan["logicIds"] == ["C01", "C03", "C04", "C05", "C06", "C07", "C08"]
    assert plan["preservedAuthority"] == ["ecommerce.skill.C02@r2"]
    assert plan["providerCalls"] == 0
    assert plan["secretPayloadReads"] == 0
    assert "AgentRun" in plan["forbiddenSideEffects"]
    assert "SkillBinding" in plan["forbiddenSideEffects"]
    assert "media generation" in plan["forbiddenSideEffects"]
    assert "content publication" in plan["forbiddenSideEffects"]


def test_expected_results_are_independent_and_complete() -> None:
    expected_counts = {
        "C01": 7,
        "C03": 8,
        "C04": 8,
        "C05": 7,
        "C06": 8,
        "C07": 8,
        "C08": 10,
    }
    for logic_id in module.CONTENT_OFFICER_LOGIC_IDS:
        values = module._expected_results(logic_id)
        assert len(values) == expected_counts[logic_id]
        assert values[f"{logic_id.lower()}-positive"]["production_written"] is False
        assert values[f"{logic_id.lower()}-unauthorized"]["code"] == f"{logic_id}_EXTERNAL_ACTION_DENIED"
    assert module._expected_results("C03")["c03-copyright-unclear"]["code"] == "C03_COPYRIGHT_NOT_CLEARED"
    assert module._expected_results("C04")["c04-media-action"]["code"] == "C04_EXTERNAL_ACTION_DENIED"
    assert module._expected_results("C08")["c08-memory-promotion"]["code"] == "C08_MEMORY_PROMOTION_DENIED"


def test_default_entrypoint_never_applies(monkeypatch, capsys) -> None:
    monkeypatch.setattr(module, "apply", lambda: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: type("Args", (), {"apply": False})(),
    )
    assert module.main() == 0
    assert '"status": "planned"' in capsys.readouterr().out
