"""Natural feedback consumption is bounded, current-scoped and default-off."""

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_growth_feedback_consumer import CurrentFeedbackConsumer
from aos_api.main import _start_ecommerce_feedback_worker
from aos_api.tenant_scope import TenantScope


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))
        return Cursor(self.rows)


@contextmanager
def connect(connection):
    yield connection


class Worker:
    def __init__(self):
        self.calls = []

    def run_one(self, scope, command_id):
        self.calls.append((scope.key, command_id))
        return {"status": "DAILY_REVIEW_ACKED"}


def app(host_task=None):
    return SimpleNamespace(state=SimpleNamespace(
        extension_runtime_host_task=host_task,
        extension_runtime_host_status="ACTIVE" if host_task else "DISABLED",
        runtime_background_tasks=[],
    ))


def test_selector_has_current_origin_and_never_selects_claimed_or_unknown():
    connection = Connection([{"command_id": "feedback-current-1"}])
    worker = Worker()
    consumer = CurrentFeedbackConsumer(connect=lambda scope: connect(connection), worker=worker)
    result = consumer.run_once(TenantScope("org-org", "dev-project"), limit=7)
    assert result == [{"commandId": "feedback-current-1", "status": "DAILY_REVIEW_ACKED"}]
    assert worker.calls == [(('org-org', 'dev-project'), 'feedback-current-1')]
    query, params = connection.calls[0]
    assert "s.state='pending'" in query and "s.attempt=0" in query
    assert "ecommerce_growth_runtime_command_receipt" in query
    assert "extension_operation_dispatch_binding" in query
    assert "extension_runtime_binding" in query
    assert "aip_artifact" in query and "aip_task_run" in query and "aip_task" in query
    assert params == ("org-org", "dev-project", 7)


@pytest.mark.parametrize("limit", [0, 33, True])
def test_selector_rejects_unbounded_limits(limit):
    consumer = CurrentFeedbackConsumer(connect=lambda scope: connect(Connection([])), worker=Worker())
    with pytest.raises(ValueError, match="bounded"):
        consumer.run_once(TenantScope("org-org", "dev-project"), limit=limit)


def test_feedback_worker_is_off_by_default(monkeypatch):
    monkeypatch.delenv("AOS_ECOM_FEEDBACK_WORKER_ENABLED", raising=False)
    application = app()
    asyncio.run(_start_ecommerce_feedback_worker(application, asyncio.Event()))
    assert application.state.ecommerce_feedback_worker_status == "DISABLED"
    assert application.state.runtime_background_tasks == []


def test_feedback_worker_requires_active_host(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_FEEDBACK_WORKER_ENABLED", "true")
    application = app()
    with pytest.raises(RuntimeError, match="active Runtime Host"):
        asyncio.run(_start_ecommerce_feedback_worker(application, asyncio.Event()))
    assert application.state.ecommerce_feedback_worker_status == "FAILED_CLOSED"


def test_feedback_worker_invalid_flag_fails_closed(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_FEEDBACK_WORKER_ENABLED", "maybe")
    application = app()
    with pytest.raises(RuntimeError, match="enable flag is invalid"):
        asyncio.run(_start_ecommerce_feedback_worker(application, asyncio.Event()))
    assert application.state.ecommerce_feedback_worker_status == "FAILED_CLOSED"


def test_feedback_worker_requires_distinct_runtime_identity(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_FEEDBACK_WORKER_ENABLED", "true")
    from aos_api.extension_runtime import runtime_connections

    def missing_identity():
        raise RuntimeError("runtime identity missing")

    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn", missing_identity)

    async def exercise():
        host = asyncio.create_task(asyncio.sleep(10))
        application = app(host)
        try:
            with pytest.raises(RuntimeError, match="runtime identity missing"):
                await _start_ecommerce_feedback_worker(application, asyncio.Event())
            assert application.state.ecommerce_feedback_worker_status == "FAILED_CLOSED"
            assert application.state.runtime_background_tasks == []
        finally:
            host.cancel()
            try:
                await host
            except asyncio.CancelledError:
                pass

    asyncio.run(exercise())


def test_feedback_worker_managed_by_host_stop(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_FEEDBACK_WORKER_ENABLED", "true")
    from aos_api.extension_runtime import runtime_connections
    import aos_api.main as main

    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn", lambda: "isolated-test-dsn")
    calls = []

    class Runner:
        async def serve(self, stop, *, host_ready):
            calls.append(host_ready())
            await stop.wait()

    monkeypatch.setattr(main, "_build_ecommerce_feedback_consumer", lambda: Runner())

    async def exercise():
        stop = asyncio.Event()
        host = asyncio.create_task(asyncio.sleep(10))
        application = app(host)
        await _start_ecommerce_feedback_worker(application, stop)
        assert application.state.ecommerce_feedback_worker_status == "RUNNING"
        assert calls == [True]
        stop.set()
        await application.state.ecommerce_feedback_worker_task
        assert application.state.ecommerce_feedback_worker_status == "STOPPED"
        host.cancel()
        try:
            await host
        except asyncio.CancelledError:
            pass

    asyncio.run(exercise())
