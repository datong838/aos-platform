"""Second feedback segment must remain pending until the exact first Receipt."""

from contextlib import contextmanager

import pytest

from aos_api.ecommerce_growth_feedback_port import EcommerceGrowthFeedbackConflict
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_improvement_target import (
    BoundImprovementPendingTarget, CurrentImprovementConsumer,
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
