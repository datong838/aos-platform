"""Receipt-first review terminal Owner remains off until exact authority exists."""

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_content_review_step_owner import (
    ContentReviewStepConflict, ContentReviewStepOwner, ContentReviewStepUnknown,
)
from aos_api.main import _start_content_review_step_worker
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


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


def test_selector_only_names_current_accepted_receipts_without_review_attempt():
    connection = Connection([{"receipt_id": "a366a04f-f954-4e4b-8cb9-6ea8b4b26410"}])
    owner = ContentReviewStepOwner(connect_read=lambda scope: connect(connection))
    assert owner.list_pending(SCOPE, limit=3) == ["a366a04f-f954-4e4b-8cb9-6ea8b4b26410"]
    query, params = connection.calls[0]
    assert "ecommerce_growth_runtime_command_receipt" in query
    assert "ecommerce_growth_feedback_command" in query
    assert "r.status='running'" in query and "t.status='executing'" in query
    assert "NOT EXISTS" in query and "step_key='content_review'" in query
    assert params == (*SCOPE.key, 3)


@pytest.mark.parametrize("limit", [0, 17, True])
def test_selector_rejects_unbounded_limit(limit):
    owner = ContentReviewStepOwner(connect_read=lambda scope: connect(Connection([])))
    with pytest.raises(ValueError, match="bounded"):
        owner.list_pending(SCOPE, limit=limit)


def test_missing_receipt_never_opens_a_review_attempt():
    connection = Connection([])
    owner = ContentReviewStepOwner(connect_write=lambda scope: connect(connection))
    with pytest.raises(ContentReviewStepConflict, match="Receipt"):
        owner.run_one(SCOPE, "a366a04f-f954-4e4b-8cb9-6ea8b4b26410")
    assert len(connection.calls) == 1


def test_ambiguous_receipts_never_open_a_review_attempt():
    connection = Connection([{"response": {}}, {"response": {}}])
    owner = ContentReviewStepOwner(connect_write=lambda scope: connect(connection))
    with pytest.raises(ContentReviewStepConflict, match="unique current"):
        owner.run_one(SCOPE, "a366a04f-f954-4e4b-8cb9-6ea8b4b26410")
    assert len(connection.calls) == 1


def test_selector_refuses_duplicate_receipt_identity():
    identity = "a366a04f-f954-4e4b-8cb9-6ea8b4b26410"
    owner = ContentReviewStepOwner(connect_read=lambda scope: connect(
        Connection([{"receipt_id": identity}, {"receipt_id": identity}])))
    with pytest.raises(ContentReviewStepConflict, match="identity drifted"):
        owner.list_pending(SCOPE)


def test_incomplete_receipt_cannot_be_reconstructed_as_a_review_command():
    connection = Connection([{"response": {}, "metadata": {"ecommerceGrowthContentArtifact": {}}}])
    owner = ContentReviewStepOwner(connect_write=lambda scope: connect(connection))
    with pytest.raises(ContentReviewStepConflict, match="cannot be reconstructed"):
        owner.run_one(SCOPE, "a366a04f-f954-4e4b-8cb9-6ea8b4b26410")
    assert len(connection.calls) == 1


def test_natural_runner_isolates_known_blocker_but_stops_on_unknown():
    owner = ContentReviewStepOwner()
    owner.list_pending = lambda *_args, **_kwargs: ["one", "two"]
    owner.run_one = lambda _scope, receipt_id: (
        (_ for _ in ()).throw(ContentReviewStepConflict("known"))
        if receipt_id == "one" else {"status": "CONTENT_REVIEW_RUN_SUCCEEDED"})
    assert owner.run_once(SCOPE) == [
        {"receiptId": "one", "status": "BLOCKED_CURRENT_AUTHORITY"},
        {"receiptId": "two", "status": "CONTENT_REVIEW_RUN_SUCCEEDED"},
    ]
    owner.run_one = lambda *_: (_ for _ in ()).throw(ContentReviewStepUnknown("unknown"))
    with pytest.raises(ContentReviewStepUnknown):
        owner.run_once(SCOPE)
    owner.run_one = lambda *_: (_ for _ in ()).throw(RuntimeError("database unavailable"))
    with pytest.raises(RuntimeError, match="database unavailable"):
        owner.run_once(SCOPE)


