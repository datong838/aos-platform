"""Read-only, fail-closed Provider Health activation fact audit."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from aos_api.aip_provider_health_activation_change_packet import (
    CANONICAL_TENANT,
    ProviderHealthActivationChangePacket,
    build_provider_health_activation_change_packet,
)
from aos_api.aip_provider_health_activation_readiness import (
    ProviderHealthActivationFacts,
    ProviderHealthActivationReadiness,
    evaluate_provider_health_activation_readiness,
)


REQUIRED_FIELDS_BY_SOURCE: dict[str, frozenset[str]] = {
    "deployment": frozenset(
        {"expected_deployed_revision", "deployed_revision"}
    ),
    "environment": frozenset({"canonical_environment_exact"}),
    "plugin": frozenset({"plugin_installed", "action_type_exact"}),
    "authority": frozenset(
        {
            "proposal_exact",
            "approval_exact",
            "lease_exact",
            "receipt_authority_exact",
            "lease_expires_at",
        }
    ),
    "health": frozenset(
        {
            "healthy_probe_count",
            "required_probe_count",
            "health_expires_at",
            "health_cutoff",
        }
    ),
    "source_readiness": frozenset(
        {
            "source_ready_count",
            "source_required_count",
            "source_readiness_fresh_until",
            "source_readiness_cutoff",
        }
    ),
    "binding": frozenset(
        {
            "binding_exact",
            "binding_operational",
            "binding_expires_at",
            "binding_cutoff",
        }
    ),
}


class ActivationFactReader(Protocol):
    """A reader may observe sanitized metadata only and must not mutate state."""

    def __call__(
        self, tenant: str, evaluated_at: datetime
    ) -> "ActivationFactSlice": ...


@dataclass(frozen=True, slots=True)
class ActivationFactSlice:
    source_id: str
    tenant: str
    observed_at: datetime
    values: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.source_id not in REQUIRED_FIELDS_BY_SOURCE:
            raise ValueError("unsupported activation fact source")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class ProviderHealthActivationAudit:
    status: str
    tenant: str
    evaluated_at: datetime
    audit_green: bool
    audit_codes: tuple[str, ...]
    observed_sources: tuple[str, ...]
    source_cutoffs: tuple[tuple[str, str], ...]
    readiness: ProviderHealthActivationReadiness | None
    change_packet: ProviderHealthActivationChangePacket | None

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "tenant": self.tenant,
            "evaluatedAt": self.evaluated_at.isoformat(),
            "auditGreen": self.audit_green,
            "auditCodes": list(self.audit_codes),
            "observedSources": list(self.observed_sources),
            "sourceCutoffs": dict(self.source_cutoffs),
            "readiness": (
                self.readiness.as_public_dict() if self.readiness else None
            ),
            "packetId": (
                self.change_packet.packet_id if self.change_packet else None
            ),
            "executionAuthorized": False,
        }


def audit_provider_health_activation(
    *,
    tenant: str,
    evaluated_at: datetime,
    readers: Mapping[str, ActivationFactReader],
) -> ProviderHealthActivationAudit:
    """Collect each required source once and compose a non-executable audit."""
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")

    codes: list[str] = []
    observed: list[str] = []
    source_cutoffs: list[tuple[str, str]] = []
    collected: dict[str, Any] = {}

    if tenant != CANONICAL_TENANT:
        codes.append("AUDIT_TENANT_NOT_CANONICAL")

    if codes:
        return ProviderHealthActivationAudit(
            status="PROVIDER_HEALTH_ACTIVATION_AUDIT_FAILED_CLOSED",
            tenant=tenant,
            evaluated_at=evaluated_at,
            audit_green=False,
            audit_codes=tuple(codes),
            observed_sources=(),
            source_cutoffs=(),
            readiness=None,
            change_packet=None,
        )

    for source_id, required_fields in REQUIRED_FIELDS_BY_SOURCE.items():
        reader = readers.get(source_id)
        if reader is None:
            codes.append(f"AUDIT_READER_{source_id.upper()}_MISSING")
            continue
        try:
            fact_slice = reader(tenant, evaluated_at)
        except Exception:  # readers are trust boundaries; never expose details
            codes.append(f"AUDIT_READER_{source_id.upper()}_FAILED")
            continue
        observed.append(source_id)
        source_cutoffs.append(
            (source_id, fact_slice.observed_at.isoformat())
        )
        if fact_slice.source_id != source_id:
            codes.append(f"AUDIT_READER_{source_id.upper()}_SOURCE_MISMATCH")
        if fact_slice.tenant != tenant:
            codes.append(f"AUDIT_READER_{source_id.upper()}_TENANT_MISMATCH")
        if fact_slice.observed_at > evaluated_at:
            codes.append(f"AUDIT_READER_{source_id.upper()}_FUTURE_CUTOFF")

        fields = frozenset(fact_slice.values)
        if fields != required_fields:
            codes.append(f"AUDIT_READER_{source_id.upper()}_FIELDS_NOT_EXACT")
            continue
        duplicate = fields.intersection(collected)
        if duplicate:
            codes.append(f"AUDIT_READER_{source_id.upper()}_DUPLICATE_FIELDS")
            continue
        collected.update(fact_slice.values)

    readiness: ProviderHealthActivationReadiness | None = None
    packet: ProviderHealthActivationChangePacket | None = None
    if not codes:
        try:
            facts = ProviderHealthActivationFacts(
                evaluated_at=evaluated_at,
                **collected,
            )
        except (TypeError, ValueError):
            codes.append("AUDIT_FACTS_INVALID")
        else:
            fact_cutoffs = (
                facts.health_cutoff,
                facts.source_readiness_cutoff,
                facts.binding_cutoff,
            )
            if any(value is None for value in fact_cutoffs):
                codes.append("AUDIT_FACT_CUTOFF_MISSING")
            elif len(set(fact_cutoffs)) != 1:
                codes.append("AUDIT_FACT_CUTOFF_MISMATCH")
            readiness = evaluate_provider_health_activation_readiness(facts)
            packet = build_provider_health_activation_change_packet(readiness)

    audit_green = not codes
    return ProviderHealthActivationAudit(
        status=(
            "PROVIDER_HEALTH_ACTIVATION_AUDIT_GREEN"
            if audit_green
            else "PROVIDER_HEALTH_ACTIVATION_AUDIT_FAILED_CLOSED"
        ),
        tenant=tenant,
        evaluated_at=evaluated_at,
        audit_green=audit_green,
        audit_codes=tuple(codes),
        observed_sources=tuple(observed),
        source_cutoffs=tuple(source_cutoffs),
        readiness=readiness,
        change_packet=packet,
    )


__all__ = [
    "ActivationFactReader",
    "ActivationFactSlice",
    "ProviderHealthActivationAudit",
    "REQUIRED_FIELDS_BY_SOURCE",
    "audit_provider_health_activation",
]
