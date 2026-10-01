"""Budget command Owner never substitutes a guessed amount or retries unknown Host commits."""

from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
import asyncio
from pathlib import Path
import sys
from uuid import uuid4

import pytest

from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 26, tzinfo=UTC)
TASK_REF = BudgetExactRef(resource_type="Task", resource_id="task-1", revision=1,
                          content_hash="sha256:" + "1" * 64)


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _ApprovalConn:
    def __init__(self, events, snapshot):
        self.events = events
        self.snapshot = snapshot

    def execute(self, query, params):
        assert params[:2] == SCOPE.key
        if "FROM public.aip_action_approval_event" in query:
            return _Cursor(self.events)
        if "FROM public.aip_action_draft" in query:
            return _Cursor([{"snapshot": self.snapshot, "proposal_hash": "2" * 64}])
        raise AssertionError(query)


def _event():
    return {
        "approval_event_id": "approval-1", "proposal_id": "proposal-1",
        "proposal_version": 1, "proposal_hash": "2" * 64,
        "decision": "approved", "actor_id": "reviewer", "reason": "OK",
        "expires_at": NOW + timedelta(hours=1), "created_at": NOW,
        "action_binding_hash": "3" * 64,
    }


def test_approval_must_be_unique_exact_and_bound_to_original_amount(monkeypatch):
    from aos_api.ecommerce_content_budget_command_owner import (
        ContentBudgetCommandOwner, ContentBudgetCommandConflict,
    )
    checked = []
    def verify(self, conn, scope, ref, checked_at, *, task_ref, operation_id, upper_bound_minor):
        checked.append((ref, task_ref, operation_id, upper_bound_minor))
    monkeypatch.setattr(
        "aos_api.aip_budget_reservation_store.AipBudgetReservationStore._approval_authority", verify,
    )
    event = _event()
    ref, amount = ContentBudgetCommandOwner._approved_action(
        _ApprovalConn([event], {"payload": {"budgetUpperBoundMinor": 500}}),
        SCOPE, TASK_REF, checked_at=NOW,
    )
    assert ref.resource_type == "ActionApprovalEvent"
    assert ref.resource_id == "approval-1"
    assert ref.revision == 1
    assert ref.content_hash == canonical_hash(event, prefixed=True)
    assert amount == 500
    assert checked == [(ref, TASK_REF, "ecommerce_growth_content_generate", 500)]
    for events, snapshot in (
        ([], {"payload": {"budgetUpperBoundMinor": 500}}),
        ([event, {**event, "approval_event_id": "approval-2"}], {"payload": {"budgetUpperBoundMinor": 500}}),
        ([event], {"payload": {}}),
        ([event], {"payload": {"budgetUpperBoundMinor": 0}}),
        ([event], {"payload": {"budgetUpperBoundMinor": True}}),
    ):
        with pytest.raises(ContentBudgetCommandConflict):
            ContentBudgetCommandOwner._approved_action(
                _ApprovalConn(events, snapshot), SCOPE, TASK_REF, checked_at=NOW,
            )


def test_pending_selector_is_bounded_scoped_and_current_only():
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner

    class Conn:
        def execute(self, query, params):
            assert "ecommerce_growth_content_budget_command_current_a0v_104" in query
            assert "state='pending'" in query and "attempt=0" in query
            assert params == (*SCOPE.key, 2)
            return _Cursor([{"review_key": "review-1"}])

    @contextmanager
    def read(scope):
        assert scope == SCOPE
        yield Conn()

    owner = ContentBudgetCommandOwner(connect_read=read)
    assert owner.list_pending(SCOPE, limit=2) == ["review-1"]
    with pytest.raises(ValueError):
        owner.list_pending(SCOPE, limit=17)


