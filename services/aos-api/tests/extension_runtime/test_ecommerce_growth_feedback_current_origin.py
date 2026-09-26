"""A real feedback worker cannot claim a stale or invented review command."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort,
    EcommerceGrowthFeedbackConflict,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction, LockedEcommerceGrowthHostPort
from aos_api.tenant_scope import TenantScope


def ref(kind, identity):
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": "sha256:" + "a" * 64,
        "receiptId": identity,
    }


class Cursor:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


class Connection:
    def __init__(self, command, origins):
        self.command = command
        self.origins = origins
        self.claims = 0

    def execute(self, query, params=()):
        if "FROM public.ecommerce_growth_feedback_command" in query:
            return Cursor(self.command)
        if "FROM public.ecommerce_growth_runtime_command_receipt" in query:
            return Cursor(self.origins)
        if "ecommerce_growth_feedback_claim_ar2_004" in query:
            self.claims += 1
            return Cursor(None)
        raise AssertionError(f"unexpected query: {query}")


def make_port(*, decision="ACCEPT", origin_count=1):
    review = ref("ContentReviewReceipt", "review-1")
    artifact = ref("ArtifactRevision", "artifact-1")
    task = ref("Task", "task-1")
    brief = ref("TaskBriefRevision", "brief-1")
    command = {
        "decision": decision,
        "review_receipt_ref": review,
        "artifact_ref": artifact,
        "task_ref": task,
        "brief_ref": brief,
    }
    origin = {
        "request_hash": "sha256:" + "b" * 64,
        "dispatch_revision": 2,
        "installation_id": uuid4(),
        "generation": uuid4(),
        "execution_epoch": 4,
        "cutover_group_id": uuid4(),
        "cutover_group_revision": 5,
        "runtime_revision": 6,
        "response": {
            "receiptRef": review,
            "decision": decision,
            "artifactRef": artifact,
            "taskRef": task,
            "briefRef": brief,
        },
        "target_receipt_ref": review,
    }
    connection = Connection(command, [origin] * origin_count)
    readers = {
        kind: lambda **kwargs: kwargs["expected_receipt"]
        for kind in ("daily_review", "improvement_observation", "memory_candidate", "content_return_target")
    }
    port = BoundEcommerceGrowthFeedbackPort(
        HostTransaction(connection), TenantScope("org-org", "dev-project"),
        actor="feedback-worker", checked_at=datetime(2026, 9, 26, tzinfo=UTC),
        target_receipt_readers=readers,
    )
    return port, connection, origin


def test_current_origin_is_checked_before_claim(monkeypatch):
    port, connection, origin = make_port()
    seen = []

    def lock(transaction, scope, dispatch):
        seen.append((scope.key, dispatch.installation_id, dispatch.execution_epoch))
        return SimpleNamespace(runtime_revision=origin["runtime_revision"])

    monkeypatch.setattr(LockedEcommerceGrowthHostPort, "_lock_and_revalidate", staticmethod(lock))
    assert port.claim_current(command_id="feedback-1", worker="worker") is None
    assert seen == [(('org-org', 'dev-project'), origin["installation_id"], 4)]
    assert connection.claims == 1


@pytest.mark.parametrize("origin_count", [0, 2])
def test_missing_or_ambiguous_origin_does_not_claim(monkeypatch, origin_count):
    port, connection, _ = make_port(origin_count=origin_count)
    monkeypatch.setattr(
        LockedEcommerceGrowthHostPort, "_lock_and_revalidate",
        staticmethod(lambda *_: pytest.fail("must not lock an unproven origin")),
    )
    with pytest.raises(EcommerceGrowthFeedbackConflict, match="missing or ambiguous"):
        port.claim_current(command_id="feedback-1", worker="worker")
    assert connection.claims == 0


def test_review_content_drift_does_not_claim(monkeypatch):
    port, connection, origin = make_port()
    origin["response"]["decision"] = "RETURN"
    monkeypatch.setattr(
        LockedEcommerceGrowthHostPort, "_lock_and_revalidate",
        staticmethod(lambda *_: pytest.fail("must not lock drifted content")),
    )
    with pytest.raises(EcommerceGrowthFeedbackConflict, match="content drifted"):
        port.claim_current(command_id="feedback-1", worker="worker")
    assert connection.claims == 0


def test_old_or_fenced_runtime_does_not_claim(monkeypatch):
    port, connection, _ = make_port()

    def blocked(*_):
        raise RuntimeError("current runtime fenced")

    monkeypatch.setattr(LockedEcommerceGrowthHostPort, "_lock_and_revalidate", staticmethod(blocked))
    with pytest.raises(EcommerceGrowthFeedbackConflict, match="could not be proven"):
        port.claim_current(command_id="feedback-1", worker="worker")
    assert connection.claims == 0


def test_runtime_revision_drift_does_not_claim(monkeypatch):
    port, connection, origin = make_port()
    monkeypatch.setattr(
        LockedEcommerceGrowthHostPort, "_lock_and_revalidate",
        staticmethod(lambda *_: SimpleNamespace(runtime_revision=origin["runtime_revision"] + 1)),
    )
    with pytest.raises(EcommerceGrowthFeedbackConflict, match="runtime revision drifted"):
        port.claim_current(command_id="feedback-1", worker="worker")
    assert connection.claims == 0
