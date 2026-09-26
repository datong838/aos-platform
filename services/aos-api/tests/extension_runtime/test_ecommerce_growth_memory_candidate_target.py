"""A governed candidate is never a promoted Wiki item or a retryable unknown."""

import asyncio
from contextlib import contextmanager

import pytest

from aos_api.ecommerce_growth_memory_candidate_target import (
    CurrentMemoryCandidateConsumer, MemoryCandidateUnknown,
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


class Worker:
    def run_one(self, scope, command_id):
        assert scope == SCOPE and command_id == "feedback-1"
        return {"status": "MEMORY_CANDIDATE_ACKED"}


def test_selector_requires_original_second_ack_formal_review_and_current_host():
    connection = Connection()
    consumer = CurrentMemoryCandidateConsumer(
        connect=lambda scope: connect(connection), worker=Worker(),
    )
    assert consumer.run_once(SCOPE, limit=7) == [{
        "commandId": "feedback-1", "status": "MEMORY_CANDIDATE_ACKED",
    }]
    query, params = connection.calls[0]
    assert "p.completed_sequence=2" in query
    assert "second.state='acked'" in query
    assert "s.state='pending' AND s.attempt=0" in query
    assert "aip_effect_review_revision" in query
    assert "r.maturity_status='insufficient'" in query
    assert "extension_operation_dispatch_binding" in query
    assert "extension_runtime_binding" in query
    assert "ecommerce_growth_runtime_command_receipt" in query
    assert params == ("org-org", "dev-project", 7)


@pytest.mark.parametrize("limit", [0, 33, True])
def test_selector_rejects_unbounded_limit(limit):
    consumer = CurrentMemoryCandidateConsumer(
        connect=lambda scope: connect(Connection()), worker=Worker(),
    )
    with pytest.raises(ValueError, match="bounded"):
        consumer.run_once(SCOPE, limit=limit)


def test_unknown_write_boundary_is_not_swallowed_by_batch_consumer():
    class UnknownWorker:
        def run_one(self, *_args):
            raise MemoryCandidateUnknown("post-commit result unknown")

    consumer = CurrentMemoryCandidateConsumer(
        connect=lambda scope: connect(Connection()), worker=UnknownWorker(),
    )
    with pytest.raises(MemoryCandidateUnknown):
        consumer.run_once(SCOPE)
    with pytest.raises(MemoryCandidateUnknown):
        asyncio.run(consumer.serve(asyncio.Event(), host_ready=lambda: True))


def test_natural_candidate_serve_requires_host_and_bounded_interval():
    consumer = CurrentMemoryCandidateConsumer(
        connect=lambda scope: connect(Connection()), worker=Worker(),
    )
    with pytest.raises(ValueError, match="interval"):
        asyncio.run(consumer.serve(asyncio.Event(), host_ready=lambda: True,
            interval_seconds=0))
    with pytest.raises(RuntimeError, match="Runtime Host"):
        asyncio.run(consumer.serve(asyncio.Event(), host_ready=lambda: False))
