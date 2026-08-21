from aos_api.aip_agent_registry_contracts import CapabilityReadiness
from aos_api.aip_capability_provider_route import (
    TEXT_CAPABILITY_IDS,
    definition_readiness,
    strip_provider_route_unknown,
)


def test_strip_provider_route_keeps_other_blockers() -> None:
    assert strip_provider_route_unknown(
        [
            "provider_unknown",
            "w0b_contracts_unavailable",
            "aip7_route_authority_unavailable",
        ]
    ) == ["w0b_contracts_unavailable"]
    assert definition_readiness(["w0b_contracts_unavailable"]) is CapabilityReadiness.BLOCKED
    assert definition_readiness([]) is CapabilityReadiness.AVAILABLE
    assert "copy.generate" in TEXT_CAPABILITY_IDS
