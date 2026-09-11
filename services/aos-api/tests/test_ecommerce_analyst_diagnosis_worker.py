from datetime import timedelta
import os

import pytest

from aos_api.aip_task_store import AipTaskTransitionBlocked, _canonical_hash
from aos_api.ecommerce_analyst_diagnosis_worker import DiagnosisTaorWorker, diagnosis_stage_attempt_id, require_diagnosis_stage_lineage
from aos_api.ecommerce_analyst_diagnosis_service import DiagnosisGenerationCommand
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from test_ecommerce_analyst_growth_plan_worker import lineage as growth_lineage
from test_ecommerce_analyst_diagnosis_generation import fixture
from test_aip_taor_observation_recovery import SCOPE


def lineage():
    snapshot, run, _ = growth_lineage()
    snapshot.plan.steps[1].assignee_refs = snapshot.plan.steps[-1].assignee_refs
    snapshot.plan.steps[-1].assignee_refs = []
    snapshot.plan.content_hash = _canonical_hash({"steps": [x.model_dump(mode="json", by_alias=True) for x in snapshot.plan.steps], "dependencies": [], "risk": {}})
    snapshot.steps = [dict(step_key="portrait", status="succeeded")]
    run.request.skill.asset_id = "ecommerce.skill.D02"
    insight, materials, attempt, _ = fixture()
    command = DiagnosisGenerationCommand(expectedAgentRunVersion=attempt.agent_run_version, attemptId=diagnosis_stage_attempt_id(SCOPE, snapshot),
        attemptNo=1, budgetRef=attempt.budget_ref, capacityReservationRef=attempt.capacity_reservation_ref, dataClassification="internal",
        insightRef=dict(resourceType="InsightRevision", resourceId=insight.insight_id, revision=1, contentHash=insight.content_hash),
        sourceRequests=[dict(bundleRef=materials[0]["bundleRef"], grants=[dict(decisionId="grant", request=dict(
            evidenceRef=materials[0]["items"][0]["evidenceRef"], purpose="source", requestedLevel="l3", taskId="task"))])])
    return snapshot, run, command


def test_exact_diagnosis_assignee_and_stable_attempt_are_accepted():
    snapshot, run, command = lineage()
    require_diagnosis_stage_lineage(SCOPE, snapshot, run, command)


@pytest.mark.parametrize("drift", ["tenant", "task", "run", "plan", "plan_revision", "plan_hash", "approval", "order", "predecessor", "already_done", "assignee", "instance", "skill", "attempt", "attempt_no"])
def test_diagnosis_lineage_drift_is_rejected(drift):
    snapshot, run, command = lineage()
    if drift == "tenant": run.tenant.org_id = "dev-org"
    elif drift == "task": run.task_id = "other"
    elif drift == "run": run.task_run_id = "other"
    elif drift == "plan": run.request.plan_ref.resource_id = "other"
    elif drift == "plan_revision": run.request.plan_ref.revision = "2"
    elif drift == "plan_hash": snapshot.plan.content_hash = "b" * 64
    elif drift == "approval": snapshot.plan.approval_status = "draft"
    elif drift == "order": snapshot.plan.steps.reverse()
    elif drift == "predecessor": snapshot.steps.clear()
    elif drift == "already_done": snapshot.steps.append(dict(step_key="diagnosis", status="succeeded"))
    elif drift == "assignee": run.instance_id = "other"
    elif drift == "instance": run.instance_version += 1
    elif drift == "skill": run.request.skill.asset_id = "ecommerce.skill.D03"
    elif drift == "attempt": command.attempt_id = "new-attempt"
    else: command.attempt_no = 2
    with pytest.raises(AipTaskTransitionBlocked): require_diagnosis_stage_lineage(SCOPE, snapshot, run, command)


@pytest.mark.skipif(os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database opt-in required")
@pytest.mark.parametrize("outcome", ["success", "wrong_portrait", "unknown"])
def test_real_diagnosis_checkpoint_does_not_claim_solution_design(outcome):
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
    from test_ecommerce_analyst_diagnosis_receiver import seed_diagnosis_graph
    from aos_api.aip_task_store import AipTaskStore
    from aos_api.aip_agent_run_service import AipAgentRunService
    from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
    from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore
    class NoProvider:
        retains_output_text = True
        def execute(self, *args, **kwargs): raise AssertionError("retained successful answer must not invoke Provider")
    with disposable_database() as connect:
        kwargs = seed_diagnosis_graph(connect, taor_ready=True)
        attempt = AipAgentRunExecutionService(connect).get(SCOPE, kwargs["attempt_id"])
        run = AipAgentRunService(connect).get(SCOPE, attempt.agent_run_id)
        command = DiagnosisGenerationCommand(expectedAgentRunVersion=attempt.agent_run_version, attemptId=attempt.attempt_id,
            attemptNo=attempt.attempt_no, budgetRef=attempt.budget_ref, capacityReservationRef=attempt.capacity_reservation_ref,
            insightRef=kwargs["insight_ref"], sourceRequests=kwargs["source_requests"], dataClassification=attempt.data_classification)
        store = AipTaskStore(connect_factory=connect)
        observation = {"insightRef": command.insight_ref.model_dump(mode="json", by_alias=True)}
        if outcome == "wrong_portrait": observation["insightRef"]["contentHash"] = "d" * 64
        lease = store.claim_step(SCOPE, run.task_run_id, "portrait", "prior", lease_seconds=60)
        for phase, payload in [("think", {}), ("act", {}), ("verify", {"passed": True}), ("observe", observation)]:
            store.record_step_phase(SCOPE, lease.step_run_id, "prior", lease.fence, "compiler", phase, payload)
        store.complete_step(SCOPE, lease.step_run_id, "prior", lease.fence, "compiler")
        worker = DiagnosisTaorWorker(connect, NoProvider())
        if outcome == "unknown":
            def blocked(*args, **kwargs): raise ValueError("unknown model outcome")
            worker._generation.generate = blocked
        def call():
            return worker.run(SCOPE, run.task_run_id, run.agent_run_id, command, actor="compiler", worker_id="diagnosis-worker",
                markings=kwargs["markings"], clock=lambda: kwargs["now"], max_source_age=timedelta(days=1), max_bytes=10000, lease_seconds=10)
        if outcome == "success": assert call().run.status.value == "running"
        else:
            with pytest.raises(AipTaskTransitionBlocked): call()
        after = store.timeline(SCOPE, run.task_run_id)
        assert after.run.status.value == "running"
        assert all(row["step_key"] != "solution-design" for row in after.steps)
        observations = [row["payload"]["payload"] for row in after.evidence if row["evidence_type"] == "taor.observe" and row["payload"]["stepKey"] == "diagnosis"]
        if outcome == "success":
            assert len(after.checkpoints) == 2 and len(after.artifacts) == 1 and len(observations) == 1
            ref = AnalystExactRef.model_validate(observations[0]["decisionRef"])
            saved = EcommerceAnalystAuthorityStore(connect).get_decision_exact(SCOPE, ref)
            assert saved.insight_ref == command.insight_ref and observations[0]["artifacts"] == []
            with pytest.raises(AipTaskTransitionBlocked): call()
        else:
            assert len(after.checkpoints) == 1 and observations == []
