"""Bounded canonical-reader composition boundary for W2 analyst views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from aos_api.ecommerce_workshop_analyst_contracts import AnalystAxisReadiness, AnalystExactRef, AnalystMetricValue, AnalystViewId
from aos_api.tenant_scope import TenantScope


class AnalystReadError(RuntimeError):
    """A canonical dependency could not produce a trustworthy bounded view."""


@dataclass(frozen=True, slots=True)
class AnalystViewObservation:
    scope: TenantScope
    resource_revision: int
    data_cutoff: datetime
    readiness_axes: tuple[AnalystAxisReadiness, ...]
    metrics: tuple[AnalystMetricValue, ...] = ()
    authority_refs: tuple[AnalystExactRef, ...] = ()


class AnalystCanonicalReader(Protocol):
    def read_view(self, scope: TenantScope, *, view_id: AnalystViewId, cutoff: datetime, limit: int) -> AnalystViewObservation: ...


def validate_observation(observation: AnalystViewObservation, *, scope: TenantScope, cutoff: datetime) -> None:
    if observation.scope != scope or observation.data_cutoff != cutoff or observation.resource_revision < 1:
        raise AnalystReadError("analyst canonical reader tenant/revision/cutoff drift")
    if len(observation.readiness_axes) != 5 or len(observation.metrics) > 100 or len(observation.authority_refs) > 100:
        raise AnalystReadError("analyst canonical reader bound drift")
    metric_ids = [item.metric_id for item in observation.metrics]
    if len(metric_ids) != len(set(metric_ids)):
        raise AnalystReadError("analyst canonical reader duplicate metrics")
    identities = [(item.resource_type, item.resource_id, item.revision, item.content_hash, item.receipt_id) for item in observation.authority_refs]
    if len(identities) != len(set(identities)):
        raise AnalystReadError("analyst canonical reader duplicate exact refs")


__all__ = ["AnalystCanonicalReader", "AnalystReadError", "AnalystViewObservation", "validate_observation"]
