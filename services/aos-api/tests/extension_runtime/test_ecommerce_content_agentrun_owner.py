"""The natural content AgentRun may only consume an exact accepted TaskRun once."""

from contextlib import contextmanager
import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import aos_api.ecommerce_content_agentrun_owner as owner_module
from aos_api.ecommerce_content_agentrun_owner import ContentAgentRunConflict, ContentAgentRunOwner
from aos_api.main import _start_content_agentrun_worker
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import ExactContractRef, PlanStep, ResourceRef
from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness
from aos_api.aip_task_store import _canonical_hash
from aos_api.ecommerce_content_taskrun_owner import ContentTaskRunOwner
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def test_build_request_binds_immutable_plan_assignment_and_published_skill(monkeypatch):
    digest = "a" * 64
    def ref(kind, identity):
        return {"resourceType": kind, "resourceId": identity, "revision": 1,
                "contentHash": "sha256:" + digest}
    response = {
        "receiptRef": ref("ReviewDecisionReceipt", "review-receipt-1"),
        "taskRef": ref("Task", "task-1"), "briefRef": ref("TaskBriefRevision", "brief-1"),
        "handoffRef": ref("HandoffReceipt", "handoff-1"),
        "growthPlanRef": ref("GrowthPlanRevision", "growth-plan-1"),
        "artifactBindings": [{"artifactRef": ref("ArtifactRevision", f"artifact-{n}")}
                             for n in range(4)],
    }
    assignment = {
        "plan_ref": ref("ResponsibilityPlanRevision", "responsibility-1"),
        "assignee": ResourceRef(resource_type="AgentInstance", resource_id="agent-1",
                                revision="1", authority="aip-assignee-directory"),
        "agent_hash": digest,
        "capabilities": [ExactContractRef(resource_type="CapabilityRevision",
                                           resource_id="copy.generate", revision=1,
                                           content_hash=digest)],
    }
    steps = [PlanStep(step_key="content_generate", title="生成", responsibility_slot_ids=["content.generate"],
                      assignee_refs=[assignment["assignee"]], capability_refs=assignment["capabilities"]),
             PlanStep(step_key="content_review", title="人工评审")]
    dependencies = [response["growthPlanRef"], response["briefRef"], assignment["plan_ref"]]
    risk = {"reviewReceiptRef": response["receiptRef"],
            "responsibilityPlanRef": assignment["plan_ref"]}
    plan = SimpleNamespace(id="plan-1", task_id="task-1", revision=1, steps=steps,
                           dependencies=dependencies, risk=risk, approval_status="approved",
                           content_hash=_canonical_hash({
                               "steps": [step.model_dump(mode="json", by_alias=True) for step in steps],
                               "dependencies": dependencies, "risk": risk,
                           }))
    timeline = SimpleNamespace(plan=plan, run=SimpleNamespace(id="run-1", task_id="task-1",
                                                               plan_revision_id="plan-1", version=2,
                                                               status=SimpleNamespace(value="running")),
                               task=SimpleNamespace(id="task-1", version=4,
                                                    status=SimpleNamespace(value="executing")), steps=[])
    route = VersionedAssetRef(asset_type="ModelRouteRevision", asset_id="route-1",
                              revision=1, content_hash=digest)
    policy = VersionedAssetRef(asset_type="RuntimePolicyRevision", asset_id="policy-1",
                               revision=1, content_hash=digest)
    skill = {
        "binding_id": "binding-1", "required_capabilities": ["copy.generate"],
        "skill_id": "skill-1", "revision": 1, "skill_hash": digest,
        "logic_revision_ref": {"assetType": "LogicRevision", "assetId": "logic-1",
                               "revision": 1, "contentHash": digest},
        "model_route_ref": route.model_dump(mode="json", by_alias=True),
        "runtime_policy_ref": policy.model_dump(mode="json", by_alias=True),
    }
    class Cursor:
        def __init__(self, row):
            self.row = row
        def fetchone(self):
            return self.row
        def fetchall(self):
            return self.row
    class Transaction:
        existing_agents = []

        def execute(self, query, _params=()):
            if "FROM public.ecommerce_growth_content_taskrun_intent p" in query:
                return Cursor({"review_receipt_ref": response["receiptRef"], "task_id": "task-1",
                               "plan_revision_id": "plan-1", "run_id": "run-1",
                               "task_run_id": "run-1", "next_plan_id": "plan-1",
                               "next_task_id": "task-1"})
            if "clock_timestamp()" in query:
                return Cursor({"checked_at": datetime(2026, 9, 26, tzinfo=UTC)})
            if "FROM public.aip_skill_binding b" in query:
                return Cursor([skill])
            if "FROM public.aip_agent_run" in query:
                return Cursor(self.existing_agents)
            raise AssertionError(query)

    method = SimpleNamespace(source_cutoff_at=datetime(2026, 9, 26, tzinfo=UTC))
    monkeypatch.setattr(ContentTaskRunOwner, "_origin", staticmethod(
        lambda *_: ({"target_receipt_ref": response["receiptRef"]}, response)))
    monkeypatch.setattr(ContentTaskRunOwner, "_assignment", staticmethod(lambda *_: assignment))
    monkeypatch.setattr(owner_module.ContentGenerateHostService, "_review_receipt", staticmethod(lambda *_: response))
    monkeypatch.setattr(owner_module.ContentGenerateHostService, "_task_brief", staticmethod(lambda *_args, **_kw: None))
    monkeypatch.setattr(owner_module.ReviewAdvanceHostService, "_revalidate_growth_plan", staticmethod(
        lambda **_: SimpleNamespace(sales_weapon_method=method)))
    monkeypatch.setattr(owner_module.ReviewAdvanceHostService, "_sales_weapon_task_values", staticmethod(lambda *_: {}))
    monkeypatch.setattr(owner_module.ReviewAdvanceHostService, "_require_sales_weapon_method", staticmethod(lambda **_: None))
    monkeypatch.setattr(owner_module, "AipTaskStore", lambda _factory: SimpleNamespace(timeline=lambda *_: timeline))
    monkeypatch.setattr(owner_module, "AipModelRuntimeStore", lambda _factory: object())
    monkeypatch.setattr(owner_module, "AipModelRuntimeResolver", lambda _store: SimpleNamespace(
        resolve=lambda *_args, **_kwargs: SimpleNamespace(
            readiness=ModelRuntimeReadiness.READY, route=route, policy=policy)))
    transaction = Transaction()
    request = ContentAgentRunOwner._build_request(HostTransaction(transaction), SCOPE, "review-1")
    assert request.run.agent_instance.asset_id == "agent-1"
    assert request.run.skill.asset_id == "skill-1"
    assert request.run.model_route == route
    assert request.task_run_ref.resource_id == "run-1"
    assert len(request.run.input_refs) == 5
    transaction.existing_agents = [{"agent_run_id": request.agent_run_id}]
    assert ContentAgentRunOwner._build_request(
        HostTransaction(transaction), SCOPE, "review-1",
        existing_agent_run_id=request.agent_run_id,
    ) == request
    with pytest.raises(ContentAgentRunConflict, match="already has an AgentRun"):
        ContentAgentRunOwner._build_request(HostTransaction(transaction), SCOPE, "review-1")


