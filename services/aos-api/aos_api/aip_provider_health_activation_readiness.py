"""Pure, fail-closed Provider Health deployment and activation readiness."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


def _aware(value: datetime | None) -> bool:
    return value is not None and value.tzinfo is not None


@dataclass(frozen=True, slots=True)
class ProviderHealthActivationFacts:
    """Sanitized facts only; callers must never pass secret material."""

    evaluated_at: datetime
    expected_deployed_revision: str
    deployed_revision: str | None
    canonical_environment_exact: bool
    plugin_installed: bool
    action_type_exact: bool
    proposal_exact: bool
    approval_exact: bool
    lease_exact: bool
    receipt_authority_exact: bool
    lease_expires_at: datetime | None
    healthy_probe_count: int
    required_probe_count: int
    health_expires_at: datetime | None
    health_cutoff: datetime | None
    source_ready_count: int
    source_required_count: int
    source_readiness_fresh_until: datetime | None
    source_readiness_cutoff: datetime | None
    binding_exact: bool
    binding_operational: bool
    binding_expires_at: datetime | None
    binding_cutoff: datetime | None

    def __post_init__(self) -> None:
        if not _aware(self.evaluated_at):
            raise ValueError("evaluated_at must be timezone-aware")
        if not self.expected_deployed_revision.strip():
            raise ValueError("expected_deployed_revision must be non-empty")
        if self.deployed_revision is not None and not self.deployed_revision.strip():
            raise ValueError("deployed_revision must be non-empty when present")
        if self.required_probe_count != 3:
            raise ValueError("canonical Provider Health gate requires 3 probes")
        if self.source_required_count != 12:
            raise ValueError("canonical SourceReadiness gate requires 12 sources")
        if not 0 <= self.healthy_probe_count <= self.required_probe_count:
            raise ValueError("healthy_probe_count is outside required range")
        if not 0 <= self.source_ready_count <= self.source_required_count:
            raise ValueError("source_ready_count is outside required range")
        for name in (
            "lease_expires_at",
            "health_expires_at",
            "health_cutoff",
            "source_readiness_fresh_until",
            "source_readiness_cutoff",
            "binding_expires_at",
            "binding_cutoff",
        ):
            value = getattr(self, name)
            if value is not None and not _aware(value):
                raise ValueError(f"{name} must be timezone-aware when present")


@dataclass(frozen=True, slots=True)
class ProviderHealthActivationReadiness:
    status: str
    evaluated_at: datetime
    expected_deployed_revision: str
    deployed_revision: str | None
    loop_ready: bool
    provider_call_ready: bool
    pilot_ready: bool
    loop_missing: tuple[str, ...]
    provider_call_missing: tuple[str, ...]
    pilot_missing: tuple[str, ...]

    def as_public_dict(self) -> dict[str, Any]:
        """Return metadata and stable codes only, never credentials or secrets."""
        return {
            "status": self.status,
            "evaluatedAt": self.evaluated_at.isoformat(),
            "expectedDeployedRevision": self.expected_deployed_revision,
            "deployedRevision": self.deployed_revision,
            "loopReady": self.loop_ready,
            "providerCallReady": self.provider_call_ready,
            "pilotReady": self.pilot_ready,
            "loopMissing": list(self.loop_missing),
            "providerCallMissing": list(self.provider_call_missing),
            "pilotMissing": list(self.pilot_missing),
        }


def evaluate_provider_health_activation_readiness(
    facts: ProviderHealthActivationFacts,
) -> ProviderHealthActivationReadiness:
    """Evaluate loop, Provider-call and real-pilot gates without side effects."""
    loop_missing: list[str] = []
    if facts.deployed_revision != facts.expected_deployed_revision:
        loop_missing.append("DEPLOYED_REVISION_NOT_EXACT")
    if not facts.canonical_environment_exact:
        loop_missing.append("CANONICAL_ENVIRONMENT_NOT_EXACT")
    if not facts.plugin_installed:
        loop_missing.append("PROVIDER_HEALTH_ACTION_PLUGIN_NOT_INSTALLED")
    if not facts.action_type_exact:
        loop_missing.append("PROVIDER_HEALTH_ACTION_TYPE_NOT_EXACT")

    provider_call_missing = list(loop_missing)
    if not facts.proposal_exact:
        provider_call_missing.append("PROVIDER_HEALTH_PROPOSAL_NOT_EXACT")
    if not facts.approval_exact:
        provider_call_missing.append("PROVIDER_HEALTH_APPROVAL_NOT_EXACT")
    if not facts.lease_exact:
        provider_call_missing.append("PROVIDER_HEALTH_LEASE_NOT_EXACT")
    if not facts.receipt_authority_exact:
        provider_call_missing.append(
            "PROVIDER_HEALTH_RECEIPT_AUTHORITY_NOT_EXACT"
        )
    if (
        facts.lease_expires_at is None
        or facts.lease_expires_at <= facts.evaluated_at
    ):
        provider_call_missing.append("PROVIDER_HEALTH_LEASE_NOT_FRESH")

    pilot_missing = list(provider_call_missing)
    if facts.healthy_probe_count != facts.required_probe_count:
        pilot_missing.append("PROVIDER_HEALTH_NOT_3_OF_3")
    if (
        facts.health_expires_at is None
        or facts.health_expires_at <= facts.evaluated_at
    ):
        pilot_missing.append("PROVIDER_HEALTH_NOT_FRESH")
    if facts.source_ready_count != facts.source_required_count:
        pilot_missing.append("SOURCE_READINESS_NOT_12_OF_12")
    if (
        facts.source_readiness_fresh_until is None
        or facts.source_readiness_fresh_until <= facts.evaluated_at
    ):
        pilot_missing.append("SOURCE_READINESS_NOT_FRESH")
    if not facts.binding_exact:
        pilot_missing.append("PROVIDER_HEALTH_BINDING_NOT_EXACT")
    if not facts.binding_operational:
        pilot_missing.append("PROVIDER_HEALTH_BINDING_NOT_OPERATIONAL")
    if (
        facts.binding_expires_at is None
        or facts.binding_expires_at <= facts.evaluated_at
    ):
        pilot_missing.append("PROVIDER_HEALTH_BINDING_NOT_FRESH")

    cutoffs = (
        facts.health_cutoff,
        facts.source_readiness_cutoff,
        facts.binding_cutoff,
    )
    if any(value is None for value in cutoffs):
        pilot_missing.append("PROVIDER_HEALTH_PILOT_CUTOFF_NOT_EXACT")
    elif len(set(cutoffs)) != 1:
        pilot_missing.append("PROVIDER_HEALTH_PILOT_CUTOFF_MISMATCH")

    loop_ready = not loop_missing
    provider_call_ready = not provider_call_missing
    pilot_ready = not pilot_missing
    if pilot_ready:
        status = "PROVIDER_HEALTH_ACTIVATION_READINESS_GREEN"
    elif provider_call_ready:
        status = "PROVIDER_HEALTH_PILOT_NOT_READY"
    elif loop_ready:
        status = "PROVIDER_HEALTH_CALL_NOT_READY"
    else:
        status = "PROVIDER_HEALTH_LOOP_NOT_READY"
    return ProviderHealthActivationReadiness(
        status=status,
        evaluated_at=facts.evaluated_at,
        expected_deployed_revision=facts.expected_deployed_revision,
        deployed_revision=facts.deployed_revision,
        loop_ready=loop_ready,
        provider_call_ready=provider_call_ready,
        pilot_ready=pilot_ready,
        loop_missing=tuple(loop_missing),
        provider_call_missing=tuple(provider_call_missing),
        pilot_missing=tuple(pilot_missing),
    )


__all__ = [
    "ProviderHealthActivationFacts",
    "ProviderHealthActivationReadiness",
    "evaluate_provider_health_activation_readiness",
]
