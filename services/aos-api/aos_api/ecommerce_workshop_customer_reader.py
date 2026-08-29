"""Bounded canonical-reader boundary for W2 customer views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from aos_api.ecommerce_workshop_customer_contracts import CustomerAxisReadiness, CustomerExactRef, CustomerProjection, CustomerReadinessAxis, CustomerViewId
from aos_api.tenant_scope import TenantScope


class CustomerReadError(RuntimeError):
    """A canonical customer dependency could not produce a trustworthy view."""


@dataclass(frozen=True, slots=True)
class CustomerViewObservation:
    scope: TenantScope
    resource_revision: int
    data_cutoff: datetime
    readiness_axes: tuple[CustomerAxisReadiness, ...]
    items: tuple[CustomerProjection, ...] = ()
    authority_refs: tuple[CustomerExactRef, ...] = ()
    input_count: int = 0
    deduplicated_count: int = 0
    suppressed_count: int = 0


class CustomerCanonicalReader(Protocol):
    def read_view(self, scope: TenantScope, *, view_id: CustomerViewId, cutoff: datetime, limit: int) -> CustomerViewObservation: ...


def validate_customer_observation(value: CustomerViewObservation, *, scope: TenantScope, cutoff: datetime) -> None:
    if value.scope != scope or value.data_cutoff != cutoff or value.resource_revision < 1:
        raise CustomerReadError("customer reader tenant/revision/cutoff drift")
    if [item.axis for item in value.readiness_axes] != list(CustomerReadinessAxis) or len(value.items) > 100 or len(value.authority_refs) > 100:
        raise CustomerReadError("customer reader canonical axes or bound drift")
    if (
        value.input_count < 0
        or value.deduplicated_count < 0
        or value.suppressed_count < 0
        or value.input_count
        != len(value.items) + value.deduplicated_count + value.suppressed_count
    ):
        raise CustomerReadError("customer reader input/dedup ledger drift")
    item_ids = [(item.customer_ref.resource_type, item.customer_ref.resource_id, item.customer_ref.revision, item.customer_ref.content_hash, item.customer_ref.receipt_id) for item in value.items]
    authority_ids = [(item.resource_type, item.resource_id, item.revision, item.content_hash, item.receipt_id) for item in value.authority_refs]
    if len(item_ids) != len(set(item_ids)) or len(authority_ids) != len(set(authority_ids)):
        raise CustomerReadError("customer reader duplicate items or authority refs")


__all__ = ["CustomerCanonicalReader", "CustomerReadError", "CustomerViewObservation", "validate_customer_observation"]