def test_selector_requires_accepted_running_content_run_in_exact_tenant():
    calls = []

    class Cursor:
        def fetchall(self):
            return [{"review_key": "review-1"}]

    class Conn:
        def execute(self, query, params):
            calls.append((query, params))
            return Cursor()

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Conn()

    owner = ContentAgentRunOwner(connect_read=connect)
    assert owner.list_pending(SCOPE, limit=1) == ["review-1"]
    query, params = calls[0]
    assert params == (*SCOPE.key, 1)
    assert "i.state='pending'" in query and "i.attempt=0" in query
    assert "p.state='accepted'" in query
    assert "r.status='running'" in query
    assert "extension_operation_dispatch_binding" in query


def test_content_agentrun_worker_is_off_by_default(monkeypatch):
    monkeypatch.delenv("AOS_ECOM_CONTENT_AGENTRUN_WORKER_ENABLED", raising=False)
    application = type("Application", (), {"state": type("State", (), {
        "runtime_background_tasks": [], "extension_runtime_host_status": "INACTIVE",
        "extension_runtime_host_task": None,
    })()})()
    asyncio.run(_start_content_agentrun_worker(application, asyncio.Event()))
    assert application.state.content_agentrun_worker_status == "DISABLED"
    assert application.state.runtime_background_tasks == []


