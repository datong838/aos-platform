from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts"
    / "aip"
    / "bootstrap_r11_content_officer_binding_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "bootstrap_r11_content_officer_binding_authority", SCRIPT
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_plan_is_tenant_exact_and_has_no_runtime_side_effects() -> None:
    plan = module.build_plan()
    assert plan["scope"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert plan["instanceId"] == "ecommerce.content_officer.default"
    assert len(plan["bindings"]) == 7
    assert plan["preservedAuthority"] == [
        "ecommerce.content_officer.skill.C02.r2"
    ]
    assert plan["providerCalls"] == 0
    assert plan["agentRuns"] == 0
    assert plan["externalContentActions"] == 0
    assert plan["mediaGenerations"] == 0
    assert plan["memoryPromotions"] == 0
    assert plan["productionActions"] == 0
    assert plan["secretPayloadReads"] == 0


def test_binding_ids_are_unique_and_exact() -> None:
    assert len({module.binding_id(item) for item in module.BINDING_SPECS}) == 7
    for logic_id in module.BINDING_SPECS:
        assert (
            module.binding_id(logic_id)
            == f"ecommerce.content_officer.skill.{logic_id}.r2"
        )


def test_required_capability_bindings_are_explicit() -> None:
    assert module.BINDING_SPECS == {
        "C01": ["ecommerce.shared.material.collect.r1"],
        "C03": ["ecommerce.shared.copy.generate.r1"],
        "C04": ["ecommerce.shared.script.compose.r1"],
        "C05": ["ecommerce.shared.platform.adapt.r1"],
        "C06": ["ecommerce.shared.content.review.r1"],
        "C07": [
            "ecommerce.shared.material.collect.r1",
            "ecommerce.shared.copy.generate.r1",
        ],
        "C08": ["ecommerce.shared.performance.review.r1"],
    }


def test_only_expired_runtime_readiness_is_an_allowed_tail() -> None:
    assert module._base._EXPECTED_RUNTIME_TAIL == {
        "CAPABILITY_BINDING_NOT_ACTIVE",
        "CAPABILITY_HEALTH_STALE",
    }


def test_import_does_not_mutate_campaign_planner_base_configuration() -> None:
    assert module._base.INSTANCE_ID == "ecommerce.campaign_planner.default"
    assert len(module._base.BINDING_SPECS) == 5
