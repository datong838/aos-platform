"""A settled Provider result may complete one AIP step, never call Provider again."""

from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_content_step_owner import (
    ContentGenerationStepOwner, ContentGenerationStepProof, ContentStepConflict,
    ContentStepUnknown,
)
from aos_api.tenant_scope import TenantScope
from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal
from aos_api.ecommerce_content_execution_journal import ContentExecutionConflict
from aos_api.ecommerce_content_execution_composition import CurrentContentPreparation
from aos_api.ecommerce_growth_runtime_adapters import _request_hash
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
from test_ecommerce_analyst_method_authority import apply_migrations


SCOPE = TenantScope("org-org", "dev-project")
PROOF = ContentGenerationStepProof(
    reservation_id="reservation-1", run_id="run-1", task_id="task-1",
    artifact_id="artifact-1", artifact_hash="a" * 64,
    provider_receipt_ref={"resourceType": "ProviderReceipt", "resourceId": "provider-1"},
    usage_receipt_refs=({"resourceType": "UsageReceipt", "resourceId": "usage-1"},
                        {"resourceType": "UsageReceipt", "resourceId": "usage-2"}),
)


def test_generation_owner_completes_one_canonical_step_without_provider_call(monkeypatch):
    calls = []

    class Store:
        def claim_step(self, scope, run_id, step_key, worker_id, *, lease_seconds):
            calls.append(("claim", scope, run_id, step_key, worker_id, lease_seconds))
            return SimpleNamespace(step_run_id="step-1", fence=1)

        def record_step_phase(self, scope, step_id, worker, fence, actor, phase, payload):
            calls.append((phase, payload))

        def complete_step(self, scope, step_id, worker, fence, actor):
            calls.append(("complete", step_id))
            return "checkpoint-1"

    class Conn:
        def execute(self, *_):
            return SimpleNamespace(fetchone=lambda: None)

    owner = ContentGenerationStepOwner(store_factory=lambda *_: Store())
    result = owner._complete_transaction(Conn(), SCOPE, PROOF)
    assert result == "checkpoint-1"
    assert [item[0] for item in calls] == ["claim", "think", "act", "verify", "observe", "complete"]
    assert calls[2][1]["providerReceiptRef"] == PROOF.provider_receipt_ref
    assert calls[4][1]["artifactRef"]["resourceId"] == PROOF.artifact_id


def test_generation_owner_never_claims_existing_unknown_step():
    class Conn:
        def execute(self, *_):
            return SimpleNamespace(fetchone=lambda: {"status": "unknown"})

    owner = ContentGenerationStepOwner(store_factory=lambda *_: pytest.fail("must not claim"))
    with pytest.raises(ContentStepConflict, match="existing"):
        owner._complete_transaction(Conn(), SCOPE, PROOF)


@pytest.mark.parametrize('status,attempt,lease', [
    ('queued', 1, None), ('queued', 2, 'other-worker'),
    ('running', 2, None), ('failed', 2, None), ('unknown', 2, None),
])
def test_generation_owner_only_admits_unclaimed_return_queue(status, attempt, lease):
    class Conn:
        def execute(self, *_):
            return SimpleNamespace(fetchone=lambda: dict(step_run_id='repair-step', status=status, attempt=attempt, lease_owner=lease))
    owner = ContentGenerationStepOwner(store_factory=lambda *_: pytest.fail('unqualified queue must not claim'))
    with pytest.raises(ContentStepConflict, match='existing'):
        owner._complete_transaction(Conn(), SCOPE, PROOF)


