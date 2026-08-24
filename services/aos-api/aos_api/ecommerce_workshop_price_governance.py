"""Tenant-bound GET-only W2-07 price-governance contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_price_governance_contracts import PriceAxisReadiness, PriceBlocker, PriceCountLedger, PriceGovernanceViewId, PriceGovernanceViewSlice, PricePageInfo, PriceReadinessAxis, WorkshopPriceGovernanceViewEnvelope

Clock = Callable[[], datetime]


class EcommerceWorkshopPriceGovernance:
    """Expose price authority gaps without inventing quotes or capabilities."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopPriceGovernanceViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("price-governance clock must be timezone-aware")
        views = []
        for view_id in PriceGovernanceViewId:
            blocker = PriceBlocker(code=f"PRICE_{view_id.value.upper()}_AUTHORITY_NOT_AVAILABLE", dependency=f"workshop.price-governance.{view_id.value}-authority", required_action="provide tenant-bound licensed exact price authority at one revision and cutoff")
            axes = []
            for axis in PriceReadinessAxis:
                axis_blocker = PriceBlocker(code="REPRICING_R4_SPECIALIZED_GATE_REQUIRED" if axis is PriceReadinessAxis.REPRICING else "PRICE_DOMAIN_AUTHORITY_NOT_AVAILABLE", dependency=f"price.{axis.value}", required_action="keep repricing disabled until the specialized R4 gate is operational" if axis is PriceReadinessAxis.REPRICING else "attach the exact licensed domain authority")
                axes.append(PriceAxisReadiness(axis=axis, status="disabled" if axis is PriceReadinessAxis.REPRICING else "blocked", blockers=[axis_blocker]))
            views.append(PriceGovernanceViewSlice(view_id=view_id, status="blocked", resource_revision=1, data_cutoff=cutoff, readiness_axes=axes, observations=[], authority_refs=[], blockers=[blocker], count_ledger=PriceCountLedger(input=0, eligible=0, excluded=0, needsReview=0, unknown=0, deduplicated=0)))
        return WorkshopPriceGovernanceViewEnvelope(tenant=TenantContext(org_id=org_id, project_id=project_id), resource_revision=1, evaluated_at=cutoff, data_cutoff=cutoff, views=views, page=PricePageInfo(count=0))


__all__ = ["EcommerceWorkshopPriceGovernance"]
