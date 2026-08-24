"""Tenant-bound GET-only W2-05 media-studio contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_media_studio_contracts import (
    MediaAxisReadiness,
    MediaBlocker,
    MediaCountLedger,
    MediaPageInfo,
    MediaReadinessAxis,
    MediaReadinessStatus,
    MediaStudioSlice,
    MediaStudioSliceId,
    WorkshopMediaStudioViewEnvelope,
)
from aos_api.ecommerce_workshop_media_studio_reader import (
    MediaStudioCanonicalReader,
    MediaStudioReadError,
    validate_observation,
)
from aos_api.tenant_scope import TenantScope


Clock = Callable[[], datetime]


class EcommerceWorkshopMediaStudio:
    """Describe current authority gaps without promoting target state."""

    def __init__(self, *, reader: MediaStudioCanonicalReader | None = None, clock: Clock | None = None) -> None:
        self._reader = reader
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopMediaStudioViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("media-studio clock must be timezone-aware")
        scope = TenantScope(org_id=org_id, project_id=project_id)
        methods = {
            MediaStudioSliceId.CONTEXT: "read_context",
            MediaStudioSliceId.EXECUTION: "read_execution",
            MediaStudioSliceId.DELIVERY: "read_delivery",
        }
        slices: list[MediaStudioSlice] = []
        for slice_id in MediaStudioSliceId:
            blockers = [
                MediaBlocker(
                    code=f"MEDIA_{slice_id.value.upper()}_AUTHORITY_NOT_AVAILABLE",
                    dependency=f"workshop.media-studio.{slice_id.value}-authority",
                    required_action="provide tenant-bound exact refs and Receipts at one cutoff",
                )
            ]
            target_axes = [
                MediaAxisReadiness(
                    axis=axis,
                    status=MediaReadinessStatus.TARGET,
                    target_contract_ref=f"ADR-86#{slice_id.value}-{axis.value}",
                    gaps=[f"canonical {axis.value} authority is not attached"],
                    blockers=blockers,
                )
                for axis in MediaReadinessAxis
            ]
            try:
                observation = (
                    getattr(self._reader, methods[slice_id])(scope, cutoff=cutoff, limit=100)
                    if self._reader is not None
                    else None
                )
                if observation is not None:
                    validate_observation(observation, scope=scope, cutoff=cutoff)
            except (MediaStudioReadError, ValueError, TypeError):
                observation = None
            axes = list(observation.readiness_axes) if observation is not None else target_axes
            refs = list(observation.authority_refs) if observation is not None else []
            status_counts = {status: sum(item.status is status for item in axes) for status in MediaReadinessStatus}
            slice_blockers = [] if observation is not None and all(item.status in {MediaReadinessStatus.READY, MediaReadinessStatus.NOT_APPLICABLE} for item in axes) else blockers
            slices.append(
                MediaStudioSlice(
                    slice_id=slice_id,
                    status="ready" if not slice_blockers else "blocked",
                    data_cutoff=cutoff,
                    readiness_axes=axes,
                    authority_refs=refs,
                    blockers=slice_blockers,
                    count_ledger=MediaCountLedger(
                        denominator=6,
                        ready=status_counts[MediaReadinessStatus.READY],
                        target=status_counts[MediaReadinessStatus.TARGET],
                        blocked=status_counts[MediaReadinessStatus.BLOCKED],
                        unknown=status_counts[MediaReadinessStatus.UNKNOWN],
                        conflict=status_counts[MediaReadinessStatus.CONFLICT],
                        not_applicable=status_counts[MediaReadinessStatus.NOT_APPLICABLE],
                    ),
                )
            )
        return WorkshopMediaStudioViewEnvelope(
            tenant=TenantContext(org_id=org_id, project_id=project_id),
            evaluated_at=cutoff,
            data_cutoff=cutoff,
            slices=slices,
            page=MediaPageInfo(count=sum(len(item.authority_refs) for item in slices)),
        )


__all__ = ["EcommerceWorkshopMediaStudio"]