@pytest.mark.parametrize('field,value', [('run_id', 'other-run'), ('step_run_id', 'other-step'), ('attempt', 3)])
def test_repair_owner_rejects_other_run_step_or_attempt_before_claim(monkeypatch, field, value):
    from test_ecommerce_content_generate_handoff_lineage import return_command
    command, _ = return_command()
    proof = replace(PROOF, task_id=command['authorityRefs']['task']['resourceId'])
    monkeypatch.setattr(ContentExecutionJournal, 'read', lambda *_: {'command': command})
    row = dict(run_id=proof.run_id, step_run_id='repair-step', attempt=2)
    row[field] = value
    class Conn:
        def execute(self, query, params):
            assert params == (*SCOPE.key, command['returnDecisionRef']['resourceId'])
            return SimpleNamespace(fetchone=lambda: row)
    owner = ContentGenerationStepOwner()
    monkeypatch.setattr(owner, '_current_dispatch', lambda *_: pytest.fail('drifted attempt cannot reach dispatch'))
    with pytest.raises(ContentStepConflict, match='queued attempt drifted'):
        owner._repair_attempt(Conn(), SCOPE, proof, dict(step_run_id='repair-step', attempt=2))


def test_repair_owner_requires_original_host_current_authority(monkeypatch):
    from test_ecommerce_content_generate_handoff_lineage import return_command
    from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
    command, _ = return_command()
    proof = replace(PROOF, task_id=command['authorityRefs']['task']['resourceId'])
    monkeypatch.setattr(ContentExecutionJournal, 'read', lambda *_: {'command': command})
    class Conn:
        def execute(self, *_):
            return SimpleNamespace(fetchone=lambda: dict(run_id=proof.run_id, step_run_id='repair-step', attempt=2))
    owner = ContentGenerationStepOwner()
    dispatch = object()
    monkeypatch.setattr(owner, '_current_dispatch', lambda *_: dispatch)
    checked = []
    monkeypatch.setattr(ContentGenerateHostService, '_return_authority', staticmethod(lambda *a, **kw: checked.append((a, kw))))
    owner._repair_attempt(Conn(), SCOPE, proof, dict(step_run_id='repair-step', attempt=2))
    assert len(checked) == 1 and checked[0][0][2] == command
    assert checked[0][1]['dispatch'] is dispatch


@pytest.mark.parametrize('error', [ValueError('expired approval'), ContentStepConflict('current input drifted')])
def test_repair_owner_blocks_current_authority_failure_without_claim(monkeypatch, error):
    class Conn:
        def execute(self, *_):
            return SimpleNamespace(fetchone=lambda: dict(step_run_id='repair-step', status='queued', attempt=2, lease_owner=None))
    owner = ContentGenerationStepOwner(store_factory=lambda *_: pytest.fail('authority rejected; must not claim'))
    monkeypatch.setattr(owner, '_repair_attempt', lambda *_: (_ for _ in ()).throw(error))
    with pytest.raises(ContentStepConflict):
        owner._complete_transaction(Conn(), SCOPE, PROOF)


def test_generation_owner_requires_current_original_installation(monkeypatch):
    command = {"idempotencyKey": "content-1", "requestHash": "sha256:" + "a" * 64}
    monkeypatch.setattr(ContentExecutionJournal, "read", lambda *_: {
        "command": command,
        "result": {"answer": "已生成"}})
    monkeypatch.setattr(CurrentContentPreparation, "_runtime_row",
        staticmethod(lambda *_: {"request_hash": _request_hash(command),
            "response": {"state": "PENDING"}, "runtime_revision": 3}))
    monkeypatch.setattr(CurrentContentPreparation, "_lock_dispatch",
        staticmethod(lambda *_: SimpleNamespace(runtime_revision=4)))
    with pytest.raises(ContentStepConflict, match="installation revision"):
        ContentGenerationStepOwner._current_dispatch(object(), SCOPE, "reservation-1")


def test_generation_owner_treats_missing_independent_readback_as_unknown():
    class Conn:
        def execute(self, *_):
            return SimpleNamespace(fetchone=lambda: None)

    with pytest.raises(ContentStepUnknown, match="commit/readback unknown"):
        ContentGenerationStepOwner._readback(Conn(), SCOPE, PROOF, "checkpoint-1")


