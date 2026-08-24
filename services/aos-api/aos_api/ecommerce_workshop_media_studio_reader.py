"""Bounded canonical-reader composition boundary for W2 media studio."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from aos_api.ecommerce_workshop_media_studio_contracts import MediaAxisReadiness, MediaExactRef
from aos_api.tenant_scope import TenantScope


class MediaStudioReadError(RuntimeError):
    """A canonical dependency could not produce a trustworthy bounded view."""


@dataclass(frozen=True, slots=True)
class MediaStudioSliceObservation:
    scope: TenantScope
    data_cutoff: datetime
    readiness_axes: tuple[MediaAxisReadiness, ...]
    authority_refs: tuple[MediaExactRef, ...] = ()


class MediaStudioCanonicalReader(Protocol):
    def read_context(self, scope: TenantScope, *, cutoff: datetime, limit: int) -> MediaStudioSliceObservation: ...
    def read_execution(self, scope: TenantScope, *, cutoff: datetime, limit: int) -> MediaStudioSliceObservation: ...
    def read_delivery(self, scope: TenantScope, *, cutoff: datetime, limit: int) -> MediaStudioSliceObservation: ...


def validate_observation(observation: MediaStudioSliceObservation, *, scope: TenantScope, cutoff: datetime) -> None:
    if observation.scope != scope or observation.data_cutoff != cutoff:
        raise MediaStudioReadError("media canonical reader tenant/cutoff drift")
    if len(observation.readiness_axes) != 6 or len(observation.authority_refs) > 100:
        raise MediaStudioReadError("media canonical reader bound drift")
    identities = [(item.resource_type, item.resource_id, item.revision, item.content_hash, item.receipt_id) for item in observation.authority_refs]
    if len(identities) != len(set(identities)):
        raise MediaStudioReadError("media canonical reader duplicate exact refs")


__all__ = ["MediaStudioCanonicalReader", "MediaStudioReadError", "MediaStudioSliceObservation", "validate_observation"]
