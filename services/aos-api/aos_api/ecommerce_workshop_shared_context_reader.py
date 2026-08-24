"""Bounded canonical-reader boundary for W2 shared context reconstruction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from aos_api.ecommerce_workshop_shared_context_contracts import WorkshopNavigationTarget, WorkshopSharedContext, WorkshopTimelineEvent
from aos_api.tenant_scope import TenantScope


class SharedContextReadError(RuntimeError):
    """A canonical shared-context dependency was unavailable or inconsistent."""


@dataclass(frozen=True, slots=True)
class SharedContextObservation:
    scope: TenantScope
    context: WorkshopSharedContext
    timeline: tuple[WorkshopTimelineEvent, ...] = ()
    navigation_targets: tuple[WorkshopNavigationTarget, ...] = ()
    active_routes: tuple[tuple[str, str], ...] = ()


class SharedContextCanonicalReader(Protocol):
    def read_context(self, scope: TenantScope, *, context_id: str, cutoff: datetime, limit: int) -> SharedContextObservation: ...


def _ref_identity(value: object) -> tuple[object, ...]:
    return (value.authority, value.resource_type, value.resource_id, value.revision, value.content_hash)  # type: ignore[attr-defined]


def validate_shared_context_observation(value: SharedContextObservation, *, scope: TenantScope, context_id: str, cutoff: datetime, limit: int = 100) -> None:
    if value.scope != scope or value.context.context_id != context_id:
        raise SharedContextReadError("shared-context tenant or identity drift")
    if limit != 100 or len(value.timeline) > limit or len(value.navigation_targets) > 20:
        raise SharedContextReadError("shared-context bounded read drift")
    context = value.context
    if context.status != "ready" or context.disclosure != "allowed" or context.freshness != "fresh" or context.readiness != "ready":
        raise SharedContextReadError("shared-context is not disclosure-ready")
    if context.evaluated_at > cutoff or context.data_cutoff is None or context.data_cutoff > cutoff or context.expires_at <= cutoff:
        raise SharedContextReadError("shared-context cutoff or expiry drift")
    if not context.permission_decision_ref or not context.disclosure_policy_ref or not context.markings:
        raise SharedContextReadError("shared-context permission or marking authority missing")
    active_modules = [item[0] for item in value.active_routes]
    active_paths = [item[1] for item in value.active_routes]
    if len(active_modules) != len(set(active_modules)) or len(active_paths) != len(set(active_paths)):
        raise SharedContextReadError("shared-context active route identity drift")
    active = dict(value.active_routes)
    if active.get(context.source_module_id or "") != context.source_route:
        raise SharedContextReadError("shared-context source is not an active canonical route")
    primary_identity = _ref_identity(context.primary_ref)
    for target in value.navigation_targets:
        if target.status == "available" and (active.get(target.module_id or "") != target.route or _ref_identity(target.subject_ref) != primary_identity):
            raise SharedContextReadError("shared-context navigation target drift")
    known_refs = [context.primary_ref, context.permission_decision_ref, context.disclosure_policy_ref, *context.related_refs, *context.lineage_refs]
    reachable = {_ref_identity(item) for item in known_refs if item is not None}
    for event in value.timeline:
        refs = [event.source_ref, event.receipt_ref, *event.original_refs]
        if any(_ref_identity(item) not in reachable for item in refs if item is not None):
            raise SharedContextReadError("shared-context timeline contains an unreachable exact ref")


__all__ = ["SharedContextCanonicalReader", "SharedContextObservation", "SharedContextReadError", "validate_shared_context_observation"]
