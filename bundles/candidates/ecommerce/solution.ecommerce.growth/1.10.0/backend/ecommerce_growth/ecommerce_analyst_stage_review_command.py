"""Pure stage-review command identity; all current authority remains host-owned."""

from __future__ import annotations

import hashlib
import json

from .ecommerce_analyst_authority_contracts import TenantContext
from .ecommerce_analyst_stage_decision import AnalystStageDecisionRevision


_FIELDS = (
    "task_run_id",
    "plan_ref",
    "stage",
    "stage_attempt_ref",
    "subject_ref",
    "artifact_ref",
    "eval_report_ref",
)


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def stage_decision_id(item: AnalystStageDecisionRevision) -> str:
    """Derive the stable identity for one exact stage target."""

    if not isinstance(item, AnalystStageDecisionRevision):
        raise TypeError("stage decision value required")
    item = AnalystStageDecisionRevision.model_validate(item.model_dump(mode="python"))
    body = item.model_dump(mode="json", by_alias=False)
    return "stage-review-" + _canonical_hash(
        {"tenant": body["tenant"], **{key: body[key] for key in _FIELDS}}
    )


def require_stage_review_command_identity(
    *,
    tenant: TenantContext,
    item: AnalystStageDecisionRevision,
    actor: str,
    key: str,
    expected_version: int,
) -> AnalystStageDecisionRevision:
    """Validate a proposal before host authority and persistence checks."""

    if (
        not isinstance(tenant, TenantContext)
        or not isinstance(item, AnalystStageDecisionRevision)
        or type(actor) is not str
        or not actor
        or actor.strip() != actor
        or type(key) is not str
        or not key
        or key.strip() != key
        or len(key) > 200
        or type(expected_version) is not int
        or expected_version < 0
    ):
        raise ValueError("stage decision command identity drifted")
    tenant = TenantContext.model_validate(tenant.model_dump(mode="python"))
    item = AnalystStageDecisionRevision.model_validate(item.model_dump(mode="python"))
    if (
        item.created_by != actor
        or item.tenant != tenant
        or item.decision_id != stage_decision_id(item)
        or _canonical_hash(
            item.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
        )
        != item.content_hash
    ):
        raise ValueError("stage decision command identity drifted")
    return item


__all__ = ["require_stage_review_command_identity", "stage_decision_id"]
