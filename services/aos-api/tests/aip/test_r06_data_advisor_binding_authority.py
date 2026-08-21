from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts/aip/bootstrap_r06_data_advisor_binding_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r06_data_advisor_binding_authority", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_plan_is_tenant_exact_and_has_no_runtime_side_effects() -> None:
    plan = MODULE.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["instanceId"] == "ecommerce.data_advisor.default"
    assert len(plan["bindings"]) == 5
    assert plan["providerCalls"] == 0
    assert plan["agentRuns"] == 0
    assert plan["productionActions"] == 0
    assert plan["secretPayloadReads"] == 0


@pytest.mark.parametrize("logic_id", ["D01", "D02", "D04", "D05", "D06"])
def test_binding_ids_are_unique_and_exact(logic_id: str) -> None:
    assert (
        MODULE.binding_id(logic_id)
        == f"ecommerce.data_advisor.skill.{logic_id}.r2"
    )


def test_required_capability_bindings_are_explicit() -> None:
    assert MODULE.BINDING_SPECS == {
        "D01": ["ecommerce.shared.material.collect.r1"],
        "D02": ["ecommerce.shared.material.collect.r1"],
        "D04": [],
        "D05": ["ecommerce.shared.performance.review.r1"],
        "D06": ["ecommerce.shared.performance.review.r1"],
    }


def test_only_stale_capability_health_is_an_allowed_runtime_tail() -> None:
    assert MODULE._EXPECTED_RUNTIME_TAIL == {
        "CAPABILITY_BINDING_NOT_ACTIVE",
        "CAPABILITY_HEALTH_STALE",
    }
