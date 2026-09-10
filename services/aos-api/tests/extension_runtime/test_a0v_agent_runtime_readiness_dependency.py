"""Pure contract tests for the A0-V Agent runtime dependency audit."""

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts/a0v_agent_runtime_readiness_dependency.py"
SPEC = importlib.util.spec_from_file_location("a0v_agent_runtime_readiness", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def snapshot(**updates):
    value = {
        "publishedAgentTemplateCount": 6,
        "evaluatedSkillCount": 37,
        "publishedSkillCount": 0,
        "publishedCapabilityCount": 10,
        "capabilityDefinitionBlockers": [
            "provider_unknown",
            "eval_pack_unavailable",
            "w0b_contracts_unavailable",
            "aip7_route_authority_unavailable",
        ],
        "capabilityEvalAndW0bReadyCount": 0,
        "capabilityEvalAndW0bBlockers": ["eval_pack_unavailable", "w0b_contracts_unavailable"],
        "capabilityProviderRouteReadyCount": 0,
        "capabilityProviderRouteBlockers": ["provider_unknown", "aip7_route_authority_unavailable"],
        "configurationPolicyCount": 7,
        "activeProviderCount": 0,
        "healthyProviderObservationCount": 0,
        "activeModelRouteCount": 0,
        "frozenEvalContractCount": 0,
        "currentPassedEvalGateCount": 0,
        "logicPublicationCount": 0,
        "freshCapabilityBindingCount": 0,
        "freshSkillBindingCount": 0,
        "activeAgentInstanceCount": 0,
        "frozenResponsibilityPlanCount": 0,
        "canaryCounts": {"agent_instances": 0, "providers": 0},
    }
    value.update(updates)
    return value


def test_exact_ecommerce_sets_are_frozen():
    assert len(AUDIT.AGENT_IDS) == 6
    assert len(AUDIT.INSTANCE_IDS) == 6
    assert len(AUDIT.LOGIC_IDS) == 37
    assert len(AUDIT.SKILL_IDS) == 37
    assert len(AUDIT.CAPABILITY_IDS) == 10
    assert len(set(AUDIT.SKILL_IDS)) == 37


def test_current_shape_stops_at_capability_eval_and_w0b_authority():
    result = AUDIT.summarize(snapshot())
    assert result["outcome"] == "A0V_AGENT_RUNTIME_READINESS_BLOCKED"
    assert result["firstUnsatisfiedGate"] == "capabilityEvalAndW0b"
    assert result["nextAction"] == "MATERIALIZE_CAPABILITY_EVAL_AND_W0B_AUTHORITY"


def test_provider_is_next_after_definition_blockers_close():
    result = AUDIT.summarize(snapshot(
        capabilityEvalAndW0bReadyCount=10,
        capabilityEvalAndW0bBlockers=[],
    ))
    assert result["firstUnsatisfiedGate"] == "providers"
    assert result["nextAction"] == "ESTABLISH_REAL_PROVIDER_INSTANCE_AUTHORITY"


def test_canary_authority_fails_closed():
    with pytest.raises(AUDIT.RuntimeReadinessAuditBlocked, match="providers") as captured:
        AUDIT.summarize(snapshot(canaryCounts={"agent_instances": 0, "providers": 1}))
    assert captured.value.code == "CANARY_RUNTIME_AUTHORITY_NOT_EMPTY"


def test_all_real_layers_green_routes_to_four_source_revalidation():
    result = AUDIT.summarize(snapshot(
        publishedSkillCount=37,
        capabilityDefinitionBlockers=[],
        capabilityEvalAndW0bReadyCount=10,
        capabilityEvalAndW0bBlockers=[],
        capabilityProviderRouteReadyCount=10,
        capabilityProviderRouteBlockers=[],
        activeProviderCount=1,
        healthyProviderObservationCount=1,
        activeModelRouteCount=1,
        frozenEvalContractCount=37,
        currentPassedEvalGateCount=37,
        logicPublicationCount=37,
        freshCapabilityBindingCount=10,
        freshSkillBindingCount=37,
        activeAgentInstanceCount=6,
        frozenResponsibilityPlanCount=1,
    ))
    assert result["outcome"] == "A0V_AGENT_RUNTIME_READINESS_GREEN"
    assert result["firstUnsatisfiedGate"] is None
    assert result["nextAction"] == "REVALIDATE_CURRENT_FOUR_SOURCE_CONFIGURATION"
