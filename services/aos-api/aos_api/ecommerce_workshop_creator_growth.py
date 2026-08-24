"""Tenant-bound, GET-only W2-04A creator-growth shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_creator_growth_contracts import (
    CreatorBusinessStage,
    CreatorGrowthBlocker,
    CreatorGrowthCountLedger,
    CreatorGrowthPageInfo,
    CreatorGrowthSlice,
    CreatorGrowthSliceStatus,
    CreatorWorkflowPhase,
    WorkshopCreatorGrowthViewEnvelope,
)


Clock = Callable[[], datetime]
_DEPENDENCIES = {
    stage: (
        f"workshop.creator-growth.{stage.value}-authority",
        f"CANONICAL_CREATOR_{stage.value.upper()}_AUTHORITY_NOT_AVAILABLE",
    )
    for stage in CreatorBusinessStage
}


class EcommerceWorkshopCreatorGrowth:
    """Expose the five honest authority gaps without inventing creator facts."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopCreatorGrowthViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("creator-growth clock must be timezone-aware")
        slices = []
        for stage in CreatorBusinessStage:
            dependency, code = _DEPENDENCIES[stage]
            slices.append(
                CreatorGrowthSlice(
                    business_stage=stage,
                    workflow_phases=list(CreatorWorkflowPhase),
                    status=CreatorGrowthSliceStatus.BLOCKED,
                    data_cutoff=cutoff,
                    authority_refs=[],
                    blockers=[
                        CreatorGrowthBlocker(
                            code=code,
                            dependency=dependency,
                            required_action=(
                                "provide tenant-bound canonical authority refs and exact "
                                "Receipts at the same cutoff"
                            ),
                        )
                    ],
                    count_ledger=CreatorGrowthCountLedger(
                        input=0,
                        eligible=0,
                        excluded=0,
                        needs_review=0,
                        unknown=0,
                        deduplicated=0,
                    ),
                )
            )
        return WorkshopCreatorGrowthViewEnvelope(
            tenant=TenantContext(org_id=org_id, project_id=project_id),
            evaluated_at=cutoff,
            data_cutoff=cutoff,
            slices=slices,
            page=CreatorGrowthPageInfo(count=0),
        )


__all__ = ["EcommerceWorkshopCreatorGrowth"]
