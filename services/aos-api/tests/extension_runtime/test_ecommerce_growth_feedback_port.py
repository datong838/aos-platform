from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
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


def digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def plan(decision: str = "ACCEPT") -> dict[str, object]:
    kinds = (
        ("daily_review", "improvement_observation", "memory_candidate")
        if decision == "ACCEPT"
        else ("content_return_target",)
    )
    review_ref = exact("ContentReviewReceipt", "review-1")
    segments = [
        {
            "sequence": index,
            "kind": kind,
            "targetId": f"{kind}-1",
            "businessTitle": "今日内容复盘" if index == 1 else "内容结果持续改进",
            "businessSummary": "内容已通过评审，等待后续业务效果观察。",
            "targetPhase": "content_generation" if kind == "content_return_target" else None,
        }
        for index, kind in enumerate(kinds, start=1)
    ]
    command_id = "feedback-" + digest({"reviewReceiptRef": review_ref, "decision": decision})[:40]
    canonical = {
        "decision": decision,
        "reviewReceiptRef": review_ref,
        "artifactRef": exact("ArtifactRevision", "artifact-1"),
        "taskRef": exact("Task", "task-1"),
        "briefRef": exact("TaskBriefRevision", "brief-1"),
        "segments": segments,
    }
    return {
        "commandId": command_id,
        "requestHash": "sha256:" + digest(canonical),
        "decision": decision,
        "reviewReceiptRef": canonical["reviewReceiptRef"],
        "artifactRef": canonical["artifactRef"],
        "taskRef": canonical["taskRef"],
        "briefRef": canonical["briefRef"],
        "segments": segments,
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
    expected = plan()
    item, connection = port(
        [{"command_id": expected["commandId"], "request_hash": expected["requestHash"],
          "segment_count": 3, "replayed": False}]
    )
    result = item.enqueue(
        review_receipt={"receiptRef": exact("ContentReviewReceipt", "review-1")},
        feedback_plan=expected,
    )
    assert result == {
        "commandId": expected["commandId"],
        "requestHash": expected["requestHash"],
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
    reconciliation_row = {**claim_row, "checkpoint_version": 1}
    item, connection = port([claim_row, None, reconciliation_row, {
        "completed_sequence": 1, "checkpoint_version": 2, "receipt_ref": None,
    }])
    command_id = plan()["commandId"]
    claim = item.claim(command_id=command_id, worker="feedback-worker")
    assert claim["targetId"] == "daily_review-1"
    item.mark_unknown(command_id=command_id, claim=claim, reason_code="target_outcome_unknown")
    claim = item.claim_reconciliation(command_id=command_id)
    assert claim["attempt"] == 1
    target = exact("EffectReviewReceipt", "effect-1")
    checkpoint = item.reconcile(
        command_id=command_id,
        claim=claim,
        target_receipt_ref=target,
    )
    assert checkpoint == {"completedSequence": 1, "checkpointVersion": 2, "receiptRef": None}
    assert "feedback_unknown_ar2_004" in connection.calls[1][0]
    assert "feedback_reconcile_claim_ar2_004" in connection.calls[2][0]
    assert "feedback_ack_ar2_004" in connection.calls[3][0]


def test_enqueue_rejects_forged_canonical_hash_and_command_identity() -> None:
    item, connection = port([])
    drift = plan()
    drift["requestHash"] = "sha256:" + "f" * 64
    with pytest.raises(ValueError, match="canonical request hash drifted"):
        item.enqueue(review_receipt={"receiptRef": exact("ContentReviewReceipt", "review-1")}, feedback_plan=drift)
    drift = plan()
    drift["commandId"] = "feedback-" + "f" * 40
    with pytest.raises(ValueError, match="canonical command identity drifted"):
        item.enqueue(review_receipt={"receiptRef": exact("ContentReviewReceipt", "review-1")}, feedback_plan=drift)
    assert connection.calls == []


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
            command_id=plan()["commandId"],
            claim=claim,
            target_receipt_ref=exact("EffectReviewReceipt", "effect-1"),
        )
    assert connection.calls == []