def test_natural_review_owner_stops_when_host_is_lost():
    owner = ContentReviewStepOwner()
    with pytest.raises(RuntimeError, match="Runtime Host unavailable"):
        asyncio.run(owner.serve(asyncio.Event(), host_ready=lambda: False))


def _app():
    return SimpleNamespace(state=SimpleNamespace(
        extension_runtime_host_task=None,
        extension_runtime_host_status="DISABLED",
        runtime_background_tasks=[],
    ))


def test_review_step_worker_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED", raising=False)
    application = _app()
    asyncio.run(_start_content_review_step_worker(application, asyncio.Event()))
    assert application.state.content_review_step_worker_status == "DISABLED"
    assert application.state.runtime_background_tasks == []


def test_review_step_worker_rejects_invalid_flag_and_absent_host(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED", "maybe")
    application = _app()
    with pytest.raises(RuntimeError, match="enable flag"):
        asyncio.run(_start_content_review_step_worker(application, asyncio.Event()))
    assert application.state.content_review_step_worker_status == "FAILED_CLOSED"
    monkeypatch.setenv("AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED", "true")
    application = _app()
    with pytest.raises(RuntimeError, match="active Runtime Host"):
        asyncio.run(_start_content_review_step_worker(application, asyncio.Event()))
    assert application.state.content_review_step_worker_status == "FAILED_CLOSED"


def test_review_step_worker_requires_distinct_runtime_identity(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED", "true")
    from aos_api.extension_runtime import runtime_connections

    def unavailable():
        raise RuntimeError("runtime identity missing")

    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn", unavailable)

    async def exercise():
        host = asyncio.create_task(asyncio.sleep(10))
        application = _app()
        application.state.extension_runtime_host_task = host
        application.state.extension_runtime_host_status = "ACTIVE"
        try:
            with pytest.raises(RuntimeError, match="runtime identity missing"):
                await _start_content_review_step_worker(application, asyncio.Event())
            assert application.state.content_review_step_worker_status == "FAILED_CLOSED"
            assert application.state.runtime_background_tasks == []
        finally:
            host.cancel()
            try:
                await host
            except asyncio.CancelledError:
                pass

    asyncio.run(exercise())


def test_review_step_worker_is_managed_and_stops_with_host(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED", "true")
    from aos_api.extension_runtime import runtime_connections
    import aos_api.main as main
    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn", lambda: "isolated-test-dsn")
    calls = []

    class Owner:
        async def serve(self, stop, *, host_ready):
            calls.append(host_ready())
            await stop.wait()

    monkeypatch.setattr(main, "_build_content_review_step_owner", lambda: Owner())

    async def exercise():
        stop = asyncio.Event()
        host = asyncio.create_task(asyncio.sleep(10))
        application = _app()
        application.state.extension_runtime_host_task = host
        application.state.extension_runtime_host_status = "ACTIVE"
        await _start_content_review_step_worker(application, stop)
        assert application.state.content_review_step_worker_status == "RUNNING"
        assert calls == [True]
        stop.set()
        await application.state.content_review_step_worker_task
        assert application.state.content_review_step_worker_status == "STOPPED"
        host.cancel()
        try:
            await host
        except asyncio.CancelledError:
            pass

    asyncio.run(exercise())


def test_review_step_worker_immediate_failure_leaves_no_background_task(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED", "true")
    from aos_api.extension_runtime import runtime_connections
    import aos_api.main as main
    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn", lambda: "isolated-test-dsn")

    class Owner:
        async def serve(self, _stop, *, host_ready):
            assert host_ready()
            raise RuntimeError("unknown commit boundary")

    monkeypatch.setattr(main, "_build_content_review_step_owner", lambda: Owner())

    async def exercise():
        host = asyncio.create_task(asyncio.sleep(10))
        application = _app()
        application.state.extension_runtime_host_task = host
        application.state.extension_runtime_host_status = "ACTIVE"
        try:
            with pytest.raises(RuntimeError, match="failed during startup"):
                await _start_content_review_step_worker(application, asyncio.Event())
            assert application.state.content_review_step_worker_status == "FAILED_CLOSED"
            assert application.state.content_review_step_worker_task is None
            assert application.state.runtime_background_tasks == []
        finally:
            host.cancel()
            try:
                await host
            except asyncio.CancelledError:
                pass

    asyncio.run(exercise())
