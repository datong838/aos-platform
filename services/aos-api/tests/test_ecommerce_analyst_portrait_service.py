from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest

import aos_api.ecommerce_analyst_portrait_service as module
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_portrait_inputs import setup as input_setup
from test_ecommerce_analyst_portrait_generation import completed

SCOPE = TenantScope("org-org", "dev-project")


def harness(monkeypatch):
    input_args,inputs,_=input_setup(monkeypatch)
    inputs['materials'][0]['marking']=['internal']
    materials=inputs['materials']
    attempt,answer=completed(inputs)
    command = module.PortraitGenerationCommand(expectedAgentRunVersion=attempt.agent_run_version, attemptId=attempt.attempt_id,
        attemptNo=attempt.attempt_no, budgetRef=attempt.budget_ref, capacityReservationRef=attempt.capacity_reservation_ref,
        methodRef=input_args['method_ref'],evalRef=input_args['eval_ref'],cutoffAt=input_args['cutoff_at'],
        metricSources=input_args['metric_sources'],dataClassification='internal').model_copy(deep=True)
    run = SimpleNamespace(tenant=attempt.tenant, agent_run_id=attempt.agent_run_id, status="running", version=attempt.agent_run_version,
                          request=SimpleNamespace(skill=SimpleNamespace(asset_type="SkillTemplate", asset_id="ecommerce.skill.D01")))
    state = dict(existing=None, run=run, storage=True, denied=False, open=False, executions=[], recoveries=[],
                 result="succeeded", time=attempt.completed_at, mutate=None, materials=materials)
    class Connection:
        def execute(self, sql): return SimpleNamespace(fetchone=lambda: {"storage": state["storage"]})
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        state["open"] = True
        try: yield Connection()
        finally: state["open"] = False
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
            return "formal-portrait-ref"
    def read_inputs(**kwargs):
        assert state["open"] and kwargs["scope"] == SCOPE
        if state["denied"]: raise ValueError("source unavailable")
        return dict(inputs,materials=state["materials"])
    class Executor:
        retains_output_text = True
        def execute(self, scope, run_id, request, **kwargs):
            assert not state["open"], "source transaction must close before external wait"
            state["executions"].append(request)
            state["time"] += timedelta(minutes=10)
            if state["mutate"]: state["mutate"]()
            return SimpleNamespace(attempt=SimpleNamespace(status=state["result"]))
    monkeypatch.setattr(module, "AipAgentRunExecutionService", Attempts)
    monkeypatch.setattr(module, "AipAgentRunService", Runs)
    monkeypatch.setattr(module, "PortraitReceiver", Receiver)
    monkeypatch.setattr(module, "read_portrait_inputs", read_inputs)
    kwargs = dict(actor="compiler", markings=["internal", "secret"], clock=lambda: state["time"], max_source_age=timedelta(days=1), max_bytes=10000)
    return module.PortraitGenerationService(connect, Executor()), state, command, kwargs, attempt


def test_one_fixed_generation_recovers_with_fresh_time(monkeypatch):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    assert service.generate(SCOPE, attempt.agent_run_id, command, **kwargs) == "formal-portrait-ref"
    assert len(state["executions"]) == len(state["recoveries"]) == 1
    from aos_api.aip_agent_run_executor import AipAgentRunExecutor
    assert AipAgentRunExecutor._request_hash(attempt.agent_run_id, state["executions"][0]) == attempt.request_hash
    assert state["recoveries"][0]["now"] == attempt.completed_at + timedelta(minutes=10)


def test_caller_mutation_during_wait_does_not_change_recovery_identity(monkeypatch):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    original = command.method_ref.model_copy(deep=True)
    def mutate():
        command.method_ref.resource_id = "other"
        command.metric_sources[0].source_request.grants[0].decision_id = "other"
        kwargs["markings"].clear()
    state["mutate"] = mutate
    service.generate(SCOPE, attempt.agent_run_id, command, **kwargs)
    recovered = state["recoveries"][0]
    assert recovered["method_ref"] == original
    assert recovered["metric_sources"][0].source_request.grants[0].decision_id == "grant"
    assert recovered["markings"] == ["internal", "secret"]


