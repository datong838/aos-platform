"""A human RETURN can only acknowledge its already durable repair attempt."""

from copy import deepcopy
from contextlib import contextmanager

import pytest

from aos_api.ecommerce_growth_content_return_target import (
    BoundContentReturnTarget, ContentReturnFeedbackWorker, ContentReturnUnknown,
)
from aos_api.aip_budget_reservation_store import canonical_hash as budget_hash
from aos_api.aip_production_contract_store import canonical_hash as decision_hash
from aos_api.ecommerce_growth_feedback_port import EcommerceGrowthFeedbackConflict
from aos_api.ecommerce_growth_feedback_port import BoundEcommerceGrowthFeedbackPort
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import _analysis_command_hash, _request_hash
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def ref(kind, identity, fill):
    return {"resourceType": kind, "resourceId": identity,
        "revision": 1, "contentHash": "sha256:" + fill * 64}


def source_row():
    feedback_id = "feedback-1"
    target_id = "content_return_target-" + budget_hash({
        "commandId": feedback_id, "kind": "content_return_target"})[:40]
    command = {
        "operation": "content.review", "artifactRef": ref("ArtifactRevision", "artifact-1", "a"),
        "taskRef": ref("Task", "task-1", "b"),
        "briefRef": ref("TaskBriefRevision", "brief-1", "c"),
        "growthPlanRef": ref("GrowthPlanRevision", "plan-1", "d"),
        "sourceArtifactRefs": [ref("ArtifactRevision", f"source-{n}", str(n)) for n in range(1, 5)],
        "reviewIssueRef": ref("ReviewIssueRevision", "issue-1", "e"),
        "reviewerAuthorityRef": ref("ReviewerAuthorityRevision", "reviewer-1", "f"),
        "artifactContentHash": "sha256:" + "a" * 64,
        "decision": "RETURN", "returnStage": "content_generation", "idempotencyKey": "review-1",
    }
    command["requestHash"] = _analysis_command_hash(command)
    response = {name: command[name] for name in (
        "artifactRef", "taskRef", "briefRef", "reviewIssueRef", "reviewerAuthorityRef",
        "decision", "returnStage", "requestHash")}
    response.update({"replayed": False, "sideEffects": {
        "externalPublicationCount": 0, "externalBusinessMutationCount": 0}})
    response["receiptRef"] = {**ref("ContentReviewReceipt", "review-1", "0"),
        "contentHash": _analysis_command_hash(response)}
    return_decision = {
        "issueId": "issue-1", "issueVersion": 1, "runId": "run-1",
        "stepKey": "content_generate", "stepRunId": "step-2", "attempt": 2,
        "attemptIdempotencyKey": "return-1", "reason": "内容事实需修改", "actor": "reviewer-1",
    }
    return target_id, {
        "command_id": feedback_id, "decision": "RETURN",
        "review_receipt_ref": response["receiptRef"],
        "artifact_ref": command["artifactRef"], "task_ref": command["taskRef"],
        "brief_ref": command["briefRef"], "payload": {
            "kind": "content_return_target", "targetId": target_id,
            "targetPhase": "content_generation"},
        "kind": "content_return_target", "target_id": target_id,
        "response": response, "idempotency_key": "review-1",
        "request_hash": _request_hash(command), "run_id": "run-1",
        "metadata": {"ecommerceGrowthContentArtifact": {
            "growthPlanRef": command["growthPlanRef"],
            "sourceArtifactRefs": command["sourceArtifactRefs"]}},
        "artifact_hash": "a" * 64, "family_revision": 1,
        "issue_id": "issue-1", "issue_version": 2, "issue_status": "returned",
        "decision_id": "decision-1", "decision_issue_version": 1,
        "decision_run_id": "run-1", "step_key": "content_generate",
        "step_run_id": "step-2", "attempt": 2,
        "attempt_idempotency_key": "return-1", "reason": "内容事实需修改",
        "decision_hash": decision_hash(return_decision), "actor": "reviewer-1",
        "impact_decisions": [], "step_status": "queued", "step_attempt": 2,
        "input_refs": [
            {"resourceType": "ReturnDecision", "resourceId": "decision-1",
                "revision": 1, "contentHash": decision_hash(return_decision)},
            {"resourceType": "ReviewIssue", "resourceId": "issue-1", "version": 1},
            {"resourceType": "Artifact", "resourceId": "artifact-1", "contentHash": "a" * 64},
        ],
        "run_status": "running", "task_id": "task-1", "task_status": "executing",
    }


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class SourceDatabase:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return Rows([self.row])


def test_exact_return_decision_and_repair_step_have_stable_read_receipt():
    target_id, row = source_row()
    database = SourceDatabase(row)
    target = BoundContentReturnTarget(HostTransaction(database), SCOPE)
    proof = target._source(target_id, require_queued=True)
    receipt = target._receipt(proof)
    assert target.read_receipt(target_id=target_id, expected_receipt=receipt) == receipt
    assert receipt["resourceType"] == "ContentReturnTargetReceipt"
    assert database.calls[0][1] == ("org-org", "dev-project", target_id)
    assert "aip_return_decision" in database.calls[0][0]
    assert "aip_step_run" in database.calls[0][0]
    row["step_status"] = "succeeded"
    assert target.read_receipt(target_id=target_id, expected_receipt=receipt) == receipt
    with pytest.raises(EcommerceGrowthFeedbackConflict, match="lineage"):
        target._source(target_id, require_queued=True)


