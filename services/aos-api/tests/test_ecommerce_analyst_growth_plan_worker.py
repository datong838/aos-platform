"""D03 worker lineage and isolated checkpoint integration; no real provider."""
from datetime import timedelta
import os
from types import SimpleNamespace

import pytest

from aos_api.aip_contracts import PlanStep, ResourceRef, TenantContext
from aos_api.aip_task_store import AipTaskTransitionBlocked, _canonical_hash
from aos_api.ecommerce_analyst_growth_plan_generation import GrowthPlanGenerationCommand
from aos_api.ecommerce_analyst_growth_plan_worker import growth_stage_attempt_id, require_growth_stage_lineage, GrowthPlanTaorWorker
from test_aip_taor_observation_recovery import SCOPE, timeline
from test_ecommerce_analyst_growth_plan_draft import generation


def lineage():
    decision, attempt, _ = generation()
    snapshot = timeline()
    snapshot.plan.steps = [PlanStep(step_key=x, title=x) for x in ("portrait", "diagnosis", "solution-design")]
    snapshot.plan.steps[-1].assignee_refs = [ResourceRef(resource_type="AgentInstance", resource_id="colleague", revision="1", authority="aip-assignee-directory")]
    snapshot.plan.revision = 1
    snapshot.plan.task_id = "task"
    snapshot.plan.dependencies = []
    snapshot.plan.risk = {}
    snapshot.plan.approval_status = "approved"
    snapshot.plan.content_hash = _canonical_hash({"steps": [x.model_dump(mode="json", by_alias=True) for x in snapshot.plan.steps], "dependencies": [], "risk": {}})
    snapshot.run.task_id = "task"
    snapshot.run.plan_revision_id = "plan"
    snapshot.steps = [dict(step_key=x, status="succeeded") for x in ("portrait", "diagnosis")]
    run = SimpleNamespace(tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id), task_id="task", task_run_id="run", instance_id="colleague", instance_version=1,
        request=SimpleNamespace(task_ref=ResourceRef(resource_type="Task", resource_id="task", revision="1", authority="postgresql"),
            plan_ref=ResourceRef(resource_type="PlanRevision", resource_id="plan", revision="1", authority="postgresql"),
            agent_instance=SimpleNamespace(asset_type="AgentInstance", asset_id="colleague", revision=1),
            skill=SimpleNamespace(asset_type="SkillTemplate", asset_id="ecommerce.skill.D03")))
    command = GrowthPlanGenerationCommand(expected_agent_run_version=2, attempt_id=growth_stage_attempt_id(SCOPE, snapshot), attempt_no=1,
        budget_ref=attempt.budget_ref, capacity_reservation_ref=attempt.capacity_reservation_ref,
        decision_ref=dict(resourceType="DecisionSummaryRevision", resourceId=decision.decision_id, revision=1, contentHash=decision.content_hash),
        plan_budget="100", task_type="analysis", data_classification="internal")
    return snapshot, run, command


def test_exact_stage_lineage_is_accepted():
    snapshot, run, command = lineage()
    require_growth_stage_lineage(SCOPE, snapshot, run, command)


@pytest.mark.parametrize("drift", ["tenant", "task", "run", "plan", "plan_revision", "plan_hash", "approval", "stage_order", "predecessor", "assignee", "instance_version", "skill", "attempt", "attempt_no"])
def test_wrong_lineage_or_new_attempt_is_rejected(drift):
    snapshot, run, command = lineage()
    if drift == "tenant": run.tenant.org_id = "dev-org"
    elif drift == "task": run.task_id = "other"
    elif drift == "run": run.task_run_id = "other"
    elif drift == "plan": run.request.plan_ref.resource_id = "other"
    elif drift == "plan_revision": run.request.plan_ref.revision = "2"
    elif drift == "plan_hash": snapshot.plan.content_hash = "b" * 64
    elif drift == "approval": snapshot.plan.approval_status = "draft"
    elif drift == "stage_order": snapshot.plan.steps.reverse()
    elif drift == "predecessor": snapshot.steps.pop()
    elif drift == "assignee": run.instance_id = "other"
    elif drift == "instance_version": run.instance_version = 2
    elif drift == "skill": run.request.skill.asset_id = "ecommerce.skill.D02"
    elif drift == "attempt": command.attempt_id = "new-attempt"
    elif drift == "attempt_no": command.attempt_no = 2
    with pytest.raises(AipTaskTransitionBlocked):
        require_growth_stage_lineage(SCOPE, snapshot, run, command)


