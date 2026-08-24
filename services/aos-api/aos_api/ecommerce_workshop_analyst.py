"""Tenant-bound GET-only W2-06 analyst contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_analyst_contracts import AnalystAxisReadiness, AnalystBlocker, AnalystCountLedger, AnalystPageInfo, AnalystReadinessAxis, AnalystViewId, AnalystViewSlice, WorkshopAnalystViewEnvelope
from aos_api.ecommerce_workshop_analyst_reader import AnalystCanonicalReader, AnalystReadError, validate_observation
from aos_api.tenant_scope import TenantScope

Clock = Callable[[], datetime]


class EcommerceWorkshopAnalyst:
    """Expose current authority gaps without inventing business metrics."""

    def __init__(self, *, reader: AnalystCanonicalReader | None = None, clock: Clock | None = None) -> None:
        self._reader = reader
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopAnalystViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("analyst clock must be timezone-aware")
        revision = 1
        scope = TenantScope(org_id=org_id, project_id=project_id)
        views: list[AnalystViewSlice] = []
        for view_id in AnalystViewId:
            blocker = AnalystBlocker(code=f"ANALYST_{view_id.value.upper()}_AUTHORITY_NOT_AVAILABLE", dependency=f"workshop.analyst.{view_id.value}-authority", required_action="provide tenant-bound exact metric, quality, evidence and plan refs at one cutoff")
            observation = None
            try:
                observation = self._reader.read_view(scope, view_id=view_id, cutoff=cutoff, limit=100) if self._reader is not None else None
                if observation is not None:
                    validate_observation(observation, scope=scope, cutoff=cutoff)
            except (AnalystReadError, ValueError, TypeError):
                observation = None
            axes = list(observation.readiness_axes) if observation is not None else [AnalystAxisReadiness(axis=axis, status="blocked", blockers=[blocker]) for axis in AnalystReadinessAxis]
            metrics = list(observation.metrics) if observation is not None else []
            refs = list(observation.authority_refs) if observation is not None else []
            trusted = observation is not None and all(axis.status in {"ready", "not_applicable"} for axis in axes) and all(metric.status == "ready" for metric in metrics)
            counts = {status: sum(item.status == status for item in metrics) for status in ("ready", "unknown", "blocked", "conflict")}
            if trusted:
                revision = max(revision, observation.resource_revision)
            views.append(AnalystViewSlice(view_id=view_id, status="ready" if trusted else "blocked", resource_revision=observation.resource_revision if trusted else revision, data_cutoff=cutoff, readiness_axes=axes, metrics=metrics, authority_refs=refs, blockers=[] if trusted else [blocker], count_ledger=AnalystCountLedger(denominator=len(metrics), **counts)))
        trusted_revisions = {item.resource_revision for item in views if item.status == "ready"}
        if len(trusted_revisions) > 1:
            conflict = AnalystBlocker(code="ANALYST_SHARED_RESOURCE_REVISION_CONFLICT", dependency="workshop.analyst.resource-revision", required_action="re-read all seven canonical views at one exact resource revision and cutoff")
            blocked_views = [AnalystViewSlice(view_id=item.view_id, status="blocked", resource_revision=1, data_cutoff=cutoff, readiness_axes=[AnalystAxisReadiness(axis=axis, status="blocked", blockers=[conflict]) for axis in AnalystReadinessAxis], metrics=[], authority_refs=[], blockers=[conflict], count_ledger=AnalystCountLedger(denominator=0, ready=0, unknown=0, blocked=0, conflict=0)) for item in views]
            return WorkshopAnalystViewEnvelope(tenant=TenantContext(org_id=org_id, project_id=project_id), resource_revision=1, evaluated_at=cutoff, data_cutoff=cutoff, views=blocked_views, page=AnalystPageInfo(count=0))
        final_revision = max(item.resource_revision for item in views)
        normalized = [item.model_copy(update={"resource_revision": final_revision}) for item in views]
        return WorkshopAnalystViewEnvelope(tenant=TenantContext(org_id=org_id, project_id=project_id), resource_revision=final_revision, evaluated_at=cutoff, data_cutoff=cutoff, views=normalized, page=AnalystPageInfo(count=sum(len(item.metrics) for item in normalized)))


__all__ = ["EcommerceWorkshopAnalyst"]
