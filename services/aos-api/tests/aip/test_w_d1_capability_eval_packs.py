from aos_api.aip_agent_registry_contracts import CapabilityReadiness
from aos_api.aip_capability_eval_pack import (
    definition_readiness,
    strip_eval_pack_unavailable,
)


def test_strip_eval_pack_unavailable_only() -> None:
    reasons = [
        "provider_unknown",
        "eval_pack_unavailable",
        "w0b_contracts_unavailable",
        "aip7_route_authority_unavailable",
    ]
    assert strip_eval_pack_unavailable(reasons) == [
        "provider_unknown",
        "w0b_contracts_unavailable",
        "aip7_route_authority_unavailable",
    ]


def test_definition_readiness_stays_blocked_when_other_reasons() -> None:
    assert definition_readiness(["provider_unknown"]) is CapabilityReadiness.BLOCKED
    assert definition_readiness([]) is CapabilityReadiness.AVAILABLE
