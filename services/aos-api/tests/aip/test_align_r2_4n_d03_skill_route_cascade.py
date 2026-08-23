from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts"
    / "aip"
    / "align_r2_4n_d03_skill_route_cascade.py"
)
SPEC = importlib.util.spec_from_file_location(
    "align_r2_4n_d03_skill_route_cascade", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_r2_4n_contract_forbids_provider_health_and_v6() -> None:
    source = SCRIPT.read_text()
    assert MODULE.PROVIDER_BUSINESS_CALL_LIMIT == 0
    assert MODULE.HEALTH_PROBE_LIMIT == 0
    assert "refresh_r2_provider_health" not in source
    assert "execute_r2_d03_real_pilot" not in source
    assert "--apply v6" not in source


def test_r2_4n_targets_additive_skill_r3_and_new_binding() -> None:
    assert MODULE.SKILL_ID == "ecommerce.skill.D03"
    assert MODULE.SOURCE_SKILL_REVISION == 1
    assert MODULE.TARGET_SKILL_REVISION == 3
    assert MODULE.HISTORICAL_SKILL_REVISION == 2
    assert MODULE.SKILL_BINDING_ID == "ecommerce.data_advisor.skill.D03.r3"
    assert MODULE.HISTORICAL_SKILL_BINDING_ID == "ecommerce.data_advisor.skill.D03.r2"
    assert MODULE.SCOPE.org_id == "org-org"
    assert MODULE.SCOPE.project_id == "dev-project"
    assert MODULE.CANARY_SCOPE.org_id == "dev-org"


def test_r2_4n_uses_skill_publication_gate_not_route_gate() -> None:
    source = SCRIPT.read_text()
    assert "skill.release_gate_ref" in source or "published.release_gate_ref" in source
    assert "route.eval_gate_ref" not in source
    assert "eval_gate_ref\": route.eval_gate_ref" not in source


def test_r2_4n_history_points_to_the_later_sealed_r4_v8_pilot() -> None:
    pilot = (
        Path(__file__).resolve().parents[4]
        / "scripts"
        / "aip"
        / "execute_r2_d03_real_pilot.py"
    )
    spec = importlib.util.spec_from_file_location("execute_r2_d03_real_pilot", pilot)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.SKILL_REVISION == 4
    assert module.SKILL_BINDING_ID == "ecommerce.data_advisor.skill.D03.r4"
    assert module.AGENT_RUN_ID.endswith("real-pilot.v8")