def test_host_command_envelope_matches_pluggable_bundle_contract():
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
    from aos_api.ecommerce_growth_runtime_adapters import _analysis_command_hash

    root = Path(__file__).resolve().parents[4]
    for path in (root / "packages/aos-extension-sdk/python",
                 root / "bundles/solutions/ecommerce-growth/backend"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from ecommerce_growth.content_capability_runtime import ContentCapabilityRequest
    from ecommerce_growth.sdk_ports import ExactRef

    kinds = {
        "handoff": "HandoffReceipt", "task": "Task", "brief": "TaskBriefRevision",
        "growth_plan": "GrowthPlanRevision", "agent_instance": "AgentInstanceRevision",
        "responsibility_plan": "ResponsibilityPlanRevision",
        "capability": "CapabilityRevision", "model_route": "ModelRouteRevision",
        "budget": "BudgetRevision", "pricing": "ModelPriceSnapshotRevision",
        "approval": "ActionApprovalEvent", "capacity_reservation": "CapacityReservation",
    }
    refs = {name: ExactRef(kind, name + "-1", 1, "sha256:" + "1" * 64)
            for name, kind in kinds.items()}
    sources = tuple(ExactRef("ArtifactRevision", f"artifact-{i}", 1,
                             "sha256:" + "2" * 64) for i in range(4))
    facts = (ExactRef("EvidenceBundleRevision", "facts-1", 1,
                      "sha256:" + "3" * 64),)
    request = ContentCapabilityRequest(
        **{name + "_ref": value for name, value in refs.items()},
        source_artifact_refs=sources, fact_source_refs=facts, currency="CNY",
        upper_bound_fen=500, max_input_tokens=4000, max_output_tokens=2000,
        idempotency_key="review-1",
    )
    command = ContentBudgetCommandOwner._command_envelope(
        authority_refs=request.authority_refs(),
        source_artifact_refs=request.command_payload()["sourceArtifactRefs"],
        fact_source_refs=request.command_payload()["factSourceRefs"],
        approved_fen=500, max_input_tokens=4000, max_output_tokens=2000,
        review_key="review-1",
    )
    assert {k: v for k, v in command.items() if k != "requestHash"} == request.command_payload()
    assert command["requestHash"] == _analysis_command_hash(request.command_payload())


def test_missing_budget_intent_blocks_before_any_authority_or_claim():
    from aos_api.ecommerce_content_budget_command_owner import (
        ContentBudgetCommandOwner, ContentBudgetCommandConflict,
    )

    class Conn:
        calls = 0
        def execute(self, query, params):
            self.calls += 1
            assert self.calls == 1
            assert "ecommerce_growth_content_budget_command_intent" in query
            assert params == (*SCOPE.key, "review-1")
            return _Cursor([])

    from aos_api.ecommerce_growth_host_ports import HostTransaction
    conn = Conn()
    with pytest.raises(ContentBudgetCommandConflict):
        ContentBudgetCommandOwner._build_command(
            HostTransaction(conn), SCOPE, "review-1"
        )


@pytest.mark.parametrize("risk_price", [False, True])
@pytest.mark.parametrize("before_capacity", [False, True])
def test_preflight_builds_exact_command_without_claim_or_provider(monkeypatch, risk_price, before_capacity):
    from aos_api.ecommerce_content_budget_command_owner import (
        ContentBudgetCommandOwner, ContentBudgetCommandConflict,
    )
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.aip_agent_registry_contracts import AgentRunStatus
    from aos_api.aip_model_runtime_contracts import ModelRuntimeReadiness

    install, generation, group = uuid4(), uuid4(), uuid4()
    intent = dict(state="pending", attempt=0, claim_token=None, task_run_id="run-1",
                  agent_run_id="agent-run-1", capacity_reservation_id="capacity-1",
                  command_key="review-1", installation_id=install,
                  generation=generation, execution_epoch=3)
    origin = dict(installation_id=install, generation=generation, execution_epoch=3,
                  cutover_group_id=group, cutover_group_revision=2)
    ref = lambda kind, name, digest="1": dict(
        resourceType=kind, resourceId=name, revision=1,
        contentHash="sha256:" + digest * 64,
    )
    response = dict(
        handoffRef=ref("HandoffReceipt", "handoff-1"),
        taskRef=ref("Task", "task-1"), briefRef=ref("TaskBriefRevision", "brief-1"),
        growthPlanRef=ref("GrowthPlanRevision", "growth-1"),
        artifactBindings=[{"artifactRef": ref("ArtifactRevision", f"artifact-{i}")}
                          for i in range(4)],
    )
    dispatch_row = dict(handler_kind="extension", revision=5,
                        installation_id=install, generation=generation,
                        execution_epoch=3, cutover_group_id=group,
                        cutover_group_revision=2)
    class Conn:
        def __init__(self):
            self.calls = []
        def execute(self, query, params):
            self.calls.append(query)
            if "FROM public.ecommerce_growth_content_budget_command_intent" in query or "FROM public.ecommerce_growth_content_capacity_intent" in query:
                return _Cursor([intent])
            if "content_budget_command_current_a0v_104" in query or "content_capacity_current_a0v_103" in query:
                return _Cursor([{"current": True}])
            if "FROM public.extension_operation_dispatch_binding" in query:
                return _Cursor([dispatch_row])
            if "FROM public.aip_model_capacity_pool_head" in query:
                return _Cursor([dict(token_unit_per_reservation=6000)])
            if "FROM public.aip_model_capacity_reservation" in query:
                if before_capacity: return _Cursor([])
                assert "JOIN public.aip_model_capacity_pool_revision" in query
                assert "p.model_id=%s" in query and "p.provider_id=%s" in query
                return _Cursor([dict(request_hash="6" * 64, token_units=6000,
                                     status="reserved", expires_at=NOW + timedelta(hours=1))])
            raise AssertionError(query)
    conn = Conn()
    route = SimpleNamespace(asset_id="route-1", revision=1, content_hash="2" * 64)
    price_ref = SimpleNamespace(asset_type="ModelPriceSnapshotRevision", asset_id="price-1", revision=1, content_hash="3" * 64)
    provider_ref = SimpleNamespace(asset_type="ProviderInstanceRevision", asset_id="provider-1", revision=1, content_hash="b" * 64)
    model_ref = SimpleNamespace(asset_id="model-1", revision=1, content_hash="c" * 64)
    model = SimpleNamespace(content_hash=model_ref.content_hash, provider=provider_ref,
                            price_snapshot_ref=price_ref, provider_model_id="provider-model-1")
    run_request = SimpleNamespace(model_route=route)
    request = SimpleNamespace(task_run_ref=SimpleNamespace(resource_id="run-1"), run=run_request,
                              agent_run_id="agent-run-1", skill_binding_id="skill-binding-1")
    monkeypatch.setattr("aos_api.ecommerce_content_taskrun_owner.ContentTaskRunOwner._origin",
                        staticmethod(lambda *_: (origin, response)))
    monkeypatch.setattr("aos_api.ecommerce_content_agentrun_owner.ContentAgentRunOwner._build_request",
                        staticmethod(lambda *_, **__: request))
    monkeypatch.setattr("aos_api.ecommerce_content_taskrun_owner.ContentTaskRunOwner._assignment",
                        staticmethod(lambda *_: dict(
                            assignee=SimpleNamespace(resource_id="agent-1", revision="1"),
                            agent_hash="4" * 64,
                            plan_ref=ref("ResponsibilityPlanRevision", "responsibility-1"),
                            capabilities=[SimpleNamespace(resource_id="copy.generate", revision=1,
                                                           content_hash="5" * 64)],
                        )))
    monkeypatch.setattr("aos_api.ecommerce_growth_host_ports.LockedEcommerceGrowthHostPort._lock_and_revalidate",
                        staticmethod(lambda *_: SimpleNamespace(checked_at=NOW)))
    monkeypatch.setattr("aos_api.aip_agent_run_service.AipAgentRunService.get",
                        lambda *_, **__: SimpleNamespace(
                            status=AgentRunStatus.QUEUED if before_capacity else AgentRunStatus.RUNNING,
                            version=1, skill_binding_id="skill-binding-1", task_run_id="run-1", request=run_request))
    class ModelStore:
        def __init__(self, *_): pass
        def get_policy(self, *_):
            return SimpleNamespace(
                quota_policy_ref=SimpleNamespace(asset_id="quota-1", revision=1),
                budget_policy_ref=SimpleNamespace(asset_id="budget-policy-1", revision=1))
        def get_price_snapshot(self, *_):
            return SimpleNamespace(development_cost_authorization=object() if risk_price else None,
                                   input_token_price=0.5, output_token_price=1.0,
                                   token_unit=1000)
        def get_model(self, scope, identifier, revision):
            assert risk_price and scope == SCOPE and (identifier, revision) == ("model-1", 1)
            return model
    monkeypatch.setattr("aos_api.ecommerce_content_budget_command_owner.AipModelRuntimeStore", ModelStore)
    class Resolver:
        def __init__(self, *_): pass
        def resolve(self, *_ , **__):
            return SimpleNamespace(readiness=ModelRuntimeReadiness.READY,
                                   route=route, selected_price_snapshot=price_ref,
                                   selected_provider=provider_ref, selected_model=model_ref,
                                   policy=SimpleNamespace(asset_id="policy-1", revision=1))
    monkeypatch.setattr("aos_api.ecommerce_content_budget_command_owner.AipModelRuntimeResolver", Resolver)
    class Governance:
        def __init__(self, *_): pass
        def require_exact_active(self, scope, policy_ref, *, now):
            if policy_ref.asset_id == "quota-1":
                return SimpleNamespace(max_input_tokens=4000, max_output_tokens=2000)
            return SimpleNamespace(budget_revision_ref=SimpleNamespace(
                asset_type="BudgetRevision", asset_id="budget-1", revision=1, content_hash="7" * 64))
    monkeypatch.setattr("aos_api.ecommerce_content_budget_command_owner.AipModelGovernancePolicyStore", Governance)
    approval_reads = []
    def approved_action(*args, **kwargs):
        approval_reads.append((args, kwargs))
        return (BudgetExactRef(resource_type="ActionApprovalEvent",
                               resource_id="approval-1", revision=1,
                               content_hash="sha256:" + "8" * 64), 500)
    monkeypatch.setattr(ContentBudgetCommandOwner, "_approved_action", staticmethod(approved_action))
    monkeypatch.setattr("aos_api.ecommerce_growth_runtime_adapters.ReviewAdvanceHostService._revalidate_growth_plan",
                        staticmethod(lambda **__: SimpleNamespace(sales_weapon_method=SimpleNamespace(
                            evidence_refs=[SimpleNamespace(resource_id="facts-1", revision=1,
                                                           content_hash="9" * 64)]))))
    validated = []
    monkeypatch.setattr("aos_api.ecommerce_growth_runtime_adapters.ContentGenerateHostService.revalidate",
                        lambda self, **kwargs: validated.append(kwargs["command"]))
    if risk_price:
        # Wiring-only double. The real shared authority is exercised by the PG suite.
        def approve_bound(cls, price, amount, **options):
            assert type(options["transaction"]) is HostTransaction and options["scope"] == SCOPE
            assert options["policy_ref"].resource_id == "budget-1"
            assert options["pricing_ref"].content_hash == "sha256:" + "3" * 64
            assert options["provider_ref"].resource_id == "provider-1"
            assert options["provider_model_id"] == "provider-model-1"
            assert options["max_input_tokens"] == 4000 and options["max_output_tokens"] == 2000
            assert price.development_cost_authorization is not None
            return amount
        monkeypatch.setattr(ContentBudgetCommandOwner, "_approved_bound", classmethod(approve_bound))
    sources = ContentBudgetCommandOwner._prepare_sources(HostTransaction(conn), SCOPE, "review-1",
                                                         before_capacity=before_capacity)
    if before_capacity:
        assert sources.action_context.capacity is None
        assert "capacity_reservation" not in sources.authorities
        assert approval_reads == [] and validated == []
        intent["state"], intent["attempt"], intent["claim_token"] = "unknown", 1, uuid4()
        with pytest.raises(ContentBudgetCommandConflict, match="origin unavailable"):
            ContentBudgetCommandOwner._prepare_sources(HostTransaction(conn), SCOPE, "review-1", before_capacity=True)
        return
    assert approval_reads == [] and validated == []
    assert "approval" not in sources.authorities
    assert sources.task_ref.resource_id == "task-1"
    assert sources.authorities["capacity_reservation"]["resourceId"] == "capacity-1"
    assert not any("_claim_a0v_104" in query for query in conn.calls)
    dispatch, command = ContentBudgetCommandOwner._build_command(
        HostTransaction(conn), SCOPE, "review-1"
    )
    assert dispatch.execution_epoch == 3 and dispatch.installation_id == install
    assert command["authorityRefs"]["budget"]["resourceId"] == "budget-1"
    assert command["authorityRefs"]["capacity_reservation"]["resourceId"] == "capacity-1"
    assert command["upperBoundFen"] == 500 and validated == [command]
    assert len(approval_reads) == 1
    assert {k: v for k, v in command["authorityRefs"].items() if k != "approval"} == sources.authorities
    assert command["sourceArtifactRefs"] == sources.source_artifact_refs
    assert command["factSourceRefs"] == sources.fact_source_refs
    assert not any("_claim_a0v_104" in query for query in conn.calls)

    if risk_price:
        model.content_hash = "d" * 64
        with pytest.raises(ContentBudgetCommandConflict, match="model/provider/price drifted"):
            ContentBudgetCommandOwner._build_command(HostTransaction(Conn()), SCOPE, "review-1")
        model.content_hash = model_ref.content_hash

    intent["execution_epoch"] = 4
    with pytest.raises(ContentBudgetCommandConflict, match="installation lineage"):
        ContentBudgetCommandOwner._build_command(HostTransaction(Conn()), SCOPE, "review-1")


def test_claim_is_once_only_after_full_preflight_and_independent_readback(monkeypatch):
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner

    class WriteConn:
        def __init__(self): self.commits = 0; self.claims = 0
        def execute(self, query, params):
            assert "content_budget_command_claim_a0v_104" in query
            self.claims += 1
            return _Cursor([{"claimed": True}])
        def commit(self): self.commits += 1
    class ReadConn:
        def execute(self, query, params):
            assert "ecommerce_growth_content_budget_command_intent" in query
            return _Cursor([dict(state="claimed", attempt=1, claim_token=token)])
    token = uuid4()
    write = WriteConn()
    @contextmanager
    def connect_write(scope):
        assert scope == SCOPE
        yield write
    @contextmanager
    def connect_read(scope):
        assert scope == SCOPE
        yield ReadConn()
    prepared = []
    monkeypatch.setattr(ContentBudgetCommandOwner, "_build_command", classmethod(
        lambda cls, transaction, scope, key, **kwargs: prepared.append(key) or (object(), {})))
    owner = ContentBudgetCommandOwner(connect_write=connect_write, connect_read=connect_read)
    assert owner.claim(SCOPE, "review-1", token=token) == token
    assert prepared == ["review-1"] and write.claims == 1 and write.commits == 1


def test_claimed_command_commits_once_then_acks_only_after_independent_readback(monkeypatch):
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner

    token, reservation = uuid4(), uuid4()
    command = {"requestHash": "sha256:" + "a" * 64,
               "idempotencyKey": "review-1"}
    dispatch = SimpleNamespace(org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                               installation_id=uuid4(), generation=uuid4(), execution_epoch=3)
    events = []
    class Conn:
        def execute(self, query, params):
            assert "content_budget_command_ack_a0v_104" in query
            events.append("ack")
            assert params == ("review-1", token, reservation)
            return _Cursor([{"accepted": True}])
        def commit(self): events.append("ack-commit")
    @contextmanager
    def write(scope):
        assert scope == SCOPE
        yield Conn()
    class ReadConn:
        def execute(self, query, params):
            assert "content_budget_command_intent" in query
            events.append("final-read")
            return _Cursor([dict(state="accepted", attempt=1, claim_token=token,
                                 budget_reservation_id=reservation)])
    @contextmanager
    def read(scope):
        assert scope == SCOPE
        yield ReadConn()
    owner = ContentBudgetCommandOwner(connect_write=write, connect_read=read)
    monkeypatch.setattr(ContentBudgetCommandOwner, "_build_command", classmethod(
        lambda cls, transaction, scope, key, *, claimed_token: (dispatch, command)))
    class Port:
        def commit(self, *, dispatch_ref, command, occurred_at):
            events.append("host-commit")
            return {"state": "PENDING"}
    monkeypatch.setattr(owner, "_capability_port", lambda: Port())
    monkeypatch.setattr(owner, "_committed_readback", lambda *args, **kwargs:
                        events.append("receipt-read") or reservation)
    assert owner.execute_claim(SCOPE, "review-1", token)["status"] == "CONTENT_BUDGET_PENDING"
    assert events == ["host-commit", "receipt-read", "ack", "ack-commit", "final-read"]


def test_unknown_host_commit_leaves_claimed_without_ack(monkeypatch):
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
    token = uuid4()
    owner = ContentBudgetCommandOwner()
    monkeypatch.setattr(ContentBudgetCommandOwner, "_build_command", classmethod(
        lambda cls, transaction, scope, key, *, claimed_token: (object(), {})))
    @contextmanager
    def write(scope):
        yield object()
    owner._connect_write = write
    class Port:
        def commit(self, **kwargs):
            raise TimeoutError("commit outcome unknown")
    monkeypatch.setattr(owner, "_capability_port", lambda: Port())
    with pytest.raises(TimeoutError, match="unknown"):
        owner.execute_claim(SCOPE, "review-1", token)


def test_incomplete_postcommit_readback_never_acks_or_resends(monkeypatch):
    from aos_api.ecommerce_content_budget_command_owner import (
        ContentBudgetCommandOwner, ContentBudgetCommandConflict,
    )
    token = uuid4()
    events = []
    owner = ContentBudgetCommandOwner()
    monkeypatch.setattr(ContentBudgetCommandOwner, "_build_command", classmethod(
        lambda cls, transaction, scope, key, *, claimed_token: (object(), {})))
    @contextmanager
    def write(scope):
        events.append("preflight")
        yield object()
    owner._connect_write = write
    class Port:
        def commit(self, **kwargs):
            events.append("commit")
            return {"state": "PENDING"}
    monkeypatch.setattr(owner, "_capability_port", lambda: Port())
    monkeypatch.setattr(owner, "_committed_readback", lambda *args, **kwargs:
                        (_ for _ in ()).throw(ContentBudgetCommandConflict("readback unknown")))
    with pytest.raises(ContentBudgetCommandConflict, match="readback unknown"):
        owner.execute_claim(SCOPE, "review-1", token)
    assert events == ["preflight", "commit"]


def test_independent_readback_requires_exact_held_journal_runtime_triplet(monkeypatch):
    from aos_api.ecommerce_content_budget_command_owner import (
        ContentBudgetCommandOwner, ContentBudgetCommandConflict,
    )
    from aos_api.ecommerce_growth_runtime_adapters import _request_hash
    reservation, installation, generation = uuid4(), uuid4(), uuid4()
    command = {"requestHash": "sha256:" + "a" * 64,
               "idempotencyKey": "review-1", "authorityRefs": {"task": {"resourceId": "task-1"}}}
    full_hash = _request_hash(command)
    target = {"resourceType": "ContentExecutionReceipt", "resourceId": "receipt-1",
              "revision": 1, "contentHash": "sha256:" + "c" * 64}
    response = {"state": "PENDING", "budgetState": "HELD",
                "requestHash": command["requestHash"], "authorityRefs": command["authorityRefs"],
                "receiptRef": target, "budgetReservationRef": {"resourceId": str(reservation)},
                "providerRequestReceiptRef": None,
                "sideEffects": {"providerInvocationCount": 0}}
    row = dict(reservation_id=reservation, budget_request_hash="b" * 64,
               budget_state="held", journal_budget_hash="b" * 64,
               command_hash=full_hash.removeprefix("sha256:"), command_payload=command,
               runtime_hash=full_hash, response=response, target_receipt_ref=target,
               installation_id=installation, generation=generation, execution_epoch=3)
    class Conn:
        def execute(self, query, params):
            assert "aip_budget_reservation" in query and "ecommerce_content_execution_command" in query
            assert params == (*SCOPE.key, "review-1")
            return _Cursor([row])
    @contextmanager
    def read(scope):
        assert scope == SCOPE
        yield Conn()
    monkeypatch.setattr(
        "aos_api.ecommerce_growth_runtime_adapters.ContentGenerateHostService._budget_request",
        staticmethod(lambda *_: SimpleNamespace(request_hash=lambda: "b" * 64)),
    )
    owner = ContentBudgetCommandOwner(connect_read=read)
    dispatch = SimpleNamespace(installation_id=installation, generation=generation,
                               execution_epoch=3)
    assert owner._committed_readback(SCOPE, "review-1", dispatch, command, response) == reservation
    row["runtime_hash"] = command["requestHash"]
    with pytest.raises(ContentBudgetCommandConflict):
        owner._committed_readback(SCOPE, "review-1", dispatch, command, response)


def test_budget_command_worker_is_off_by_default_and_requires_runtime_host(monkeypatch):
    from aos_api.main import _start_content_budget_command_worker
    monkeypatch.delenv("AOS_ECOM_CONTENT_BUDGET_COMMAND_WORKER_ENABLED", raising=False)
    application = SimpleNamespace(state=SimpleNamespace())
    asyncio.run(_start_content_budget_command_worker(application, asyncio.Event()))
    assert application.state.content_budget_command_worker_status == "DISABLED"
    monkeypatch.setenv("AOS_ECOM_CONTENT_BUDGET_COMMAND_WORKER_ENABLED", "true")
    application = SimpleNamespace(state=SimpleNamespace(extension_runtime_host_status="INACTIVE"))
    with pytest.raises(RuntimeError, match="active Runtime Host"):
        asyncio.run(_start_content_budget_command_worker(application, asyncio.Event()))
    assert application.state.content_budget_command_worker_status == "FAILED_CLOSED"


def test_pricing_bound_uses_exact_token_unit_and_requires_approved_cover():
    from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner

    price = SimpleNamespace(input_token_price=0.5, output_token_price=1.0,
                            token_unit=1000, development_cost_authorization=None)
    assert ContentBudgetCommandOwner._minimum_bound_fen(
        price, max_input_tokens=4000, max_output_tokens=2000) == 400
    assert ContentBudgetCommandOwner._approved_bound(
        price, 500, max_input_tokens=4000, max_output_tokens=2000) == 500
    with pytest.raises(ValueError, match="approved upper bound"):
        ContentBudgetCommandOwner._approved_bound(
            price, 399, max_input_tokens=4000, max_output_tokens=2000)
    with pytest.raises(ValueError, match="price"):
        ContentBudgetCommandOwner._minimum_bound_fen(
            SimpleNamespace(input_token_price=None, output_token_price=1.0,
                            token_unit=1000, development_cost_authorization=None),
            max_input_tokens=4000, max_output_tokens=2000)
