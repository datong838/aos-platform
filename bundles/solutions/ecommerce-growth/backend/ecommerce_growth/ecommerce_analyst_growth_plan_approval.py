"""Pure GrowthPlan approval transition; persistence and authority stay with the host."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json

from .ecommerce_analyst_authority_contracts import (
    AnalystExactRef,
    GrowthPlanLifecycle,
    GrowthPlanRevision,
)


class GrowthPlanApprovalBlocked(RuntimeError):
    code = "ECOMMERCE_GROWTH_PLAN_APPROVAL_BLOCKED"


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def approve_growth_plan_successor(
    *,
    draft: GrowthPlanRevision,
    draft_ref: AnalystExactRef,
    plan_id: str,
    expected_version: int,
    is_current: bool,
    actor: str,
    approved_at: datetime,
) -> GrowthPlanRevision:
    """Create an adjacent approved revision from host-verified immutable inputs."""

    draft = GrowthPlanRevision.model_validate(draft.model_dump(mode="python"))
    draft_ref = AnalystExactRef.model_validate(draft_ref.model_dump(mode="python"))
    if type(plan_id) is not str or not plan_id.strip() or plan_id.strip() != plan_id:
        raise ValueError("canonical GrowthPlan path identity is required")
    if draft_ref.resource_type != "GrowthPlanRevision" or draft_ref.resource_id != plan_id:
        raise ValueError("draftRef must match the exact GrowthPlan path")
    if (
        draft.plan_id != plan_id
        or draft.revision != draft_ref.revision
        or draft.content_hash != draft_ref.content_hash
    ):
        raise GrowthPlanApprovalBlocked("draft exact reference is stale")
    if type(expected_version) is not int or draft.version != expected_version:
        raise GrowthPlanApprovalBlocked("draft If-Match version is stale")
    if type(is_current) is not bool or not is_current:
        raise GrowthPlanApprovalBlocked("draft is not the current GrowthPlan authority")
    if draft.lifecycle is not GrowthPlanLifecycle.DRAFT:
        raise GrowthPlanApprovalBlocked("only a DRAFT GrowthPlanRevision may be approved")
    if type(actor) is not str or not actor.strip() or actor.strip() != actor:
        raise GrowthPlanApprovalBlocked("canonical human approval actor is required")
    if not isinstance(approved_at, datetime) or approved_at.utcoffset() is None:
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
    payload["contentHash"] = _canonical_hash(
        validated.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
    )
    return GrowthPlanRevision.model_validate(payload)


__all__ = ["GrowthPlanApprovalBlocked", "approve_growth_plan_successor"]
