from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest

import aos_api.ecommerce_analyst_growth_plan_generation as module
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_draft import generation

SCOPE = TenantScope("org-org", "dev-project")


def harness(monkeypatch):
    decision, attempt, _ = generation()
    ref = AnalystExactRef(resourceType="DecisionSummaryRevision", resourceId=decision.decision_id, revision=1, contentHash=decision.content_hash)
    command = module.GrowthPlanGenerationCommand(expectedAgentRunVersion=attempt.agent_run_version, attemptId=attempt.attempt_id, attemptNo=1,
        budgetRef=attempt.budget_ref, capacityReservationRef=attempt.capacity_reservation_ref, decisionRef=ref,
        planBudget="100", taskType="analysis", dataClassification="internal")
    run = SimpleNamespace(tenant=attempt.tenant, agent_run_id=attempt.agent_run_id, status="running", version=attempt.agent_run_version,
        request=SimpleNamespace(skill=SimpleNamespace(asset_type="SkillTemplate", asset_id="ecommerce.skill.D03"),
            input_refs=[SimpleNamespace(resource_type=x.resource_type, resource_id=x.resource_id, revision=str(x.revision), authority="postgresql") for x in [ref, decision.insight_ref, *decision.evidence_refs]]))
    state = dict(existing=None, storage=True, source=True, run=run, executions=[], recoveries=[], connection_open=False, result="succeeded")
    class Connection:
        def execute(self, sql, params=None): return SimpleNamespace(fetchone=lambda: {"storage": state["storage"]})
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        state["connection_open"] = True
        try: yield Connection()
        finally: state["connection_open"] = False
    class Attempts:
        def __init__(self, factory): pass
        def get(self, scope, identity):
            if state["existing"] is None: raise AipAgentRegistryNotFound("not found")
            return state["existing"]
    class Runs:
        def __init__(self, factory): pass
        def get(self, scope, identity): return state["run"]
    class Receiver:
        def __init__(self, factory): pass
        def recover(self, scope, **kwargs):
            state["recoveries"].append(kwargs)
            return "formal-plan-ref"
    def sources(*args, **kwargs):
        if not state["source"]: raise ValueError("source unavailable")
        return decision
    class Executor:
        retains_output_text = True
        def execute(self, scope, run_id, request, **kwargs):
            assert not state["connection_open"], "network execution must not hold source transaction"
            state["executions"].append(request)
            return SimpleNamespace(attempt=SimpleNamespace(status=state["result"]))
    monkeypatch.setattr(module, "AipAgentRunExecutionService", Attempts)
    monkeypatch.setattr(module, "AipAgentRunService", Runs)
    monkeypatch.setattr(module, "GrowthPlanDraftReceiver", Receiver)
    monkeypatch.setattr(module, "require_growth_plan_sources", sources)
    service = module.GrowthPlanGenerationService(connect, Executor())
    kwargs = dict(actor="compiler", markings=["internal"], now=attempt.completed_at, max_source_age=timedelta(days=1))
    return service, state, command, kwargs, attempt


def test_generation_uses_fixed_prompt_then_recovers_persisted_result(monkeypatch):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    assert service.generate(SCOPE, attempt.agent_run_id, command, **kwargs) == "formal-plan-ref"
    assert len(state["executions"]) == len(state["recoveries"]) == 1
    from aos_api.aip_agent_run_executor import AipAgentRunExecutor
    assert AipAgentRunExecutor._request_hash(attempt.agent_run_id, state["executions"][0]) == attempt.request_hash


@pytest.mark.parametrize("status", ["succeeded", "unknown", "failed", "prepared", "invoking"])
def test_existing_attempt_never_invokes_model_again(monkeypatch, status):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    state["existing"] = attempt.model_copy(update={"status": status})
    if status == "succeeded":
        assert service.generate(SCOPE, attempt.agent_run_id, command, **kwargs) == "formal-plan-ref"
    else:
        with pytest.raises(ValueError): service.generate(SCOPE, attempt.agent_run_id, command, **kwargs)
    assert state["executions"] == []


@pytest.mark.parametrize("blocker", ["source", "storage", "skill", "input", "version", "status"])
def test_preflight_blocks_without_model_call(monkeypatch, blocker):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    if blocker in {"source", "storage"}: state[blocker] = False
    elif blocker == "skill": state["run"].request.skill.asset_id = "ecommerce.skill.D02"
    elif blocker == "input": state["run"].request.input_refs = []
    elif blocker == "version": state["run"].version += 1
    else: state["run"].status = "unknown"
    with pytest.raises(ValueError): service.generate(SCOPE, attempt.agent_run_id, command, **kwargs)
    assert state["executions"] == []


def test_successful_attempt_cannot_be_reused_for_another_run(monkeypatch):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    state["existing"] = attempt
    with pytest.raises(ValueError): service.generate(SCOPE, "other-run", command, **kwargs)
    assert state["executions"] == state["recoveries"] == []


def test_unknown_result_does_not_generate_plan(monkeypatch):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    state["result"] = "unknown"
    with pytest.raises(ValueError): service.generate(SCOPE, attempt.agent_run_id, command, **kwargs)
    assert len(state["executions"]) == 1 and state["recoveries"] == []


@pytest.mark.parametrize("field,value", [("attempt_no", 2), ("expected_agent_run_version", 3), ("data_classification", "public")])
def test_existing_generation_request_drift_is_rejected(monkeypatch, field, value):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    state["existing"] = attempt
    command = command.model_copy(update={field: value})
    kwargs["markings"] = ["internal", "public"]
    with pytest.raises(ValueError): service.generate(SCOPE, attempt.agent_run_id, command, **kwargs)
    assert state["executions"] == state["recoveries"] == []


def test_nonretaining_executor_is_rejected_before_any_work():
    with pytest.raises(ValueError): module.GrowthPlanGenerationService(lambda scope: None, SimpleNamespace(retains_output_text=False))


def test_real_database_completed_generation_recovers_without_executor_call():
    import os
    if os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1":
        pytest.skip("requires explicit disposable full-graph database test")
    import importlib.util
    from pathlib import Path
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, seed_graph
    class Executor:
        retains_output_text = True
        def execute(self, *args, **kwargs): raise AssertionError("completed generation must not invoke model")
    with disposable_database() as connect:
        path = Path(__file__).resolve().parents[1] / "alembic/versions/a0v_012_agent_text_output.py"
        spec = importlib.util.spec_from_file_location("generation_retention_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with connect(SCOPE) as conn:
            migration.op = SimpleNamespace(execute=conn.execute)
            migration.upgrade()
        kwargs = seed_graph(connect, retain_text=True)
        _, attempt, _ = generation()
        command = module.GrowthPlanGenerationCommand(expectedAgentRunVersion=attempt.agent_run_version,
            attemptId=attempt.attempt_id, attemptNo=attempt.attempt_no, budgetRef=attempt.budget_ref,
            capacityReservationRef=attempt.capacity_reservation_ref, decisionRef=kwargs["decision_ref"],
            planBudget=kwargs["budget"], taskType=kwargs["task_type"], dataClassification="internal")
        options = {key: kwargs[key] for key in ["actor", "markings", "now", "max_source_age"]}
        service = module.GrowthPlanGenerationService(connect, Executor())
        first = service.generate(SCOPE, attempt.agent_run_id, command, **options)
        assert service.generate(SCOPE, attempt.agent_run_id, command, **options) == first
        assert first.resource_type == "GrowthPlanRevision"
