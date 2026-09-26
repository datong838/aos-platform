"""Second feedback segment must remain pending until the exact first Receipt."""

from contextlib import contextmanager

import pytest

from aos_api.ecommerce_growth_feedback_port import BoundEcommerceGrowthFeedbackPort, EcommerceGrowthFeedbackConflict
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_improvement_target import (
    BoundImprovementPendingTarget, CurrentImprovementConsumer,
    ImprovementFeedbackUnknown, ImprovementFeedbackWorker,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


class NoWrite:
    def execute(self, *_args, **_kwargs):
        pytest.fail("invalid improvement target must not touch the database")


def _ref(kind):
    return {"resourceType": kind, "resourceId": kind + "-1", "revision": 1,
        "contentHash": "sha256:" + "a" * 64, "receiptId": kind + "-1"}


def _command():
    return {"decision": "ACCEPT", "reviewReceiptRef": _ref("ContentReviewReceipt"),
        "artifactRef": _ref("ArtifactRevision"), "taskRef": _ref("Task"),
        "briefRef": _ref("TaskBriefRevision")}


def _claim():
    return {"sequence": 2, "kind": "improvement_observation",
        "targetId": "improvement_observation-1", "payload": {
            "sequence": 2, "kind": "improvement_observation",
            "targetId": "improvement_observation-1", "businessTitle": "内容效果改进建议",
            "businessSummary": "等待可比较的业务证据", "targetPhase": None},
        "attempt": 1, "leaseToken": "b97bb670-29ab-4c14-ab1c-5b73c497965f",
        "checkpointVersion": 2}


@pytest.mark.parametrize("mutation", [
    {"sequence": 1}, {"kind": "memory_candidate"}, {"attempt": 2},
    {"targetId": "daily_review-1"}, {"checkpointVersion": 0},
])
def test_invalid_second_claim_cannot_write(mutation):
    target = BoundImprovementPendingTarget(HostTransaction(NoWrite()), SCOPE)
    claim = {**_claim(), **mutation}
    with pytest.raises(EcommerceGrowthFeedbackConflict, match="input drifted"):
        target.put(command_id="feedback-1", command=_command(), claim=claim,
            origin={"reviewReceiptRef": _ref("ContentReviewReceipt")},
            daily_receipt_ref=_ref("DailyReviewReceipt"))


def test_non_accept_cannot_write():
    target = BoundImprovementPendingTarget(HostTransaction(NoWrite()), SCOPE)
    with pytest.raises(EcommerceGrowthFeedbackConflict, match="input drifted"):
        target.put(command_id="feedback-1", command={**_command(), "decision": "RETURN"},
            claim=_claim(), origin={"reviewReceiptRef": _ref("ContentReviewReceipt")},
            daily_receipt_ref=_ref("DailyReviewReceipt"))


class Cursor:
    def fetchall(self):
        return [{"command_id": "feedback-1"}]


class ReadConnection:
    def __init__(self):
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return Cursor()


@contextmanager
def connect(connection):
    yield connection


class Worker:
    def run_one(self, scope, command_id):
        assert scope == SCOPE and command_id == "feedback-1"
        return {"status": "IMPROVEMENT_PENDING_ACKED"}


def test_selector_is_bounded_and_tied_to_first_receipt_and_original_run():
    connection = ReadConnection()
    consumer = CurrentImprovementConsumer(connect=lambda scope: connect(connection), worker=Worker())
    assert consumer.run_once(SCOPE, limit=7) == [
        {"commandId": "feedback-1", "status": "IMPROVEMENT_PENDING_ACKED"}]
    query, params = connection.calls[0]
    assert "first.state='acked'" in query and "p.completed_sequence=1" in query
    assert "second.state='pending'" in query and "second.attempt=0" in query
    assert "ecommerce_growth_daily_review_target" in query
    assert "ecommerce_growth_runtime_command_receipt" in query
    assert "aip_task_run" in query and "aip_task" in query
    assert params == ("org-org", "dev-project", 7)


@pytest.mark.parametrize("limit", [0, 33, True])
def test_selector_rejects_unbounded_limit(limit):
    consumer = CurrentImprovementConsumer(connect=lambda scope: connect(ReadConnection()), worker=Worker())
    with pytest.raises(ValueError, match="bounded"):
        consumer.run_once(SCOPE, limit=limit)


def test_natural_selector_never_swallows_unknown_result():
    class UnknownWorker:
        def run_one(self, _scope, _command_id):
            raise ImprovementFeedbackUnknown("postcommit unknown")

    consumer = CurrentImprovementConsumer(
        connect=lambda scope: connect(ReadConnection()), worker=UnknownWorker())
    with pytest.raises(ImprovementFeedbackUnknown, match="postcommit unknown"):
        consumer.run_once(SCOPE)


@pytest.mark.parametrize("failure", ["commit", "read", "drift"])
def test_second_target_unknown_boundary_never_reports_success(monkeypatch, failure):
    receipt = _ref("ImprovementPendingReceipt")
    first = {"state": "acked", "targetReceiptRef": _ref("DailyReviewReceipt"),
        "payload": {"kind": "daily_review"}}
    second = {"state": "pending", "attempt": 0, "targetReceiptRef": None,
        "payload": {"kind": "improvement_observation", "targetId": _claim()["targetId"]}}
    command = {**_command(), "checkpoint": {"completedSequence": 1},
        "segments": [first, second, {"state": "pending"}]}
    current = {**command, "checkpoint": {"completedSequence": 2},
        "segments": [first, {**second, "state": "acked", "attempt": 1,
            "targetReceiptRef": receipt}, {"state": "pending"}]}
    observed = {"commits": 0, "reads": 0, "claims": 0, "acked": False}

    class WriteConnection:
        def commit(self):
            observed["commits"] += 1
            if failure == "commit":
                raise RuntimeError("commit boundary is unknown")

    @contextmanager
    def write_connect(scope):
        assert scope == SCOPE
        yield WriteConnection()

    @contextmanager
    def read_connect(scope):
        assert scope == SCOPE and observed["commits"] == 1
        observed["reads"] += 1
        if failure == "read":
            raise RuntimeError("independent read unavailable")
        yield object()

    def read(_self, *, command_id):
        assert command_id == "feedback-1"
        if observed["commits"] and failure == "drift":
            return {**current, "segments": [first,
                {**current["segments"][1], "attempt": 2}, {"state": "pending"}]}
        return current if observed["acked"] else command

    def claim(_self, *, command_id, worker):
        assert command_id == "feedback-1" and worker == "ecommerce-improvement"
        observed["claims"] += 1
        return _claim()

    monkeypatch.setattr(BoundEcommerceGrowthFeedbackPort, "read", read)
    monkeypatch.setattr(BoundEcommerceGrowthFeedbackPort, "claim_current", claim)
    monkeypatch.setattr(BoundEcommerceGrowthFeedbackPort, "require_current_origin",
        lambda _self, *, command_id: {"reviewReceiptRef": command["reviewReceiptRef"]})
    def acknowledge(_self, **_kwargs):
        observed["acked"] = True
        return {"completedSequence": 2}
    monkeypatch.setattr(BoundEcommerceGrowthFeedbackPort, "acknowledge", acknowledge)
    monkeypatch.setattr(BoundImprovementPendingTarget, "put",
        lambda _self, **_kwargs: receipt)
    monkeypatch.setattr(BoundImprovementPendingTarget, "read_receipt",
        lambda _self, **_kwargs: receipt)
    with pytest.raises(ImprovementFeedbackUnknown, match="without resend"):
        ImprovementFeedbackWorker(connect=write_connect, connect_read=read_connect).run_one(
            SCOPE, "feedback-1")
    assert observed == {"commits": 1, "reads": 0 if failure == "commit" else 1,
        "claims": 1, "acked": True}
