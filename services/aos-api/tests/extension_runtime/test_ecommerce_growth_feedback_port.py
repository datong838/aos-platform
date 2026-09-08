from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort,
    EcommerceGrowthFeedbackConflict,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


def exact(kind: str, identity: str) -> dict[str, object]:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": "sha256:" + "a" * 64,
        "receiptId": f"receipt-{identity}",
    }


def plan(decision: str = "ACCEPT") -> dict[str, object]:
    kinds = (
        ("daily_review", "improvement_observation", "memory_candidate")
        if decision == "ACCEPT"
        else ("content_return_target",)
    )
    return {
        "commandId": "feedback-command-1",
        "requestHash": "sha256:" + "b" * 64,
        "decision": decision,
        "reviewReceiptRef": exact("ContentReviewReceipt", "review-1"),
        "artifactRef": exact("ArtifactRevision", "artifact-1"),
        "taskRef": exact("Task", "task-1"),
        "briefRef": exact("TaskBriefRevision", "brief-1"),
        "segments": [
            {
                "sequence": index,
                "kind": kind,
                "targetId": f"{kind}-1",
                "businessTitle": "今日内容复盘" if index == 1 else "内容结果持续改进",
                "businessSummary": "内容已通过评审，等待后续业务效果观察。",
                "targetPhase": "content_generation" if kind == "content_return_target" else None,
            }
            for index, kind in enumerate(kinds, start=1)
        ],
        "sideEffects": {
            "providerInvocationCount": 0,
            "externalPublicationCount": 0,
            "externalBusinessMutationCount": 0,
            "taskCreatedCount": 0,
            "budgetSettlementCount": 0,
        },
    }


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))
        return Cursor(self.rows.pop(0) if self.rows else None)


def port(rows):
    connection = Connection(rows)
    readers = {
        kind: (lambda **kwargs: kwargs["expected_receipt"])
        for kind in ("daily_review", "improvement_observation", "memory_candidate", "content_return_target")
    }
    return (
        BoundEcommerceGrowthFeedbackPort(
            HostTransaction(connection),
            TenantScope("org-org", "dev-project"),
            actor="数字同事",
            checked_at=datetime(2026, 9, 8, 12, tzinfo=timezone.utc),
            target_receipt_readers=readers,
        ),
        connection,
    )


def test_enqueue_is_strict_receipt_first_and_has_no_authority_override() -> None:
    item, connection = port(
        [{"command_id": "feedback-command-1", "request_hash": "sha256:" + "b" * 64,
          "segment_count": 3, "replayed": False}]
    )
    result = item.enqueue(
        review_receipt={"receiptRef": exact("ContentReviewReceipt", "review-1")},
        feedback_plan=plan(),
    )
    assert result == {
        "commandId": "feedback-command-1",
        "requestHash": "sha256:" + "b" * 64,
        "segmentCount": 3,
        "replayed": False,
    }
    assert "feedback_enqueue_ar2_004" in connection.calls[0][0]
    assert "org-org" not in connection.calls[0][1] and "dev-project" not in connection.calls[0][1]


def test_enqueue_rejects_review_lineage_segment_and_effect_drift() -> None:
    item, _ = port([])
    with pytest.raises(ValueError, match="lineage drifted"):
        item.enqueue(review_receipt={"receiptRef": exact("ContentReviewReceipt", "other")}, feedback_plan=plan())
    drift = plan()
    drift["segments"] = list(reversed(drift["segments"]))
    with pytest.raises(ValueError, match="segment set or order"):
        item.enqueue(review_receipt={"receiptRef": exact("ContentReviewReceipt", "review-1")}, feedback_plan=drift)
    drift = plan()
    drift["sideEffects"]["taskCreatedCount"] = 1
    with pytest.raises(ValueError, match="side-effect boundary"):
        item.enqueue(review_receipt={"receiptRef": exact("ContentReviewReceipt", "review-1")}, feedback_plan=drift)


def test_claim_unknown_and_reconcile_preserve_one_target_and_checkpoint() -> None:
    token = uuid4()
    claim_row = {
        "sequence": 1,
        "kind": "daily_review",
        "target_id": "daily_review-1",
        "payload": {"businessTitle": "今日内容复盘"},
        "attempt": 1,
        "lease_token": token,
        "checkpoint_version": 1,
    }
    item, connection = port([claim_row, None, {
        "completed_sequence": 1, "checkpoint_version": 2, "receipt_ref": None,
    }])
    claim = item.claim(command_id="feedback-command-1", worker="feedback-worker")
    assert claim["targetId"] == "daily_review-1"
    item.mark_unknown(command_id="feedback-command-1", claim=claim, reason_code="target_outcome_unknown")
    target = exact("EffectReviewReceipt", "effect-1")
    checkpoint = item.reconcile(
        command_id="feedback-command-1",
        claim=claim,
        target_receipt_ref=target,
    )
    assert checkpoint == {"completedSequence": 1, "checkpointVersion": 2, "receiptRef": None}
    assert "feedback_unknown_ar2_004" in connection.calls[1][0]
    assert "feedback_ack_ar2_004" in connection.calls[2][0]


def test_checkpoint_cannot_advance_when_target_readback_differs() -> None:
    connection = Connection([])
    readers = {
        kind: (lambda **kwargs: exact("EffectReviewReceipt", "effect-2"))
        for kind in ("daily_review", "improvement_observation", "memory_candidate", "content_return_target")
    }
    item = BoundEcommerceGrowthFeedbackPort(
        HostTransaction(connection), TenantScope("org-org", "dev-project"), actor="数字同事",
        checked_at=datetime(2026, 9, 8, 12, tzinfo=timezone.utc), target_receipt_readers=readers,
    )
    claim = {
        "sequence": 1, "checkpointVersion": 1, "leaseToken": str(uuid4()),
        "kind": "daily_review", "targetId": "daily_review-1",
    }
    with pytest.raises(EcommerceGrowthFeedbackConflict, match="readback drifted"):
        item.acknowledge(
            command_id="feedback-command-1",
            claim=claim,
            target_receipt_ref=exact("EffectReviewReceipt", "effect-1"),
        )
    assert connection.calls == []
