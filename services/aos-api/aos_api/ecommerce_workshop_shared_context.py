"""Tenant-bound GET-only W2-09 shared context contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_shared_context_contracts import WorkshopSharedBlocker, WorkshopSharedContext, WorkshopSharedContextEnvelope, WorkshopSharedContextPage
from aos_api.ecommerce_workshop_shared_context_reader import SharedContextCanonicalReader, SharedContextReadError, validate_shared_context_observation
from aos_api.tenant_scope import TenantScope

Clock = Callable[[], datetime]


class EcommerceWorkshopSharedContext:
    """Fail closed until a canonical tenant-bound context assembler is attached."""

    def __init__(self, *, reader: SharedContextCanonicalReader | None = None, clock: Clock | None = None) -> None:
        self._reader = reader
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _closed(*, scope: TenantScope, context_id: str, now: datetime, status: str, code: str, action: str) -> WorkshopSharedContextEnvelope:
        blocker = WorkshopSharedBlocker(code=code, dependency="workshop.shared-context.authority", required_action=action)
        context = WorkshopSharedContext(context_id=context_id, status=status, disclosure="unknown", evaluated_at=now, expires_at=now + timedelta(minutes=5), freshness="unknown", readiness="blocked", blockers=[blocker])
        return WorkshopSharedContextEnvelope(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id), context=context, timeline=[], navigation_targets=[], page=WorkshopSharedContextPage(count=0))

    def read(self, *, org_id: str, project_id: str, context_id: str) -> WorkshopSharedContextEnvelope:
        now = self._clock()
        if now.utcoffset() is None:
            raise ValueError("shared context clock must be timezone-aware")
        scope = TenantScope(org_id=org_id, project_id=project_id)
        if self._reader is None:
            return self._closed(scope=scope, context_id=context_id, now=now, status="blocked", code="SHARED_CONTEXT_AUTHORITY_UNAVAILABLE", action="attach tenant-bound active-installation context authority")
        try:
            value = self._reader.read_context(scope, context_id=context_id, cutoff=now, limit=100)
            if value.scope != scope or value.context.context_id != context_id:
                return self._closed(scope=scope, context_id=context_id, now=now, status="forbidden", code="SHARED_CONTEXT_SCOPE_MISMATCH", action="re-authorize the opaque context token for this exact tenant")
            if value.context.expires_at <= now:
                return self._closed(scope=scope, context_id=context_id, now=now, status="expired", code="SHARED_CONTEXT_EXPIRED", action="create a fresh tenant-bound context token")
            validate_shared_context_observation(value, scope=scope, context_id=context_id, cutoff=now, limit=100)
        except (SharedContextReadError, ValueError, TypeError):
            return self._closed(scope=scope, context_id=context_id, now=now, status="blocked", code="SHARED_CONTEXT_AUTHORITY_INVALID", action="repair the tenant-bound exact context authority")
        return WorkshopSharedContextEnvelope(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id), context=value.context, timeline=list(value.timeline), navigation_targets=list(value.navigation_targets), page=WorkshopSharedContextPage(count=len(value.timeline)))


__all__ = ["EcommerceWorkshopSharedContext"]