def test_content_agentrun_worker_needs_active_host(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_CONTENT_AGENTRUN_WORKER_ENABLED", "true")
    application = type("Application", (), {"state": type("State", (), {
        "runtime_background_tasks": [], "extension_runtime_host_status": "INACTIVE",
        "extension_runtime_host_task": None,
    })()})()
    with pytest.raises(RuntimeError, match="active Runtime Host"):
        asyncio.run(_start_content_agentrun_worker(application, asyncio.Event()))
    assert application.state.content_agentrun_worker_status == "FAILED_CLOSED"


@pytest.mark.parametrize("acknowledged,committed_readback", [(True, True), (True, False), (False, False)])
def test_claimed_agentrun_uses_public_owner_and_never_commits_without_ack(
    monkeypatch, acknowledged, committed_readback
):
    token = uuid4()
    events = []
    request = SimpleNamespace(agent_run_id="content-agent-1",
                              task_run_ref=SimpleNamespace(resource_id="run-1"))

    class Cursor:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class Conn:
        def execute(self, query, params=()):
            if "FOR UPDATE" in query and "agentrun_intent" in query:
                return Cursor({"state": "claimed", "attempt": 1, "claim_token": token,
                               "task_run_id": "run-1", "agent_run_id": None})
            if "clock_timestamp()" in query:
                return Cursor({"checked_at": datetime(2026, 9, 26, tzinfo=UTC)})
            if "agentrun_ack_a0v_102" in query:
                events.append("ack")
                return Cursor({"accepted": acknowledged})
            if "capacity_put_a0v_103" in query:
                events.append("capacity_intent")
                return Cursor({"pending": True})
            raise AssertionError(query)

        def commit(self):
            events.append("commit")

    @contextmanager
    def connect_write(scope):
        assert scope == SCOPE
        yield Conn()

    class ReadConn:
        def execute(self, query, params):
            assert "aip_agent_registry_receipt" in query
            assert params == (*SCOPE.key, "review-1")
            events.append("independent_readback")
            if not committed_readback:
                return Cursor(None)
            return Cursor({"state": "accepted", "attempt": 1, "claim_token": token,
                           "agent_run_id": "content-agent-1", "agent_status": "queued",
                           "receipt_status": "applied", "next_state": "pending",
                           "next_attempt": 0})

    @contextmanager
    def connect_read(scope):
        assert scope == SCOPE
        yield ReadConn()

    class Owner:
        def __init__(self, _factory):
            pass

        def _create_in_transaction(self, _transaction, _scope, _request, **kwargs):
            assert kwargs["idempotency_key"] == "review-1"
            events.append("public_owner")
            return (SimpleNamespace(agent_run_id="content-agent-1",
                                    status=SimpleNamespace(value="queued")),
                    SimpleNamespace(operation="agent_run.create", idempotency_key="review-1",
                                    result_ref=SimpleNamespace(resource_id="content-agent-1")))

    monkeypatch.setattr(ContentAgentRunOwner, "_build_request", staticmethod(lambda *_: request))
    monkeypatch.setattr(owner_module, "AipAgentRunService", Owner)
    worker = ContentAgentRunOwner(connect_write=connect_write, connect_read=connect_read)
    if acknowledged and committed_readback:
        assert worker.execute_claim(SCOPE, "review-1", token)["agentRunId"] == "content-agent-1"
        assert events == ["public_owner", "ack", "capacity_intent", "commit", "independent_readback"]
    elif not acknowledged:
        with pytest.raises(ContentAgentRunConflict, match="ack unavailable"):
            worker.execute_claim(SCOPE, "review-1", token)
        assert events == ["public_owner", "ack"]
    else:
        with pytest.raises(ContentAgentRunConflict, match="committed readback unknown"):
            worker.execute_claim(SCOPE, "review-1", token)
        assert events == ["public_owner", "ack", "capacity_intent", "commit", "independent_readback"]
