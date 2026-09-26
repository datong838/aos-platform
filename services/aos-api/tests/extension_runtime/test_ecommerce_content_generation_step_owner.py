"""A settled Provider result may complete one AIP step, never call Provider again."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_content_step_owner import (
    ContentGenerationStepOwner, ContentGenerationStepProof, ContentStepConflict,
)
from aos_api.tenant_scope import TenantScope
from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal
from aos_api.ecommerce_content_execution_composition import CurrentContentPreparation
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


def test_generation_owner_requires_current_original_installation(monkeypatch):
    monkeypatch.setattr(ContentExecutionJournal, "read", lambda *_: {
        "command": {"idempotencyKey": "content-1", "requestHash": "request-1"},
        "result": {"answer": "已生成"}})
    monkeypatch.setattr(CurrentContentPreparation, "_runtime_row",
        staticmethod(lambda *_: {"request_hash": "request-1",
            "response": {"state": "PENDING"}, "runtime_revision": 3}))
    monkeypatch.setattr(CurrentContentPreparation, "_lock_dispatch",
        staticmethod(lambda *_: SimpleNamespace(runtime_revision=4)))
    with pytest.raises(ContentStepConflict, match="installation revision"):
        ContentGenerationStepOwner._current_dispatch(object(), SCOPE, "reservation-1")


def test_generation_owner_treats_missing_independent_readback_as_unknown():
    class Conn:
        def execute(self, *_):
            return SimpleNamespace(fetchone=lambda: None)

    with pytest.raises(ContentStepConflict, match="commit/readback unknown"):
        ContentGenerationStepOwner._readback(Conn(), SCOPE, PROOF, "checkpoint-1")


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
