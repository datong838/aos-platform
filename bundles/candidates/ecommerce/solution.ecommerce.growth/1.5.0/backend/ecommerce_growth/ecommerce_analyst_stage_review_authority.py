"""Pure stage-review slot matching; plan, member, and Receipt authority stay host-owned."""

from __future__ import annotations

from .ecommerce_analyst_stage_decision import AssigneeRef


_STAGES = frozenset({"portrait", "diagnosis", "solution-design"})


def require_stage_review_slot(
    *,
    stage: str,
    actor: str,
    slot_id: str,
    responsibility_type: str,
    required_capability_ids: list[str],
    return_stage: str,
    assignee: AssigneeRef,
    assignee_resolution_receipt_id: str,
) -> AssigneeRef:
    """Match one slot from a host-verified current ResponsibilityPlan."""

    if (
        type(stage) is not str
        or stage not in _STAGES
        or type(actor) is not str
        or not actor
        or actor.strip() != actor
    ):
        raise ValueError("exact stage reviewer identity required")
    if not isinstance(assignee, AssigneeRef) or type(assignee.version) is not int:
        raise ValueError("actor does not hold the human stage review responsibility")
    assignee = AssigneeRef.model_validate(assignee.model_dump(mode="python"))
    if (
        type(slot_id) is not str
        or slot_id != f"analyst.{stage}.review"
        or type(responsibility_type) is not str
        or responsibility_type != "independent_review"
        or type(required_capability_ids) is not list
        or required_capability_ids
        or type(return_stage) is not str
        or return_stage != stage
        or assignee.kind != "human_principal"
        or type(assignee.version) is not int
        or assignee.version != 1
        or assignee.resource_id != actor
        or type(assignee_resolution_receipt_id) is not str
        or not assignee_resolution_receipt_id
        or assignee_resolution_receipt_id.strip() != assignee_resolution_receipt_id
        or len(assignee_resolution_receipt_id) > 240
    ):
        raise ValueError("actor does not hold the human stage review responsibility")
    return assignee


__all__ = ["require_stage_review_slot"]
