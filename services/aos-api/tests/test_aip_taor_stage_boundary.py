import os

import pytest

from aos_api.aip_contracts import PlanStep
from aos_api.aip_taor_loop import CanonicalTaorRunner
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked
from test_aip_taor_observation_recovery import SCOPE, Store, Adapter, timeline


@pytest.mark.parametrize("boundary", ["", " ", "absent", True, 1, []])
def test_invalid_boundary_never_claims_a_step(boundary):
    store = Store(timeline())
    with pytest.raises(ValueError):
        CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=Adapter(), stop_after_step=boundary)
    assert store.claimed == []


def test_duplicate_boundary_is_ambiguous():
    snapshot = timeline()
    snapshot.plan.steps.append(PlanStep(step_key="diagnosis", title="duplicate"))
    store = Store(snapshot)
    with pytest.raises(ValueError):
        CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=Adapter(), stop_after_step="diagnosis")
    assert store.claimed == []


def test_completed_boundary_with_missing_predecessor_never_backfills_history():
    snapshot = timeline()
    snapshot.plan.steps.insert(0, PlanStep(step_key="portrait", title="missing"))
    store = Store(snapshot)
    with pytest.raises(AipTaskTransitionBlocked):
        CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=Adapter(), stop_after_step="diagnosis")
    assert store.claimed == []


@pytest.mark.skipif(os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database opt-in required")
def test_real_three_stage_handoff_stops_claims_and_recovers_without_replay():
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
    from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
    with disposable_database() as connect:
        store = AipTaskStore(connect_factory=connect)
        task = store.create_task(SCOPE, "tester", "boundary-task", CreateTaskRequest(type="analysis", title="Synthetic handoff"))
        plan = store.create_plan(SCOPE, "tester", task.id, "boundary-plan", CreatePlanRevisionRequest(expected_task_version=task.version,
            steps=[PlanStep(step_key=key, title=key) for key in ["portrait", "diagnosis", "solution-design"]]))
        task = store.get_task(SCOPE, task.id)
        store.approve_plan(SCOPE, "tester", task.id, plan.revision, task.version, plan.content_hash)
        task = store.get_task(SCOPE, task.id)
        run = store.create_run(SCOPE, "tester", task.id, "boundary-run", CreateTaskRunRequest(plan_revision_id=plan.id, expected_task_version=task.version))
        for index, stage in enumerate(["portrait", "diagnosis", "solution-design"]):
            adapter = Adapter()
            result = CanonicalTaorRunner(store).run(SCOPE, run.id, actor="tester", worker_id=stage, adapter=adapter, stop_after_step=stage)
            assert set(adapter.contexts) == {stage}
            assert result.run.status.value == ("succeeded" if index == 2 else "running")
            after = store.timeline(SCOPE, run.id)
            assert len(after.steps) == len(after.checkpoints) == index + 1
            if index:
                assert adapter.contexts[stage]["step:portrait"]["result"] == "portrait"
            if index < 2:
                repeated = Adapter()
                replay = CanonicalTaorRunner(store).run(SCOPE, run.id, actor="tester", worker_id="replay", adapter=repeated, stop_after_step=stage)
                assert replay.run.status.value == "running" and repeated.contexts == {}
                assert store.timeline(SCOPE, run.id).steps == after.steps
