"""Tenant-bound GET-only W2-08 customer contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_customer_contracts import CustomerAxisReadiness, CustomerBlocker, CustomerCountLedger, CustomerPageInfo, CustomerReadinessAxis, CustomerViewId, CustomerViewSlice, WorkshopCustomerViewEnvelope

Clock = Callable[[], datetime]


class EcommerceWorkshopCustomer:
    """Expose exact customer-authority gaps without returning PII or enabling outreach."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopCustomerViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("customer clock must be timezone-aware")
        views = []
        for view_id in CustomerViewId:
            blocker = CustomerBlocker(code=f"CUSTOMER_{view_id.value.upper()}_AUTHORITY_NOT_AVAILABLE", dependency=f"workshop.customer.{view_id.value}-authority", required_action="provide tenant-bound purpose-scoped exact customer authority without protected contact")
            axes = [CustomerAxisReadiness(axis=axis, status="blocked", blockers=[CustomerBlocker(code=blocker.code, dependency=f"customer.{axis.value}", required_action=blocker.required_action)]) for axis in CustomerReadinessAxis]
            views.append(CustomerViewSlice(view_id=view_id, status="blocked", resource_revision=1, data_cutoff=cutoff, readiness_axes=axes, items=[], authority_refs=[], blockers=[blocker], count_ledger=CustomerCountLedger(input=0, eligible=0, excluded=0, unknown=0, deduplicated=0)))
        return WorkshopCustomerViewEnvelope(tenant=TenantContext(org_id=org_id, project_id=project_id), resource_revision=1, evaluated_at=cutoff, data_cutoff=cutoff, views=views, page=CustomerPageInfo(count=0))


__all__ = ["EcommerceWorkshopCustomer"]
