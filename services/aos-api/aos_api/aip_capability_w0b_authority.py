"""Pure checks for closing capability definition EvalPack and W0B blockers."""

from __future__ import annotations

from typing import Any


REQUIRED_RELATIONS = frozenset(
    {
        "aip_task_brief_head",
        "aip_task_brief_revision",
        "aip_evidence_bundle_revision",
        "aip_eval_contract_head",
        "aip_eval_contract_revision",
        "aip_responsibility_plan_head",
        "aip_responsibility_plan_revision",
        "aip_stage_template_head",
        "aip_stage_template_revision",
        "aip_artifact_relation",
        "aip_review_issue",
        "aip_review_issue_event",
        "aip_return_decision",
        "aip_impact_preview_head",
        "aip_impact_preview_revision",
    }
)

REQUIRED_STORE_METHODS = frozenset(
    {
        "create_brief",
        "freeze_brief",
        "get_brief",
        "build_evidence_bundle",
        "get_evidence_bundle",
        "create_eval_contract",
        "freeze_eval_contract",
        "get_eval_contract",
        "create_responsibility_plan",
        "freeze_responsibility_plan",
        "get_responsibility_plan",
        "create_stage_template",
        "freeze_stage_template",
        "get_stage_template",
        "create_artifact_relation",
        "get_artifact_relation",
        "create_review_issue",
        "get_review_issue",
        "get_return_decision",
        "create_impact_preview",
        "freeze_impact_preview",
        "get_impact_preview",
    }
)


def evaluate_w0b_relations(rows: list[dict[str, Any]]) -> list[str]:
    by_name = {str(row["relation"]): row for row in rows}
    blockers: list[str] = []
    for relation in sorted(REQUIRED_RELATIONS):
        row = by_name.get(relation)
        if row is None:
            blockers.append(f"missing_relation:{relation}")
            continue
        if int(row.get("tenant_key_columns", 0)) != 2:
            blockers.append(f"tenant_key_missing:{relation}")
        if not bool(row.get("rls")):
            blockers.append(f"rls_missing:{relation}")
        if not bool(row.get("force_rls")):
            blockers.append(f"force_rls_missing:{relation}")
        if int(row.get("policy_count", 0)) < 1:
            blockers.append(f"policy_missing:{relation}")
    return blockers


def close_definition_reasons(
    reasons: list[str], *, eval_pack_ready: bool, w0b_ready: bool
) -> list[str]:
    removable = set()
    if eval_pack_ready:
        removable.add("eval_pack_unavailable")
    if w0b_ready:
        removable.add("w0b_contracts_unavailable")
    return [reason for reason in reasons if reason not in removable]


__all__ = [
    "REQUIRED_RELATIONS",
    "REQUIRED_STORE_METHODS",
    "close_definition_reasons",
    "evaluate_w0b_relations",
]
