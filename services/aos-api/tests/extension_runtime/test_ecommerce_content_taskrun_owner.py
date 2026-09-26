"""Natural content TaskRun startup never retries an unknown or claimed intent."""

from contextlib import contextmanager
import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import aos_api.ecommerce_content_taskrun_owner as owner_module
from aos_api.ecommerce_content_taskrun_owner import ContentTaskRunOwner
from aos_api.main import _start_content_taskrun_worker
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def test_selector_is_tenant_bounded_and_only_pristine_pending():
    calls = []

    class Cursor:
        def fetchall(self):
            return [{"review_key": "review-key-1"}]

    class Conn:
        def execute(self, query, params):
            calls.append((query, params))
            return Cursor()

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Conn()

    owner = ContentTaskRunOwner(connect_read=connect)
    assert owner.list_pending(SCOPE, limit=1) == ["review-key-1"]
    query, params = calls[0]
    assert params == (*SCOPE.key, 1)
    assert "state='pending'" in query and "attempt=0" in query
    assert "extension_operation_dispatch_binding" in query
    assert "extension_runtime_binding" in query


def test_content_taskrun_worker_is_off_by_default(monkeypatch):
    monkeypatch.delenv("AOS_ECOM_CONTENT_TASKRUN_WORKER_ENABLED", raising=False)
    application = type("Application", (), {"state": type("State", (), {
        "runtime_background_tasks": [], "extension_runtime_host_status": "INACTIVE",
        "extension_runtime_host_task": None,
    })()})()
    asyncio.run(_start_content_taskrun_worker(application, asyncio.Event()))
    assert application.state.content_taskrun_worker_status == "DISABLED"
    assert application.state.runtime_background_tasks == []


def test_content_taskrun_worker_needs_active_host(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_CONTENT_TASKRUN_WORKER_ENABLED", "true")
    application = type("Application", (), {"state": type("State", (), {
        "runtime_background_tasks": [], "extension_runtime_host_status": "INACTIVE",
        "extension_runtime_host_task": None,
    })()})()
    with pytest.raises(RuntimeError, match="active Runtime Host"):
        asyncio.run(_start_content_taskrun_worker(application, asyncio.Event()))
    assert application.state.content_taskrun_worker_status == "FAILED_CLOSED"


@pytest.mark.parametrize("acknowledged,committed_readback", [(True, True), (True, False), (False, False)])
def test_claimed_content_run_uses_one_outer_commit_and_fails_closed_without_ack(
    monkeypatch, acknowledged, committed_readback
):
    token = uuid4()
    review = {"resourceType": "ReviewDecisionReceipt", "resourceId": "review-1",
              "revision": 1, "contentHash": "sha256:" + "a" * 64}
    task = {"resourceType": "Task", "resourceId": "task-1",
            "revision": 1, "contentHash": "sha256:" + "a" * 64}
    brief = {"resourceType": "TaskBriefRevision", "resourceId": "brief-1",
             "revision": 1, "contentHash": "sha256:" + "a" * 64}
    response = {"receiptRef": review, "taskRef": task, "briefRef": brief,
                "handoffRef": {**review, "resourceType": "HandoffReceipt"},
                "growthPlanRef": {**review, "resourceType": "GrowthPlanRevision"},
                "artifactBindings": [{"artifactRef": {**review, "resourceType": "ArtifactRevision"}}] * 4}
    origin = {"target_receipt_ref": review, "request_hash": "sha256:" + "b" * 64}
    events = []

    class Cursor:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class Conn:
        def execute(self, query, _params=()):
            if "FOR UPDATE" in query and "content_taskrun_intent" in query:
                return Cursor({"review_receipt_ref": review, "task_id": "task-1",
                               "brief_id": "brief-1", "origin_request_hash": origin["request_hash"],
                               "state": "claimed", "attempt": 1, "claim_token": token,
                               "plan_revision_id": None, "run_id": None})
            if "clock_timestamp()" in query:
                return Cursor({"checked_at": datetime(2026, 9, 9, tzinfo=UTC)})
            if "taskrun_ack_a0v_101" in query:
                events.append("ack")
                return Cursor({"accepted": acknowledged})
            if "FROM public.ecommerce_growth_content_taskrun_intent" in query:
                return Cursor({"state": "accepted", "attempt": 1,
                               "claim_token": token, "plan_revision_id": "plan-1", "run_id": "run-1"})
            raise AssertionError(query)

        def commit(self):
            events.append("commit")

    @contextmanager
    def connect(_scope):
        yield Conn()

    class ReadConn:
        def execute(self, query, params):
            assert "JOIN public.aip_task_run" in query
            assert params == (*SCOPE.key, "review-key-1")
            events.append("independent_readback")
            if not committed_readback:
                return Cursor(None)
            return Cursor({"state": "accepted", "attempt": 1, "claim_token": token,
                           "plan_revision_id": "plan-1", "run_id": "run-1",
                           "approval_status": "approved", "run_status": "running"})

    @contextmanager
    def connect_read(_scope):
        yield ReadConn()

    class Store:
        def __init__(self, _factory):
            pass

        def get_task(self, _scope, _task_id):
            version = 1 if "plan" not in events else 2 if "approve" not in events else 3
            return SimpleNamespace(id="task-1", status=SimpleNamespace(value="pending"),
                                   version=version, current_plan_revision_id=None)

        def create_plan(self, *_args):
            events.append("plan")
            return SimpleNamespace(id="plan-1", revision=1, content_hash="a" * 64)

        def approve_plan(self, *_args):
            events.append("approve")

        def create_run(self, *_args):
            events.append("run")
            return SimpleNamespace(id="run-1", version=1)

        def start_run(self, *_args, **_kwargs):
            events.append("start")

    monkeypatch.setattr(ContentTaskRunOwner, "_origin", staticmethod(lambda *_: (origin, response)))
    monkeypatch.setattr(owner_module.ContentGenerateHostService, "_review_receipt", staticmethod(lambda *_: response))
    monkeypatch.setattr(owner_module.ContentGenerateHostService, "_task_brief", staticmethod(lambda *_args, **_kwargs: None))
    method = SimpleNamespace(source_cutoff_at=datetime(2026, 9, 9, tzinfo=UTC))
    monkeypatch.setattr(owner_module.ReviewAdvanceHostService, "_revalidate_growth_plan", staticmethod(
        lambda **_: SimpleNamespace(sales_weapon_method=method)))
    monkeypatch.setattr(owner_module.ReviewAdvanceHostService, "_sales_weapon_task_values", staticmethod(lambda *_: {}))
    monkeypatch.setattr(owner_module.ReviewAdvanceHostService, "_require_sales_weapon_method", staticmethod(lambda **_: None))
    monkeypatch.setattr(owner_module, "AipTaskStore", Store)
    worker = ContentTaskRunOwner(connect_write=connect, connect_read=connect_read)
    if acknowledged and committed_readback:
        result = worker.execute_claim(SCOPE, "review-key-1", token)
        assert result["runId"] == "run-1"
        assert events == ["plan", "approve", "run", "start", "ack", "commit", "independent_readback"]
    elif not acknowledged:
        with pytest.raises(owner_module.ContentTaskRunConflict, match="ack unavailable"):
            worker.execute_claim(SCOPE, "review-key-1", token)
        assert events == ["plan", "approve", "run", "start", "ack"]
    else:
        with pytest.raises(owner_module.ContentTaskRunConflict, match="committed readback unknown"):
            worker.execute_claim(SCOPE, "review-key-1", token)
        assert events == ["plan", "approve", "run", "start", "ack", "commit", "independent_readback"]