@pytest.mark.parametrize("policy", ["not_applicable", "no_assignee", "untrusted_assignee"])
def test_consistently_hashed_plan_still_requires_executable_assigned_stage(policy):
    snapshot, run, command = lineage()
    stage = snapshot.plan.steps[-1]
    if policy == "not_applicable":
        stage.applicability = "not_applicable"
        stage.skip_reason = "excluded from approved plan"
    elif policy == "no_assignee":
        stage.assignee_refs = []
    else:
        stage.assignee_refs[0].authority = "client"
    snapshot.plan.content_hash = _canonical_hash({"steps": [x.model_dump(mode="json", by_alias=True) for x in snapshot.plan.steps], "dependencies": [], "risk": {}})
    command.attempt_id = growth_stage_attempt_id(SCOPE, snapshot)
    with pytest.raises(AipTaskTransitionBlocked):
        require_growth_stage_lineage(SCOPE, snapshot, run, command)


@pytest.mark.skipif(os.environ.get("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database opt-in required")
@pytest.mark.parametrize("outcome", ["success", "unproven", "wrong_source"])
def test_real_d03_worker_from_retained_answer_to_checkpoint(outcome):
    import importlib.util
    from pathlib import Path
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, seed_graph
    from aos_api.aip_task_store import AipTaskStore
    from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
    from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore
    from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
    class NoProvider:
        retains_output_text = True
        def execute(self, *args, **kwargs):
            raise AssertionError("successful original attempt must not call provider again")
    with disposable_database() as connect:
        path = Path(__file__).resolve().parents[1] / "alembic/versions/a0v_012_agent_text_output.py"
        spec = importlib.util.spec_from_file_location("worker_text_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with connect(SCOPE) as conn:
            migration.op = SimpleNamespace(execute=conn.execute)
            migration.upgrade()
        kwargs = seed_graph(connect, retain_text=True, taor_ready=True)
        attempt = AipAgentRunExecutionService(connect).get(SCOPE, kwargs["attempt_id"])
        command = GrowthPlanGenerationCommand(expected_agent_run_version=attempt.agent_run_version, attempt_id=attempt.attempt_id, attempt_no=attempt.attempt_no,
            budget_ref=attempt.budget_ref, capacity_reservation_ref=attempt.capacity_reservation_ref, decision_ref=kwargs["decision_ref"],
            plan_budget=kwargs["budget"], task_type=kwargs["task_type"], data_classification="internal")
        store = AipTaskStore(connect_factory=connect)
        from aos_api.ecommerce_analyst_growth_plan_sources import require_growth_plan_sources
        with connect(SCOPE) as conn:
            decision = require_growth_plan_sources(conn, SCOPE, command.decision_ref, markings=kwargs["markings"], now=kwargs["now"], max_source_age=kwargs["max_source_age"])
        for step, observation in [("portrait", {"insightRef": decision.insight_ref.model_dump(mode="json", by_alias=True)}),
                                  ("diagnosis", {"decisionRef": command.decision_ref.model_dump(mode="json", by_alias=True)})]:
            if outcome == "wrong_source" and step == "diagnosis": observation["decisionRef"]["contentHash"] = "b" * 64
            lease = store.claim_step(SCOPE, "a0v-full-task-run", step, "prior", lease_seconds=60)
            for phase, payload in [("think", {}), ("act", {}), ("verify", {"passed": True}), ("observe", observation)]:
                store.record_step_phase(SCOPE, lease.step_run_id, "prior", lease.fence, "compiler", phase, payload)
            store.complete_step(SCOPE, lease.step_run_id, "prior", lease.fence, "compiler")
        worker = GrowthPlanTaorWorker(connect, NoProvider())
        if outcome == "unproven":
            def blocked(*args, **kwargs): raise ValueError("unknown provider outcome")
            worker._generation.generate = blocked
        call = lambda: worker.run(SCOPE, "a0v-full-task-run", attempt.agent_run_id, command, actor="compiler", worker_id="d03-worker",
            markings=kwargs["markings"], clock=lambda: kwargs["now"], max_source_age=timedelta(days=1), lease_seconds=10)
        if outcome == "success":
            assert call().run.status.value == "succeeded"
        else:
            with pytest.raises(AipTaskTransitionBlocked): call()
        after = store.timeline(SCOPE, "a0v-full-task-run")
        observations = [x["payload"]["payload"] for x in after.evidence if x["evidence_type"] == "taor.observe" and x["payload"]["stepKey"] == "solution-design"]
        if outcome == "success":
            ref = AnalystExactRef.model_validate(observations[0]["growthPlanRef"])
            plan = EcommerceAnalystAuthorityStore(connect).get_plan_exact(SCOPE, ref)
            assert plan.lifecycle.value == "draft" and plan.items[0].title == "检查回购间隔"
            assert plan.decision_ref == command.decision_ref
            assert observations[0]["artifacts"] == [] and observations[0]["artifactRefs"] == []
            assert len(after.artifacts) == 1 and len(after.checkpoints) == 3
            with pytest.raises(AipTaskTransitionBlocked): call()
        else:
            assert observations == [] and len(after.checkpoints) == 2
            assert after.run.status.value == "running"
