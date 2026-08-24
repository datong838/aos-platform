"""Tenant-bound GET-only W2-06 analyst contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_analyst_contracts import AnalystAxisReadiness, AnalystBlocker, AnalystCountLedger, AnalystPageInfo, AnalystReadinessAxis, AnalystViewId, AnalystViewSlice, WorkshopAnalystViewEnvelope

Clock = Callable[[], datetime]


class EcommerceWorkshopAnalyst:
    """Expose current authority gaps without inventing business metrics."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopAnalystViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("analyst clock must be timezone-aware")
        revision = 1
        views: list[AnalystViewSlice] = []
        for view_id in AnalystViewId:
            blocker = AnalystBlocker(code=f"ANALYST_{view_id.value.upper()}_AUTHORITY_NOT_AVAILABLE", dependency=f"workshop.analyst.{view_id.value}-authority", required_action="provide tenant-bound exact metric, quality, evidence and plan refs at one cutoff")
            views.append(AnalystViewSlice(view_id=view_id, status="blocked", resource_revision=revision, data_cutoff=cutoff, readiness_axes=[AnalystAxisReadiness(axis=axis, status="blocked", blockers=[blocker]) for axis in AnalystReadinessAxis], blockers=[blocker], count_ledger=AnalystCountLedger(denominator=0, ready=0, unknown=0, blocked=0, conflict=0)))
        return WorkshopAnalystViewEnvelope(tenant=TenantContext(org_id=org_id, project_id=project_id), resource_revision=revision, evaluated_at=cutoff, data_cutoff=cutoff, views=views, page=AnalystPageInfo(count=0))


__all__ = ["EcommerceWorkshopAnalyst"]
