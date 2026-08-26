"""BI-W8-05 fail-closed human approval for canonical GrowthPlan revisions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_analyst_authority_contracts import (
    AnalystExactRef,
    GrowthPlanLifecycle,
    GrowthPlanRevision,
)
from aos_api.ecommerce_analyst_authority_store import (
    AnalystAuthorityIdempotencyConflict,
    EcommerceAnalystAuthorityStore,
    canonical_hash,
)
from aos_api.tenant_scope import TenantScope


class GrowthPlanApprovalBlocked(RuntimeError):
    code = "ECOMMERCE_GROWTH_PLAN_APPROVAL_BLOCKED"


class ApproveGrowthPlanRequest(AipContractModel):
    draft_ref: AnalystExactRef

    @model_validator(mode="after")
    def _draft_type(self) -> "ApproveGrowthPlanRequest":
        if self.draft_ref.resource_type != "GrowthPlanRevision":
            raise ValueError("draftRef must be an exact GrowthPlanRevision")
        return self


class GrowthPlanApprovalResponse(AipContractModel):
    tenant: TenantContext
    draft_ref: AnalystExactRef
    approved_ref: AnalystExactRef
    lifecycle: Literal["approved"] = "approved"
    replayed: bool
    external_effects_allowed: Literal[False] = False


class EcommerceAnalystGrowthPlanApprovalService:
    def __init__(
        self,
        store: EcommerceAnalystAuthorityStore | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store or EcommerceAnalystAuthorityStore()
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _receipt_key(idempotency_key: str) -> str:
        return f"bi-growth-plan-approve:{canonical_hash(idempotency_key)}"

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    def _replay(
        self,
        scope: TenantScope,
        draft_ref: AnalystExactRef,
        receipt_key: str,
        actor: str,
    ) -> GrowthPlanApprovalResponse | None:
        approved_ref = self._store.find_plan_publication_receipt(scope, receipt_key)
        if approved_ref is None:
            return None
        approved = self._store.get_plan_exact(scope, approved_ref)
        if (
            approved.lifecycle is not GrowthPlanLifecycle.APPROVED
            or approved.prior_ref != draft_ref
            or approved.created_by != actor
        ):
            raise GrowthPlanApprovalBlocked(
                "idempotency key is already bound to a different approval command"
            )
        return GrowthPlanApprovalResponse(
            tenant=self._tenant(scope),
            draftRef=draft_ref,
            approvedRef=approved_ref,
            replayed=True,
        )

    def approve(
        self,
        scope: TenantScope,
        plan_id: str,
        request: ApproveGrowthPlanRequest,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
    ) -> GrowthPlanApprovalResponse:
        draft_ref = request.draft_ref
        if draft_ref.resource_id != plan_id:
            raise ValueError("draftRef resourceId must match the GrowthPlan path")
        receipt_key = self._receipt_key(idempotency_key)
        replay = self._replay(scope, draft_ref, receipt_key, actor)
        if replay is not None:
            return replay

        draft = self._store.get_plan_exact(scope, draft_ref)
        if draft.plan_id != plan_id or draft.version != expected_version:
            raise GrowthPlanApprovalBlocked("draft exact ref or If-Match version is stale")
        if draft.lifecycle is not GrowthPlanLifecycle.DRAFT:
            raise GrowthPlanApprovalBlocked("only a DRAFT GrowthPlanRevision may be approved")
        if not self._store.is_current_plan(scope, draft_ref):
            raise GrowthPlanApprovalBlocked("draft is not the current GrowthPlan authority")

        approved_at = self._clock()
        if approved_at.utcoffset() is None:
            raise GrowthPlanApprovalBlocked("approval clock must include a timezone")
        payload = draft.model_dump(mode="json", by_alias=True)
        payload.update(
            revision=draft.revision + 1,
            version=draft.version + 1,
            priorRef=draft_ref.model_dump(mode="json", by_alias=True),
            lifecycle=GrowthPlanLifecycle.APPROVED.value,
            approvedAt=approved_at.isoformat(),
            createdBy=actor,
            createdAt=approved_at.isoformat(),
            contentHash="0" * 64,
        )
        validated = GrowthPlanRevision.model_validate(payload)
        canonical = validated.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
        payload["contentHash"] = canonical_hash(canonical)
        approved = GrowthPlanRevision.model_validate(payload)
        try:
            approved_ref = self._store.publish_plan(
                scope,
                actor,
                receipt_key,
                approved,
                expected_version=expected_version,
            )
        except AnalystAuthorityIdempotencyConflict:
            replay = self._replay(scope, draft_ref, receipt_key, actor)
            if replay is not None:
                return replay
            raise
        return GrowthPlanApprovalResponse(
            tenant=self._tenant(scope),
            draftRef=draft_ref,
            approvedRef=approved_ref,
            replayed=False,
        )
