"""Bounded canonical-reader boundary for W2 price-governance views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from aos_api.ecommerce_workshop_price_governance_contracts import PriceAxisReadiness, PriceExactRef, PriceGovernanceViewId, PriceObservationProjection, PriceReadinessAxis
from aos_api.tenant_scope import TenantScope


class PriceGovernanceReadError(RuntimeError):
    """A canonical price dependency could not produce a trustworthy view."""


@dataclass(frozen=True, slots=True)
class PriceGovernanceViewObservation:
    scope: TenantScope
    resource_revision: int
    data_cutoff: datetime
    readiness_axes: tuple[PriceAxisReadiness, ...]
    observations: tuple[PriceObservationProjection, ...] = ()
    authority_refs: tuple[PriceExactRef, ...] = ()
    input_count: int = 0
    deduplicated_count: int = 0


class PriceGovernanceCanonicalReader(Protocol):
    def read_view(self, scope: TenantScope, *, view_id: PriceGovernanceViewId, cutoff: datetime, limit: int) -> PriceGovernanceViewObservation: ...


def validate_price_observation(value: PriceGovernanceViewObservation, *, scope: TenantScope, cutoff: datetime) -> None:
    if value.scope != scope or value.data_cutoff != cutoff or value.resource_revision < 1:
        raise PriceGovernanceReadError("price reader tenant/revision/cutoff drift")
    if [item.axis for item in value.readiness_axes] != list(PriceReadinessAxis) or len(value.observations) > 100 or len(value.authority_refs) > 100:
        raise PriceGovernanceReadError("price reader canonical axes or bound drift")
    if value.readiness_axes[-1].status != "disabled":
        raise PriceGovernanceReadError("price repricing axis must remain disabled")
    if value.input_count < 0 or value.deduplicated_count < 0 or value.input_count != len(value.observations) + value.deduplicated_count:
        raise PriceGovernanceReadError("price reader input/dedup ledger drift")
    observation_ids = [(item.observation_ref.resource_type, item.observation_ref.resource_id, item.observation_ref.revision, item.observation_ref.content_hash, item.observation_ref.receipt_id) for item in value.observations]
    authority_ids = [(item.resource_type, item.resource_id, item.revision, item.content_hash, item.receipt_id) for item in value.authority_refs]
    if len(observation_ids) != len(set(observation_ids)) or len(authority_ids) != len(set(authority_ids)):
        raise PriceGovernanceReadError("price reader duplicate observations or authority refs")


__all__ = ["PriceGovernanceCanonicalReader", "PriceGovernanceReadError", "PriceGovernanceViewObservation", "validate_price_observation"]
