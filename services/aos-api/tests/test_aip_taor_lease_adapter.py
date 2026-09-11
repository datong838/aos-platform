"""Opt-in waiting preserves one invocation and current execution ownership."""
import os
import time
from threading import Event

import pytest

from aos_api.aip_taor_loop import CanonicalTaorRunner
from aos_api.aip_task_store import AipTaskStore, AipTaskVersionConflict
from test_aip_taor_observation_recovery import Adapter, Store, SCOPE, timeline


class HeartbeatStore(Store):
    def __init__(self):
        super().__init__(timeline())
        self.pulses = 0
        self.phases = []
        self.reject = False

    def heartbeat_step(self, scope, step_id, worker, fence, **kwargs):
        self.pulses += 1
        assert scope == SCOPE and step_id == "next" and worker == "worker" and fence == 1
        if self.reject:
            raise RuntimeError("sensitive transport details must not escape")

    def record_step_phase(self, scope, step_id, worker, fence, actor, phase, payload):
        self.phases.append(phase)


def test_explicit_waiting_renews_and_preserves_one_adapter_call():
    store = HeartbeatStore()
    class Slow(Adapter):
        calls = 0
        def act(self, step, thought):
            self.calls += 1
            time.sleep(1.4)
            return {"ok": True}
    adapter = Slow()
    assert CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=adapter,
                                           lease_seconds=1, renew_step_lease=True) == "completed"
    assert adapter.calls == 1 and store.pulses >= 10
    assert store.phases == ["think", "act", "verify", "observe"]


def test_default_does_not_start_heartbeat():
    store = HeartbeatStore()
    CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=Adapter())
    assert store.pulses == 0


@pytest.mark.parametrize("renew,seconds", [(True, 0), (True, -1), (True, True), (True, 0.5), ("yes", 30)])
def test_invalid_renewal_configuration_rejected_before_claim(renew, seconds):
    store = HeartbeatStore()
    with pytest.raises(ValueError):
        CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=Adapter(),
                                       lease_seconds=seconds, renew_step_lease=renew)
    assert not store.claimed


def test_renewal_failure_before_call_never_invokes_adapter():
    store = HeartbeatStore()
    store.reject = True
    adapter = Adapter()
    with pytest.raises(AipTaskVersionConflict, match="lease renewal failed"):
        CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=adapter, renew_step_lease=True)
    assert adapter.contexts == {} and store.phases == []


def test_lost_lease_waits_for_original_result_without_retry_or_recording_success():
    store = HeartbeatStore()
    finished = Event()
    class LosesLease(Adapter):
        calls = 0
        def act(self, step, thought):
            self.calls += 1
            store.reject = True
            time.sleep(0.8)
            finished.set()
            return {"providerResult": "already received"}
    adapter = LosesLease()
    with pytest.raises(AipTaskVersionConflict, match="lease renewal failed") as exc:
        CanonicalTaorRunner(store).run(SCOPE, "run", actor="tester", worker_id="worker", adapter=adapter,
                                       lease_seconds=1, renew_step_lease=True)
    assert finished.is_set() and adapter.calls == 1
    assert store.phases == ["think"]
    assert "sensitive" not in str(exc.value)


def running_run(store):
    from aos_api.aip_contracts import PlanStep
    from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
    task = store.create_task(SCOPE, "tester", "lease-task", CreateTaskRequest(type="lease-test", title="Synthetic lease test"))
    plan = store.create_plan(SCOPE, "tester", task.id, "lease-plan", CreatePlanRevisionRequest(
        expected_task_version=task.version, steps=[PlanStep(step_key="solution-design", title="方案设计")]))
    task = store.get_task(SCOPE, task.id)
    store.approve_plan(SCOPE, "tester", task.id, plan.revision, task.version, plan.content_hash)
    task = store.get_task(SCOPE, task.id)
    run = store.create_run(SCOPE, "tester", task.id, "lease-run", CreateTaskRunRequest(plan_revision_id=plan.id, expected_task_version=task.version))
    snapshot = store.timeline(SCOPE, run.id)
    store.start_run(SCOPE, run.id, expected_run_version=run.version, expected_task_version=snapshot.task.version,
                    actor="tester", idempotency_key="lease-start", reason="synthetic lease")
    return run


@pytest.mark.skipif(os.environ.get("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database opt-in required")
@pytest.mark.parametrize("control", ["none", "pause", "cancel", "fence"])
def test_real_postgres_slow_call_and_control_boundaries(control):
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
    with disposable_database() as connect:
        store = AipTaskStore(connect_factory=connect)
        run = running_run(store)
        class ControlledSlow(Adapter):
            calls = 0
            def act(self, step, thought):
                self.calls += 1
                if control == "fence":
                    # Only this disposable fixture: simulate ownership moving on
                    # while the old worker's single external call is in flight.
                    with connect(SCOPE) as conn:
                        conn.execute("UPDATE aip_execution_assignment_head SET current_fence=current_fence+1 WHERE org_id=%s AND project_id=%s AND run_id=%s", (*SCOPE.key, run.id))
                        conn.commit()
                elif control != "none":
                    current = store.timeline(SCOPE, run.id)
                    getattr(store, control + "_run")(SCOPE, run.id,
                        expected_run_version=current.run.version, expected_task_version=current.task.version,
                        actor="tester", idempotency_key="control-" + control, reason="synthetic control")
                time.sleep(1.4)
                return {"synthetic": True}
        adapter = ControlledSlow()
        runner = CanonicalTaorRunner(store)
        if control in {"cancel", "fence"}:
            with pytest.raises(AipTaskVersionConflict):
                runner.run(SCOPE, run.id, actor="tester", worker_id="worker", adapter=adapter, lease_seconds=1, renew_step_lease=True)
        else:
            result = runner.run(SCOPE, run.id, actor="tester", worker_id="worker", adapter=adapter, lease_seconds=1, renew_step_lease=True)
            assert result.run.status.value == ("paused" if control == "pause" else "succeeded")
        assert adapter.calls == 1
        after = store.timeline(SCOPE, run.id)
        if control in {"cancel", "fence"}:
            assert after.run.status.value == ("cancelled" if control == "cancel" else "running")
            assert after.steps[0]["action_ref"] is None
            assert not after.checkpoints
        else:
            assert after.steps[0]["status"] == "succeeded"
            assert len(after.checkpoints) == 1
