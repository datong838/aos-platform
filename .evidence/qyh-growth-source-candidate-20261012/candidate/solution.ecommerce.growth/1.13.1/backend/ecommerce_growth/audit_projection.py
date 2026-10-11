"""Separate readable business feedback from expandable technical audit data."""

from __future__ import annotations

from typing import Any

from .ecommerce_business_investigation_review_command import exact_ref_payload
from .result_feedback import ResultFeedbackPlan


_STATUS_LABELS = {
    "daily_review": "等待效果观察",
    "improvement_observation": "证据积累中",
    "memory_candidate": "等待经验治理",
    "content_return_target": "等待重新调整",
}


def business_feedback_projection(plan: ResultFeedbackPlan) -> dict[str, Any]:
    return {
        "title": "业务结果回流",
        "decisionLabel": "评审通过" if plan.decision == "ACCEPT" else "退回调整",
        "items": [
            {
                "title": segment.business_title,
                "summary": segment.business_summary,
                "statusLabel": _STATUS_LABELS[segment.kind],
            }
            for segment in plan.segments
        ],
    }


def audit_feedback_projection(plan: ResultFeedbackPlan) -> dict[str, Any]:
    return {
        "auditDetails": {
            "commandId": plan.command_id,
            "requestHash": f"sha256:{plan.command_hash}",
            "reviewReceiptRef": exact_ref_payload(plan.review_receipt_ref),
            "artifactRef": exact_ref_payload(plan.artifact_ref),
            "taskRef": exact_ref_payload(plan.task_ref),
            "briefRef": exact_ref_payload(plan.brief_ref),
            "targets": [
                {
                    "sequence": segment.sequence,
                    "kind": segment.kind,
                    "targetId": segment.target_id,
                    "targetPhase": segment.target_phase,
                }
                for segment in plan.segments
            ],
        }
    }


__all__ = ["audit_feedback_projection", "business_feedback_projection"]
