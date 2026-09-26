"""A reviewed content result reaches one durable daily-review target atomically."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_growth_daily_review_target import DailyReviewFeedbackWorker
from aos_api.tenant_scope import TenantScope


RECEIPT = {
    "resourceType": "DailyReviewReceipt",
    "resourceId": "daily_review-1",
    "revision": 1,
    "contentHash": "sha256:" + "a" * 64,
    "receiptId": "daily_review-1",
}
REVIEW_REF = {"resourceType": "ContentReviewReceipt", "resourceId": "review-1", "revision": 1,
              "contentHash": "sha256:" + "b" * 64, "receiptId": "review-1"}
FIRST_PAYLOAD = {"sequence": 1, "kind": "daily_review", "targetId": "daily_review-1",
                 "businessTitle": "今日内容复盘", "businessSummary": "内容通过评审，效果待观察。",
                 "targetPhase": None}


class Connection:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


@contextmanager
def connect_factory(connection):
    yield connection


class FakePort:
    instance = None
    status = "pending"
    claim_kind = "daily_review"
    fail_ack = False

    def __init__(self, *_args, **_kwargs):
        self.events = []
        FakePort.instance = self

    def read(self, *, command_id):
        self.events.append("read")
        return {
            "decision": "ACCEPT",
            "reviewReceiptRef": REVIEW_REF,
            "artifactRef": {"resourceType": "ArtifactRevision"},
            "taskRef": {"resourceType": "Task"},
            "briefRef": {"resourceType": "TaskBriefRevision"},
            "segments": [
                {"state": self.status, "kind": "daily_review", "payload": FIRST_PAYLOAD,
                 "targetReceiptRef": RECEIPT if self.status == "acked" else None},
                {"state": "pending", "kind": "improvement_observation", "payload": {"kind": "improvement_observation"}},
                {"state": "pending", "kind": "memory_candidate", "payload": {"kind": "memory_candidate"}},
            ],
            "checkpoint": {"completedSequence": 1 if self.status == "acked" else 0},
        }

    def claim_current(self, **_kwargs):
        self.events.append("claim_current")
        if self.status != "pending":
            return None
        return {
            "sequence": 1, "kind": self.claim_kind, "targetId": "daily_review-1",
            "payload": FIRST_PAYLOAD,
            "attempt": 1, "leaseToken": "lease-1", "checkpointVersion": 1,
        }

    def require_current_origin(self, **_kwargs):
        self.events.append("revalidate_before_write")
        return {"dispatch": SimpleNamespace(installation_id="install-1", generation="gen-1", execution_epoch=1),
                "reviewReceiptRef": REVIEW_REF}

    def acknowledge(self, **_kwargs):
        self.events.append("ack")
        if self.fail_ack:
            raise RuntimeError("feedback ack failed")
        self.status = "acked"
        return {"completedSequence": 1, "checkpointVersion": 2, "receiptRef": RECEIPT}


class FakeTarget:
    instance = None
    fail_write = False

    def __init__(self, *_args):
        self.events = []
        FakeTarget.instance = self

    def put(self, **_kwargs):
        self.events.append("put")
        if self.fail_write:
            raise RuntimeError("target write failed")
        return RECEIPT

    def read_receipt(self, **_kwargs):
        self.events.append("read_receipt")
        return RECEIPT


@pytest.fixture(autouse=True)
def reset_fakes():
    FakePort.status = "pending"
    FakePort.claim_kind = "daily_review"
    FakePort.fail_ack = False
    FakeTarget.fail_write = False
    FakeTarget.instance = None


def worker(monkeypatch, connection):
    import aos_api.ecommerce_growth_daily_review_target as module

    monkeypatch.setattr(module, "BoundEcommerceGrowthFeedbackPort", FakePort)
    monkeypatch.setattr(module, "BoundDailyReviewTarget", FakeTarget)
    return DailyReviewFeedbackWorker(connect=lambda scope: connect_factory(connection))


def test_daily_review_is_written_read_back_and_acked_before_commit(monkeypatch):
    connection = Connection()
    result = worker(monkeypatch, connection).run_one(TenantScope("org-org", "dev-project"), "feedback-1")
    assert result["status"] == "DAILY_REVIEW_ACKED"
    assert connection.commits == 1
    assert FakePort.instance.events == ["read", "claim_current", "revalidate_before_write", "ack", "read"]
    assert FakeTarget.instance.events == ["put", "read_receipt"]


def test_existing_ack_is_read_only_and_does_not_claim(monkeypatch):
    FakePort.status = "acked"
    connection = Connection()
    result = worker(monkeypatch, connection).run_one(TenantScope("org-org", "dev-project"), "feedback-1")
    assert result["status"] == "ALREADY_ACKED"
    assert FakePort.instance.events == ["read"]
    assert connection.commits == 0


def test_write_error_does_not_commit_or_ack(monkeypatch):
    FakeTarget.fail_write = True
    connection = Connection()
    with pytest.raises(RuntimeError, match="target write failed"):
        worker(monkeypatch, connection).run_one(TenantScope("org-org", "dev-project"), "feedback-1")
    assert connection.commits == 0
    assert "ack" not in FakePort.instance.events


def test_unsupported_kind_does_not_write_or_commit(monkeypatch):
    FakePort.claim_kind = "memory_candidate"
    connection = Connection()
    with pytest.raises(RuntimeError, match="unsupported feedback segment"):
        worker(monkeypatch, connection).run_one(TenantScope("org-org", "dev-project"), "feedback-1")
    assert connection.commits == 0
    assert FakeTarget.instance is None or FakeTarget.instance.events == []


def test_ack_error_does_not_commit_target(monkeypatch):
    FakePort.fail_ack = True
    connection = Connection()
    with pytest.raises(RuntimeError, match="feedback ack failed"):
        worker(monkeypatch, connection).run_one(TenantScope("org-org", "dev-project"), "feedback-1")
    assert FakeTarget.instance.events == ["put", "read_receipt"]
    assert connection.commits == 0