@pytest.mark.parametrize("key,value", [
    ("decision_hash", "0" * 64), ("step_run_id", "other-step"),
    ("artifact_hash", "f" * 64), ("issue_status", "open"),
    ("run_status", "succeeded"),
])
def test_tampered_return_source_is_not_accepted(key, value):
    target_id, row = source_row()
    row = deepcopy(row)
    row[key] = value
    target = BoundContentReturnTarget(HostTransaction(SourceDatabase(row)), SCOPE)
    with pytest.raises(EcommerceGrowthFeedbackConflict):
        target._source(target_id, require_queued=True)


@pytest.mark.parametrize("failure", ("commit", "readback", "drift"))
def test_unknown_return_boundary_does_not_report_success_or_reclaim(monkeypatch, failure):
    target_id, row = source_row()
    receipt = {"resourceType": "ContentReturnTargetReceipt", "resourceId": target_id,
        "revision": 1, "contentHash": "sha256:" + "a" * 64}
    segment = {"state": "pending", "attempt": 0, "targetReceiptRef": None,
        "payload": {"kind": "content_return_target", "targetId": target_id}}
    command = {"decision": "RETURN", "reviewReceiptRef": row["review_receipt_ref"],
        "checkpoint": {"completedSequence": 0}, "segments": [segment]}
    accepted = {**command, "checkpoint": {"completedSequence": 1},
        "segments": [{**segment, "state": "acked", "attempt": 1,
            "targetReceiptRef": receipt}]}
    calls = {"claim": 0, "commit": 0, "read": 0, "acked": False}

    class WriteConnection:
        def commit(self):
            calls["commit"] += 1
            if failure == "commit":
                raise RuntimeError("commit boundary unknown")

    @contextmanager
    def write_connect(scope):
        assert scope == SCOPE
        yield WriteConnection()

    @contextmanager
    def read_connect(scope):
        assert scope == SCOPE and calls["commit"] == 1
        calls["read"] += 1
        if failure == "readback":
            raise RuntimeError("independent reader unavailable")
        yield object()

    def read(_self, *, command_id):
        assert command_id == "feedback-1"
        if not calls["acked"]:
            return command
        if failure == "drift":
            return {**accepted, "segments": [{**accepted["segments"][0], "attempt": 2}]}
        return accepted

    def claim(_self, *, command_id, worker):
        assert command_id == "feedback-1" and worker == "ecommerce-content-return"
        calls["claim"] += 1
        return {"sequence": 1, "kind": "content_return_target", "targetId": target_id,
            "attempt": 1, "payload": segment["payload"]}

    monkeypatch.setattr(BoundEcommerceGrowthFeedbackPort, "read", read)
    monkeypatch.setattr(BoundEcommerceGrowthFeedbackPort, "claim_current", claim)
    monkeypatch.setattr(BoundEcommerceGrowthFeedbackPort, "require_current_origin",
        lambda _self, *, command_id: {"reviewReceiptRef": row["review_receipt_ref"]})
    monkeypatch.setattr(BoundEcommerceGrowthFeedbackPort, "acknowledge",
        lambda _self, **_kwargs: calls.update(acked=True) or {"completedSequence": 1})
    monkeypatch.setattr(BoundContentReturnTarget, "read_existing",
        lambda _self, **_kwargs: receipt)
    monkeypatch.setattr(BoundContentReturnTarget, "read_receipt",
        lambda _self, **_kwargs: receipt)
    with pytest.raises(ContentReturnUnknown, match="without resend"):
        ContentReturnFeedbackWorker(connect=write_connect, connect_read=read_connect).run_one(
            SCOPE, "feedback-1")
    assert calls == {"claim": 1, "commit": 1,
        "read": 0 if failure == "commit" else 1, "acked": True}


class NoDatabase:
    def execute(self, *_args, **_kwargs):
        pytest.fail("invalid return target must not touch the database")


@pytest.mark.parametrize("claim", [
    {"sequence": 2}, {"kind": "daily_review"}, {"attempt": 2},
    {"targetId": "other-1"},
])
def test_invalid_return_claim_never_reads_or_acknowledges(claim):
    target = BoundContentReturnTarget(HostTransaction(NoDatabase()), SCOPE)
    valid = {"sequence": 1, "kind": "content_return_target", "attempt": 1,
        "targetId": "content_return_target-1", "payload": {
            "kind": "content_return_target", "targetId": "content_return_target-1",
            "targetPhase": "content_generation"}}
    with pytest.raises(EcommerceGrowthFeedbackConflict):
        target.read_existing(command_id="feedback-1", command={"commandId": "feedback-1",
            "decision": "RETURN", "reviewReceiptRef": ref("ContentReviewReceipt", "review-1", "a")},
            claim={**valid, **claim}, origin={"reviewReceiptRef": ref(
                "ContentReviewReceipt", "review-1", "a")})
