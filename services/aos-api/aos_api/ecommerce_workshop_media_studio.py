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


Clock = Callable[[], datetime]


class EcommerceWorkshopMediaStudio:
    """Describe current authority gaps without promoting target state."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopMediaStudioViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("media-studio clock must be timezone-aware")
        slices: list[MediaStudioSlice] = []
        for slice_id in MediaStudioSliceId:
            blockers = [
                MediaBlocker(
                    code=f"MEDIA_{slice_id.value.upper()}_AUTHORITY_NOT_AVAILABLE",
                    dependency=f"workshop.media-studio.{slice_id.value}-authority",
                    required_action="provide tenant-bound exact refs and Receipts at one cutoff",
                )
            ]
            axes = [
                MediaAxisReadiness(
                    axis=axis,
                    status=MediaReadinessStatus.TARGET,
                    target_contract_ref=f"ADR-86#{slice_id.value}-{axis.value}",
                    gaps=[f"canonical {axis.value} authority is not attached"],
                    blockers=blockers,
                )
                for axis in MediaReadinessAxis
            ]
            slices.append(
                MediaStudioSlice(
                    slice_id=slice_id,
                    status="blocked",
                    data_cutoff=cutoff,
                    readiness_axes=axes,
                    blockers=blockers,
                    count_ledger=MediaCountLedger(
                        denominator=6,
                        ready=0,
                        target=6,
                        blocked=0,
                        unknown=0,
                        conflict=0,
                        not_applicable=0,
                    ),
                )
            )
        return WorkshopMediaStudioViewEnvelope(
            tenant=TenantContext(org_id=org_id, project_id=project_id),
            evaluated_at=cutoff,
            data_cutoff=cutoff,
            slices=slices,
            page=MediaPageInfo(count=0),
        )


__all__ = ["EcommerceWorkshopMediaStudio"]
