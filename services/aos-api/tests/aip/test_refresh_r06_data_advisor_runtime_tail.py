from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts/aip/refresh_r06_data_advisor_runtime_tail.py"
)
SPEC = importlib.util.spec_from_file_location(
    "refresh_r06_data_advisor_runtime_tail", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_plan_is_exact_and_has_no_provider_or_agent_side_effect() -> None:
    plan = MODULE.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["capabilityBindings"] == [
        "ecommerce.shared.material.collect.r1",
        "ecommerce.shared.performance.review.r1",
    ]
    assert len(plan["skillBindings"]) == 5
    assert plan["providerCalls"] == 0
    assert plan["agentRuns"] == 0
    assert plan["productionActions"] == 0
    assert plan["secretPayloadReads"] == 0


def test_refresh_requires_separate_fresh_health_precondition() -> None:
    assert "3/3 ProviderHealthObservation" in MODULE.build_plan()["precondition"]