@pytest.mark.parametrize("status", ["succeeded", "unknown", "prepared", "invoking", "failed"])
def test_existing_attempt_is_never_dispatched_again(monkeypatch, status):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    state["existing"] = attempt.model_copy(update={"status": status})
    if status == "succeeded":
        assert service.generate(SCOPE, attempt.agent_run_id, command, **kwargs) == "formal-portrait-ref"
    else:
        with pytest.raises(ValueError): service.generate(SCOPE, attempt.agent_run_id, command, **kwargs)
    assert state["executions"] == []


@pytest.mark.parametrize("blocker", ["source", "storage", "skill", "version", "run_status", "run_tenant", "wrong_id", "actor", "classification", "clock", "byte_limit"])
def test_preflight_failure_has_no_model_call(monkeypatch, blocker):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    if blocker == "source": state["denied"] = True
    elif blocker == "storage": state["storage"] = False
    elif blocker == "skill": state["run"].request.skill.asset_id = "ecommerce.skill.D03"
    elif blocker == "version": state["run"].version += 1
    elif blocker == "run_status": state["run"].status = "unknown"
    elif blocker == "run_tenant": state["run"].tenant = attempt.tenant.model_copy(update={"org_id": "dev-org"})
    elif blocker == "wrong_id": state["run"].agent_run_id = "other"
    elif blocker == "actor": kwargs["actor"] = " "
    elif blocker == "classification": kwargs["markings"] = ["public"]
    elif blocker == "clock": kwargs["clock"] = lambda: attempt.completed_at.replace(tzinfo=None)
    elif blocker == "byte_limit": kwargs["max_bytes"] = True
    with pytest.raises(ValueError): service.generate(SCOPE, attempt.agent_run_id, command, **kwargs)
    assert state["executions"] == state["recoveries"] == []


@pytest.mark.parametrize("change", ["run", "actor", "budget", "capacity", "attempt_no", "version", "classification"])
def test_existing_attempt_identity_drift_is_rejected(monkeypatch, change):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    state["existing"] = attempt
    run_id = attempt.agent_run_id
    if change == "run": run_id = "other"
    elif change == "actor": kwargs["actor"] = "other"
    elif change == "budget": command.budget_ref.asset_id = "other"
    elif change == "capacity": command.capacity_reservation_ref.resource_id = "other"
    elif change == "attempt_no": command.attempt_no += 1
    elif change == "version": command.expected_agent_run_version += 1
    elif change == "classification":
        command.data_classification = "public"
        kwargs["markings"].append("public")
    with pytest.raises(ValueError): service.generate(SCOPE, run_id, command, **kwargs)
    assert state["executions"] == state["recoveries"] == []


@pytest.mark.parametrize("level", ["bundle_high", "body_high", "bundle_missing", "bundle_unknown", "body_unknown", "bundle_empty"])
def test_source_cannot_be_downgraded_for_model(monkeypatch, level):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    material = state["materials"][0]
    if level == "bundle_high": material["marking"] = ["confidential"]
    elif level == "body_high": material["items"][0]["payload"]["marking"] = ["confidential"]
    elif level == "bundle_missing": del material["marking"]
    elif level == "bundle_unknown": material["marking"] = ["secret"]
    elif level == "body_unknown": material["items"][0]["payload"]["marking"] = ["secret"]
    else: material["marking"] = []
    with pytest.raises(ValueError, match="classification"):
        service.generate(SCOPE, attempt.agent_run_id, command, **kwargs)
    assert state["executions"] == state["recoveries"] == []


def test_unknown_result_never_becomes_portrait(monkeypatch):
    service, state, command, kwargs, attempt = harness(monkeypatch)
    state["result"] = "unknown"
    with pytest.raises(ValueError): service.generate(SCOPE, attempt.agent_run_id, command, **kwargs)
    assert len(state["executions"]) == 1 and state["recoveries"] == []


def test_executor_must_retain_original_output():
    with pytest.raises(ValueError): module.PortraitGenerationService(lambda scope: None, SimpleNamespace(retains_output_text=False))


