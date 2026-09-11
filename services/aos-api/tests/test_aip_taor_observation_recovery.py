"""Checkpoint recovery tests; optional PostgreSQL work is disposable only."""
from copy import deepcopy
import os
from types import SimpleNamespace

import pytest

from aos_api.aip_contracts import PlanStep
from aos_api.aip_taor_loop import CanonicalTaorRunner
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked, _canonical_hash
from aos_api.public_contracts import TaskStatus
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
OBSERVATION = {"decisionRef": {"resourceId": "diagnosis-exact", "revision": 1}, "artifactRefs": []}


def timeline():
    payload = {"stepRunId": "step-diagnosis", "stepKey": "diagnosis", "payload": deepcopy(OBSERVATION)}
    result = SimpleNamespace(
        task=SimpleNamespace(id="task", goal={}, status=TaskStatus.EXECUTING),
        run=SimpleNamespace(id="run", status=SimpleNamespace(value="running"), logic_graph_id=None, logic_revision=None),
        plan=SimpleNamespace(id="plan", content_hash="a" * 64, steps=[
            PlanStep(step_key="diagnosis", title="诊断"),
            PlanStep(step_key="solution-design", title="方案设计"),
        ]),
        steps=[dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id, run_id="run", step_run_id="step-diagnosis", step_key="diagnosis", status="succeeded", observe_ref={"evidenceId": "observe-1"})],
        evidence=[dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id, run_id="run", evidence_id="observe-1", evidence_type="taor.observe", content_hash=_canonical_hash(payload), payload=payload)],
    )
    result.model_dump = lambda **kwargs: {"run": {}, "plan": {"steps": [s.model_dump(by_alias=True) for s in result.plan.steps]}}
    return result


class Adapter:
    def __init__(self):
        self.contexts = {}

    def think(self, step, context):
        self.contexts[step["stepKey"]] = deepcopy(context)
        return {}

    def act(self, step, thought):
        return {}

    def verify(self, step, action):
        return {"passed": True}

    def observe(self, step, action, verification):
        return {"result": step["stepKey"], "artifacts": []}


class Store:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.claimed = []

    def timeline(self, scope, run_id):
        return self.snapshot

    def claim_step(self, scope, run_id, step_key, worker_id, **kwargs):
        self.claimed.append(step_key)
        return SimpleNamespace(step_run_id="next", fence=1)

    def record_step_phase(self, *args):
        pass

    def complete_step(self, *args):
        pass

    def complete_run(self, *args):
        return "completed"

    def fail_step(self, *args):
        raise AssertionError(args[-1])


def test_new_runner_restores_previous_result_without_reexecuting_completed_step():
    snapshot = timeline()
    store, adapter = Store(snapshot), Adapter()
    assert CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker-2", adapter=adapter) == "completed"
    assert store.claimed == ["solution-design"]
    assert adapter.contexts["solution-design"]["step:diagnosis"] == OBSERVATION
    assert snapshot.evidence[0]["payload"]["payload"] == OBSERVATION


@pytest.mark.parametrize("corrupt", [
    "missing_ref", "missing_evidence", "duplicate_evidence", "wrong_step_tenant", "wrong_evidence_tenant",
    "wrong_step_run", "wrong_evidence_run", "wrong_type", "wrong_step_id", "wrong_step_key",
    "wrong_hash", "invalid_payload", "invalid_observation", "duplicate_success", "unknown_step",
])
def test_invalid_recovery_blocks_before_any_step_claim(corrupt):
    snapshot = timeline()
    step, evidence = snapshot.steps[0], snapshot.evidence[0]
    if corrupt == "missing_ref": step["observe_ref"] = None
    elif corrupt == "missing_evidence": snapshot.evidence.clear()
    elif corrupt == "duplicate_evidence": snapshot.evidence.append(deepcopy(evidence))
    elif corrupt == "wrong_step_tenant": step["org_id"] = "dev-org"
    elif corrupt == "wrong_evidence_tenant": evidence["project_id"] = "other"
    elif corrupt == "wrong_step_run": step["run_id"] = "other"
    elif corrupt == "wrong_evidence_run": evidence["run_id"] = "other"
    elif corrupt == "wrong_type": evidence["evidence_type"] = "taor.think"
    elif corrupt == "wrong_step_id": evidence["payload"]["stepRunId"] = "other"
    elif corrupt == "wrong_step_key": evidence["payload"]["stepKey"] = "other"
    elif corrupt == "wrong_hash": evidence["content_hash"] = "b" * 64
    elif corrupt == "invalid_payload": evidence["payload"] = []
    elif corrupt == "invalid_observation": evidence["payload"]["payload"] = []
    elif corrupt == "duplicate_success": snapshot.steps.append(deepcopy(step))
    elif corrupt == "unknown_step": step["step_key"] = "not-in-plan"
    if corrupt != "wrong_hash": evidence["content_hash"] = _canonical_hash(evidence["payload"])
    store = Store(snapshot)
    with pytest.raises(AipTaskTransitionBlocked):
        CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=Adapter())
    assert store.claimed == []


