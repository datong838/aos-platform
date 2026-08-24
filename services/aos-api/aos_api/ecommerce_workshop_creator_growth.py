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
from aos_api.ecommerce_workshop_creator_growth_store import (
    CreatorAuthorityReadError,
    EcommerceWorkshopCreatorGrowthStore,
)
from aos_api.tenant_scope import TenantScope


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

    def __init__(self, *, store: EcommerceWorkshopCreatorGrowthStore | None = None, clock: Clock | None = None) -> None:
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopCreatorGrowthViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("creator-growth clock must be timezone-aware")
        scope = TenantScope(org_id=org_id, project_id=project_id)
        readers = {
            CreatorBusinessStage.CANDIDATE: "list_candidates",
            CreatorBusinessStage.OUTREACH: "list_outreach_batches",
            CreatorBusinessStage.CONTRACT: "list_contracts",
            CreatorBusinessStage.DELIVERY: "list_deliveries",
            CreatorBusinessStage.RELATIONSHIP: "list_relationships",
        }
        slices = []
        for stage in CreatorBusinessStage:
            dependency, code = _DEPENDENCIES[stage]
            try:
                observations = (
                    getattr(self._store, readers[stage])(scope, cutoff=cutoff, limit=100)
                    if self._store is not None
                    else None
                )
            except CreatorAuthorityReadError:
                observations = None
            if observations is not None:
                refs = []
                for observation in observations:
                    authority = observation.authority
                    identity = next(
                        value
                        for value in (
                            getattr(authority, "candidate_id", None),
                            getattr(authority, "batch_id", None),
                            getattr(authority, "contract_id", None),
                            getattr(authority, "delivery_id", None),
                            getattr(authority, "relationship_id", None),
                        )
                        if value is not None
                    )
                    refs.append(
                        {
                            "resourceType": type(authority).__name__,
                            "resourceId": identity,
                            "revision": authority.revision,
                            "contentHash": f"sha256:{authority.content_hash}",
                            "receiptId": observation.receipt_id,
                            "workflowPhase": "matching" if stage is CreatorBusinessStage.CANDIDATE else "evidence",
                            "businessStage": stage,
                            "piiRefs": getattr(authority, "pii_refs", []),
                        }
                    )
                slices.append(
                    CreatorGrowthSlice(
                        business_stage=stage,
                        workflow_phases=list(CreatorWorkflowPhase),
                        status=CreatorGrowthSliceStatus.READY,
                        data_cutoff=cutoff,
                        authority_refs=refs,
                        blockers=[],
                        count_ledger=CreatorGrowthCountLedger(
                            input=len(refs), eligible=len(refs), excluded=0,
                            needs_review=0, unknown=0, deduplicated=0,
                        ),
                    )
                )
                continue
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
            page=CreatorGrowthPageInfo(
                count=sum(len(item.authority_refs) for item in slices)
            ),
        )


__all__ = ["EcommerceWorkshopCreatorGrowth"]
