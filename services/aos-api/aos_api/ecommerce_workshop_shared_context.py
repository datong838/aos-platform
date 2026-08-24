"""Tenant-bound GET-only W2-09 shared context contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_shared_context_contracts import WorkshopSharedBlocker, WorkshopSharedContext, WorkshopSharedContextEnvelope, WorkshopSharedContextPage

Clock = Callable[[], datetime]


class EcommerceWorkshopSharedContext:
    """Fail closed until a canonical tenant-bound context assembler is attached."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str, context_id: str) -> WorkshopSharedContextEnvelope:
        now = self._clock()
        if now.utcoffset() is None:
            raise ValueError("shared context clock must be timezone-aware")
        blocker = WorkshopSharedBlocker(code="SHARED_CONTEXT_AUTHORITY_UNAVAILABLE", dependency="workshop.shared-context.authority", required_action="attach tenant-bound active-installation context authority")
        context = WorkshopSharedContext(context_id=context_id, status="blocked", disclosure="unknown", evaluated_at=now, expires_at=now + timedelta(minutes=5), freshness="unknown", readiness="blocked", blockers=[blocker])
        return WorkshopSharedContextEnvelope(tenant=TenantContext(org_id=org_id, project_id=project_id), context=context, timeline=[], navigation_targets=[], page=WorkshopSharedContextPage(count=0))


__all__ = ["EcommerceWorkshopSharedContext"]
