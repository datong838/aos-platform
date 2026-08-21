from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts"
    / "aip"
    / "bootstrap_r10_campaign_planner_binding_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r10_campaign_planner_binding_authority", SCRIPT
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_plan_is_tenant_exact_and_has_no_runtime_side_effects() -> None:
    plan = module.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["instanceId"] == "ecommerce.campaign_planner.default"
    assert len(plan["bindings"]) == 5
    assert plan["preservedAuthority"] == [
        "ecommerce.campaign_planner.skill.A02.r2"
    ]
    assert plan["providerCalls"] == 0
    assert plan["agentRuns"] == 0
    assert plan["externalCampaignActions"] == 0
    assert plan["productionActions"] == 0
    assert plan["secretPayloadReads"] == 0


@pytest.mark.parametrize("logic_id", ["A01", "A03", "A04", "A05", "A06"])
def test_binding_ids_are_unique_and_exact(logic_id: str) -> None:
    assert (
        module.binding_id(logic_id)
        == f"ecommerce.campaign_planner.skill.{logic_id}.r2"
    )


def test_required_capability_bindings_are_explicit() -> None:
    assert module.BINDING_SPECS == {
        "A01": [
            "ecommerce.shared.material.collect.r1",
            "ecommerce.shared.performance.review.r1",
        ],
        "A03": [
            "ecommerce.data_advisor.strategy.plan.r2",
            "ecommerce.shared.performance.review.r1",
        ],
        "A04": ["ecommerce.data_advisor.strategy.plan.r2"],
        "A05": ["ecommerce.shared.performance.review.r1"],
        "A06": ["ecommerce.shared.performance.review.r1"],
    }


def test_only_expired_runtime_readiness_is_an_allowed_tail() -> None:
    assert module._EXPECTED_RUNTIME_TAIL == {
        "CAPABILITY_BINDING_NOT_ACTIVE",
        "CAPABILITY_HEALTH_STALE",
    }
