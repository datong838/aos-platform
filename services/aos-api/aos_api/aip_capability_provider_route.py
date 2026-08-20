"""Helpers for W-D4 definition-layer provider/route reason stripping."""

from __future__ import annotations

from aos_api.aip_agent_registry_contracts import CapabilityReadiness

PROVIDER_ROUTE_REASONS = frozenset(
    {"provider_unknown", "aip7_route_authority_unavailable"}
)

TEXT_CAPABILITY_IDS = frozenset(
    {
        "material.collect",
        "strategy.plan",
        "copy.generate",
        "script.compose",
        "content.review",
        "platform.adapt",
        "performance.review",
    }
)

MEDIA_CAPABILITY_IDS = frozenset(
    {"speech.synthesize", "video.compose", "live.orchestrate"}
)


def strip_provider_route_unknown(reasons: list[str]) -> list[str]:
    return [code for code in reasons if code not in PROVIDER_ROUTE_REASONS]


def definition_readiness(reasons: list[str]) -> CapabilityReadiness:
    return (
        CapabilityReadiness.AVAILABLE
        if not reasons
        else CapabilityReadiness.BLOCKED
    )
