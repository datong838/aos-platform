"""Tenant-bound GET-only W2-08 customer contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_customer_contracts import CustomerAxisReadiness, CustomerBlocker, CustomerCountLedger, CustomerPageInfo, CustomerProjection, CustomerReadinessAxis, CustomerViewId, CustomerViewSlice, WorkshopCustomerViewEnvelope
from aos_api.ecommerce_workshop_customer_reader import CustomerCanonicalReader, CustomerReadError, CustomerViewObservation, validate_customer_observation
from aos_api.tenant_scope import TenantScope

Clock = Callable[[], datetime]


class EcommerceWorkshopCustomer:
    """Expose exact customer-authority gaps without returning PII or enabling outreach."""

    def __init__(self, *, reader: CustomerCanonicalReader | None = None, clock: Clock | None = None) -> None:
        self._reader = reader
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopCustomerViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("customer clock must be timezone-aware")
        scope = TenantScope(org_id=org_id, project_id=project_id)
        candidates: list[tuple[CustomerViewId, CustomerBlocker, CustomerViewObservation | None]] = []
        for view_id in CustomerViewId:
            blocker = CustomerBlocker(code=f"CUSTOMER_{view_id.value.upper()}_AUTHORITY_NOT_AVAILABLE", dependency=f"workshop.customer.{view_id.value}-authority", required_action="provide tenant-bound purpose-scoped exact customer authority without protected contact")
            observation = None
            try:
                observation = self._reader.read_view(scope, view_id=view_id, cutoff=cutoff, limit=100) if self._reader is not None else None
                if observation is not None:
                    validate_customer_observation(observation, scope=scope, cutoff=cutoff)
            except (CustomerReadError, ValueError, TypeError):
                observation = None
            candidates.append((view_id, blocker, observation))
        observed_revisions = {item.resource_revision for _, _, item in candidates if item is not None}
        revision_conflict = len(observed_revisions) > 1
        revision = next(iter(observed_revisions)) if len(observed_revisions) == 1 else 1
        views = []
        for view_id, blocker, observation in candidates:
            if revision_conflict:
                blocker = CustomerBlocker(code="CUSTOMER_SHARED_RESOURCE_REVISION_CONFLICT", dependency="workshop.customer.resource-revision", required_action="re-read all four canonical views at one exact revision and cutoff")
                observation = None
            trusted = observation is not None and all(axis.status not in {"blocked", "unknown"} for axis in observation.readiness_axes)
            if trusted:
                axes = list(observation.readiness_axes)
                items = list(observation.items)
                refs = list(observation.authority_refs)
                eligible = sum(item.disclosure == "allowed" for item in items)
                unknown = sum(item.disclosure == "unknown" or item.freshness == "unknown" or item.quality == "unknown" or item.consent == "unknown" or item.retention == "unknown" for item in items)
                excluded = len(items) - eligible - unknown
                ledger = CustomerCountLedger(input=observation.input_count, eligible=eligible, excluded=excluded, unknown=unknown, deduplicated=observation.deduplicated_count)
                view_blockers = []
            elif observation is not None:
                axes = list(observation.readiness_axes)
                items = []
                refs = list(observation.authority_refs)
                axis_blockers = [item for axis in axes for item in axis.blockers]
                unique_blockers = list({item.code: item for item in axis_blockers}.values())
                if unique_blockers:
                    blocker = unique_blockers[0]
                view_blockers = unique_blockers or [blocker]
                ledger = CustomerCountLedger(
                    input=observation.input_count,
                    eligible=0,
                    excluded=0,
                    unknown=observation.suppressed_count,
                    deduplicated=observation.deduplicated_count,
                )
            else:
                axes = [CustomerAxisReadiness(axis=axis, status="blocked", blockers=[CustomerBlocker(code=blocker.code, dependency=f"customer.{axis.value}", required_action=blocker.required_action)]) for axis in CustomerReadinessAxis]
                items, refs = [], []
                ledger = CustomerCountLedger(input=0, eligible=0, excluded=0, unknown=0, deduplicated=0)
                view_blockers = [blocker]
            views.append(CustomerViewSlice(view_id=view_id, status="ready" if trusted else "blocked", resource_revision=revision, data_cutoff=cutoff, readiness_axes=axes, items=items, authority_refs=refs, blockers=view_blockers, count_ledger=ledger))
        return WorkshopCustomerViewEnvelope(tenant=TenantContext(org_id=org_id, project_id=project_id), resource_revision=revision, evaluated_at=cutoff, data_cutoff=cutoff, views=views, page=CustomerPageInfo(count=sum(len(item.items) for item in views)))


__all__ = ["EcommerceWorkshopCustomer"]