def test_generation_selector_is_bounded_and_only_picks_unmaterialized_settled_results():
    captured = []

    class Conn:
        def execute(self, query, params):
            captured.append((query, params))
            return SimpleNamespace(fetchall=lambda: [{"reservation_id": "reservation-1"}])

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Conn()

    owner = ContentGenerationStepOwner(connect_read=connect)
    assert owner.list_pending(SCOPE, limit=3) == ["reservation-1"]
    query, params = captured[0]
    assert params == (*SCOPE.key, 3)
    assert "b.state='settled'" in query
    assert "ecommerce_content_execution_result" in query
    assert "aip_step_run" in query
    assert "NOT EXISTS" in query
    assert "decision.decision_id=command.command_payload->'returnDecisionRef'->>'resourceId'" in query
    assert "decision.attempt_idempotency_key=command.command_payload->>'idempotencyKey'" in query
    assert "step.status='queued' AND step.attempt>=2" in query
    with pytest.raises(ValueError):
        owner.list_pending(SCOPE, limit=0)


def test_generation_runner_isolates_known_blocker_but_stops_on_unknown():
    owner = ContentGenerationStepOwner()
    owner.list_pending = lambda *_args, **_kwargs: ["one", "two"]
    owner.run_one = lambda _scope, value: (_ for _ in ()).throw(
        ContentStepConflict("known")) if value == "one" else {"status": "GENERATION_STEP_SUCCEEDED"}
    assert owner.run_once(SCOPE) == [
        {"reservationId": "one", "status": "BLOCKED_CURRENT_AUTHORITY"},
        {"reservationId": "two", "status": "GENERATION_STEP_SUCCEEDED"},
    ]
    owner.run_one = lambda *_: (_ for _ in ()).throw(ContentStepUnknown("unknown"))
    with pytest.raises(ContentStepUnknown):
        owner.run_once(SCOPE)
    owner.run_one = lambda *_: (_ for _ in ()).throw(ContentExecutionConflict("bad receipt"))
    assert all(item["status"] == "BLOCKED_CURRENT_AUTHORITY" for item in owner.run_once(SCOPE))


def test_generation_owner_persists_one_step_and_checkpoint_in_isolated_database(monkeypatch):
    with disposable_database() as connect:
        apply_migrations(connect)
        store = AipTaskStore(connect)
        task = store.create_task(SCOPE, "tester", "step-task", CreateTaskRequest(
            type="analysis", title="Content step"))
        plan = store.create_plan(SCOPE, "tester", task.id, "step-plan",
            CreatePlanRevisionRequest(expected_task_version=task.version, steps=[
                PlanStep(step_key="content_generate", title="Generate"),
                PlanStep(step_key="content_review", title="Review"),
            ]))
        task = store.get_task(SCOPE, task.id)
        store.approve_plan(SCOPE, "tester", task.id, plan.revision,
                           task.version, plan.content_hash)
        task = store.get_task(SCOPE, task.id)
        run = store.create_run(SCOPE, "tester", task.id, "step-run",
            CreateTaskRunRequest(plan_revision_id=plan.id,
                                 expected_task_version=task.version))
        store.start_run(SCOPE, run.id, expected_run_version=run.version,
                        expected_task_version=store.timeline(SCOPE, run.id).task.version,
                        actor="tester", idempotency_key="step-start")
        proof = ContentGenerationStepProof(**{**PROOF.__dict__, "run_id": run.id,
            "task_id": task.id})
        owner = ContentGenerationStepOwner(
            source=SimpleNamespace(read=lambda *_: proof),
            connect_write=connect, connect_read=connect)
        monkeypatch.setattr(owner, "_current_dispatch", lambda *_: None)
        first = owner.run_one(SCOPE, proof.reservation_id)
        second = owner.run_one(SCOPE, proof.reservation_id)
        assert first == second
        assert first["status"] == "GENERATION_STEP_SUCCEEDED"
        with connect(SCOPE) as conn:
            steps = conn.execute(
                "SELECT step_run_id,status FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (*SCOPE.key, run.id)).fetchall()
            assert steps == [{"step_run_id": first["stepRunId"], "status": "succeeded"}]
