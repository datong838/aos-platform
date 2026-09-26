"""A formal effect review is routed only after the original pending receipt."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_growth_effect_review_owner import (
    CurrentEffectReviewConsumer, EffectReviewOwner, EffectReviewUnknown,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


class Cursor:
    def fetchall(self):
        return [{"command_id": "feedback-1"}]


class Connection:
    def __init__(self):
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return Cursor()


@contextmanager
def connect(connection):
    yield connection


class Owner:
    def run_one(self, scope, command_id):
        assert scope == SCOPE and command_id == "feedback-1"
        return {"status": "EFFECT_REVIEW_INSUFFICIENT"}


def test_selector_requires_second_receipt_current_runtime_and_no_formal_review():
    connection = Connection()
    consumer = CurrentEffectReviewConsumer(connect=lambda scope: connect(connection), owner=Owner())
    assert consumer.run_once(SCOPE, limit=7) == [
        {"commandId": "feedback-1", "status": "EFFECT_REVIEW_INSUFFICIENT"}]
    query, params = connection.calls[0]
    assert "p.completed_sequence=2" in query
    assert "s.state='acked'" in query
    assert "ecommerce_growth_improvement_target" in query
    assert "extension_operation_dispatch_binding" in query
    assert "extension_runtime_binding" in query
    assert "ecommerce_growth_runtime_command_receipt" in query
    assert "NOT EXISTS" in query and "aip_effect_review_head" in query
    assert params == ("org-org", "dev-project", 7)


@pytest.mark.parametrize("limit", [0, 33, True])
def test_selector_rejects_unbounded_limit(limit):
    consumer = CurrentEffectReviewConsumer(
        connect=lambda scope: connect(Connection()), owner=Owner())
    with pytest.raises(ValueError, match="bounded"):
        consumer.run_once(SCOPE, limit=limit)


def test_post_commit_readback_failure_is_unknown_and_not_a_retryable_block(monkeypatch):
    from aos_api import ecommerce_growth_effect_review_owner as module

    class WriteConnection:
        commits = 0

        def commit(self):
            self.commits += 1

    write = WriteConnection()

    @contextmanager
    def broken_read(_scope):
        raise RuntimeError("read transport failed")
        yield

    monkeypatch.setattr(EffectReviewOwner, "_source", staticmethod(
        lambda *_: {"resourceType": "ImprovementPendingReceipt", "resourceId": "pending-1",
            "revision": 1, "contentHash": "sha256:" + "a" * 64}))
    monkeypatch.setattr(EffectReviewOwner, "_existing", staticmethod(lambda *_: None))
    monkeypatch.setattr(EffectReviewOwner, "_verify_review", staticmethod(lambda *_: None))
    monkeypatch.setattr(module, "AipEffectReviewStore", lambda: SimpleNamespace(
        create_review_in_transaction=lambda *_args, **_kwargs: SimpleNamespace(review_id="review-1")))
    owner = EffectReviewOwner(connect=lambda scope: connect(write), connect_read=broken_read)
    with pytest.raises(EffectReviewUnknown, match="reconcile without resend"):
        owner.run_one(SCOPE, "feedback-1")
    assert write.commits == 1

    class UnknownOwner:
        def run_one(self, *_args):
            raise EffectReviewUnknown("unknown")

    consumer = CurrentEffectReviewConsumer(
        connect=lambda scope: connect(Connection()), owner=UnknownOwner())
    with pytest.raises(EffectReviewUnknown):
        consumer.run_once(SCOPE)
