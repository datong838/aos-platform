from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts"
    / "aip"
    / "bootstrap_r09_customer_service_binding_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r09_customer_service_binding_authority", SCRIPT
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_plan_is_tenant_exact_and_has_no_runtime_side_effects() -> None:
    plan = module.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["instanceId"] == "ecommerce.customer_service.default"
    assert len(plan["bindings"]) == 5
    assert plan["preservedAuthority"] == [
        "ecommerce.customer_service.skill.S04.r2"
    ]
    assert plan["providerCalls"] == 0
    assert plan["agentRuns"] == 0
    assert plan["externalCustomerActions"] == 0
    assert plan["productionActions"] == 0
    assert plan["secretPayloadReads"] == 0


@pytest.mark.parametrize("logic_id", ["S01", "S02", "S03", "S05", "S06"])
def test_binding_ids_are_unique_and_exact(logic_id: str) -> None:
    assert (
        module.binding_id(logic_id)
        == f"ecommerce.customer_service.skill.{logic_id}.r2"
    )


def test_required_capability_bindings_are_explicit() -> None:
    assert module.BINDING_SPECS == {
        "S01": ["ecommerce.shared.material.collect.r1"],
        "S02": ["ecommerce.shared.material.collect.r1"],
        "S03": ["ecommerce.shared.material.collect.r1"],
        "S05": ["ecommerce.shared.copy.generate.r1"],
        "S06": ["ecommerce.shared.performance.review.r1"],
    }


def test_only_expired_runtime_readiness_is_an_allowed_tail() -> None:
    assert module._EXPECTED_RUNTIME_TAIL == {
        "CAPABILITY_BINDING_NOT_ACTIVE",
        "CAPABILITY_HEALTH_STALE",
    }