def test_later_completed_step_does_not_leak_into_earlier_step_context():
    snapshot = timeline()
    snapshot.plan.steps.reverse()
    adapter = Adapter()
    CanonicalTaorRunner(Store(snapshot)).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=adapter)
    assert "step:diagnosis" not in adapter.contexts["solution-design"]


def test_adapter_mutation_cannot_change_persisted_observation():
    snapshot = timeline()
    class MutatingAdapter(Adapter):
        def think(self, step, context):
            context["step:diagnosis"]["decisionRef"]["revision"] = 999
            return {}
    CanonicalTaorRunner(Store(snapshot)).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=MutatingAdapter())
    assert snapshot.evidence[0]["payload"]["payload"] == OBSERVATION


@pytest.mark.skipif(os.environ.get("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database opt-in required")
def test_postgres_owner_completed_observation_survives_new_worker():
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
    from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest

    with disposable_database() as connect:
        store = AipTaskStore(connect_factory=connect)
        task = store.create_task(SCOPE, "tester", "resume-task", CreateTaskRequest(type="recovery-test", title="Synthetic recovery test"))
        plan = store.create_plan(SCOPE, "tester", task.id, "resume-plan", CreatePlanRevisionRequest(expected_task_version=task.version, steps=[
            PlanStep(step_key="diagnosis", title="诊断"), PlanStep(step_key="solution-design", title="方案设计")]))
        task = store.get_task(SCOPE, task.id)
        store.approve_plan(SCOPE, "tester", task.id, plan.revision, task.version, plan.content_hash)
        task = store.get_task(SCOPE, task.id)
        run = store.create_run(SCOPE, "tester", task.id, "resume-run", CreateTaskRunRequest(plan_revision_id=plan.id, expected_task_version=task.version))
        snapshot = store.timeline(SCOPE, run.id)
        store.start_run(SCOPE, run.id, expected_run_version=run.version, expected_task_version=snapshot.task.version, actor="tester", idempotency_key="resume-start", reason="synthetic recovery")
        lease = store.claim_step(SCOPE, run.id, "diagnosis", "worker-1", lease_seconds=60)
        for phase, payload in [("think", {}), ("act", {}), ("verify", {"passed": True}), ("observe", OBSERVATION)]:
            store.record_step_phase(SCOPE, lease.step_run_id, "worker-1", lease.fence, "tester", phase, payload)
        store.complete_step(SCOPE, lease.step_run_id, "worker-1", lease.fence, "tester")
        before = store.timeline(SCOPE, run.id)
        adapter = Adapter()
        result = CanonicalTaorRunner(AipTaskStore(connect_factory=connect)).run(SCOPE, run.id, actor="tester", worker_id="worker-2", adapter=adapter)
        assert result.run.status.value == "succeeded"
        assert set(adapter.contexts) == {"solution-design"}
        assert adapter.contexts["solution-design"]["step:diagnosis"] == OBSERVATION
        after = store.timeline(SCOPE, run.id)
        assert [s for s in after.steps if s["step_key"] == "diagnosis"] == before.steps
        assert len(after.steps) == 2
