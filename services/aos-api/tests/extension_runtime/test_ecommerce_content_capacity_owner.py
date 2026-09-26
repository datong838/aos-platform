"""Content capacity starts once and never retries an unknown transition."""

from contextlib import contextmanager
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def test_capacity_owner_unknown_transition_spends_claim_without_resend(monkeypatch):
    from aos_api.ecommerce_content_capacity_owner import ContentCapacityOwner

    calls = []
    token = uuid4()

    class Cursor:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class Conn:
        def execute(self, query, params=()):
            if "capacity_claim_a0v_103" in query:
                calls.append("claim")
                return Cursor({"claimed": True})
            if "capacity_intent" in query and "claim_token" in query:
                return Cursor({"state": "claimed", "attempt": 1, "claim_token": token,
                               "agent_run_id": "agent-1"})
            raise AssertionError(query)

        def commit(self):
            calls.append("commit")

    @contextmanager
    def connect(_scope):
        yield Conn()

    owner = ContentCapacityOwner(connect_read=connect, connect_write=connect)
    monkeypatch.setattr(owner, "_preflight", lambda *_: SimpleNamespace(
        agent_run_id="agent-1", version=1))
    monkeypatch.setattr(owner, "_transition", lambda *_: (
        calls.append("transition"), (_ for _ in ()).throw(RuntimeError("unknown commit"))))
    assert owner.claim(SCOPE, "review-1", token=token) == token
    with pytest.raises(RuntimeError, match="unknown commit"):
        owner.execute_claim(SCOPE, "review-1", token)
    assert calls == ["claim", "commit", "transition"]


def test_capacity_owner_accepts_only_read_back_running_reservation(monkeypatch):
    from aos_api.aip_agent_registry_contracts import AgentRunStatus
    from aos_api.ecommerce_content_capacity_owner import ContentCapacityOwner
    from aos_api.ecommerce_content_agentrun_owner import ContentAgentRunOwner

    token = uuid4()
    events = []
    request = SimpleNamespace(agent_run_id="agent-1", run="frozen-request")
    current = SimpleNamespace(agent_run_id="agent-1", version=1, request="frozen-request")

    class Cursor:
        def __init__(self, row=None, rows=None):
            self.row, self.rows = row, rows

        def fetchone(self):
            return self.row

        def fetchall(self):
            return self.rows

    class Conn:
        def execute(self, query, params=()):
            if "capacity_intent" in query and "claim_token" in query:
                if "capacity_reservation_id" in query:
                    events.append("readback")
                    return Cursor({"state": "accepted", "attempt": 1, "claim_token": token,
                                   "agent_run_id": "agent-1", "capacity_reservation_id": "cap-1"})
                return Cursor({"state": "claimed", "attempt": 1, "claim_token": token,
                               "agent_run_id": "agent-1"})
            if "aip_model_capacity_reservation" in query:
                events.append("capacity_readback")
                return Cursor(rows=[{"reservation_id": "cap-1"}])
            if "capacity_ack_a0v_103" in query:
                events.append("ack")
                return Cursor({"accepted": True})
            raise AssertionError(query)

        def commit(self):
            events.append("commit")

    @contextmanager
    def connect(_scope):
        yield Conn()

    owner = ContentCapacityOwner(connect_read=connect, connect_write=connect)
    monkeypatch.setattr(owner, "_preflight", lambda *_: current)
    monkeypatch.setattr(owner, "_transition", lambda *_: (
        events.append("transition"), SimpleNamespace(status=AgentRunStatus.RUNNING))[1])
    monkeypatch.setattr(ContentAgentRunOwner, "_build_request", staticmethod(
        lambda *_args, **_kwargs: request))
    result = owner.execute_claim(SCOPE, "review-1", token)
    assert result["capacityReservationId"] == "cap-1"
    assert events == ["transition", "capacity_readback", "ack", "commit", "readback"]


def test_capacity_worker_is_off_by_default(monkeypatch):
    from aos_api.main import _start_content_capacity_worker

    monkeypatch.delenv("AOS_ECOM_CONTENT_CAPACITY_WORKER_ENABLED", raising=False)
    application = SimpleNamespace(state=SimpleNamespace())
    asyncio.run(_start_content_capacity_worker(application, asyncio.Event()))
    assert application.state.content_capacity_worker_status == "DISABLED"


def test_capacity_worker_needs_active_host(monkeypatch):
    from aos_api.main import _start_content_capacity_worker

    monkeypatch.setenv("AOS_ECOM_CONTENT_CAPACITY_WORKER_ENABLED", "true")
    application = SimpleNamespace(state=SimpleNamespace(extension_runtime_host_status="INACTIVE"))
    with pytest.raises(RuntimeError, match="active Runtime Host"):
        asyncio.run(_start_content_capacity_worker(application, asyncio.Event()))
    assert application.state.content_capacity_worker_status == "FAILED_CLOSED"


def test_existing_or_unknown_capacity_never_consumes_another_attempt(monkeypatch):
    from aos_api.ecommerce_content_capacity_owner import ContentCapacityConflict, ContentCapacityOwner

    @contextmanager
    def forbidden_connect(_scope):
        raise AssertionError("capacity claim must not be sent")
        yield

    owner = ContentCapacityOwner(connect_write=forbidden_connect)
    monkeypatch.setattr(owner, "_preflight", lambda *_: (
        _ for _ in ()).throw(ContentCapacityConflict("already reserved; reconcile")))
    assert owner.claim(SCOPE, "review-1") is None
