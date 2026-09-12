"""Host assembly checks with explicit fake execution, no source or database calls."""
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from aos_api.pipeline_control_service import PipelineControlServices
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.pipeline_schedule_control_owner import ScheduleControlBinding
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def configured(monkeypatch):
    import aos_api.pipeline_controlled_runtime as module
    scope=TenantScope('org-org','dev-project')
    ref=lambda kind,prefix:PipelineExactRef(resource_type=kind,resource_id=prefix+'55555555-5555-4555-8555-555555555555',revision=1,content_hash='sha256:'+'a'*64)
    binding=ScheduleControlBinding(ref('PipelineScheduleControlBinding','schedule-control-'),scope,'schedule','pipeline',
        '55555555-5555-4555-8555-555555555555','55555555-5555-4555-8555-555555555555',
        ref('PipelineRuntimeControlRevision','pipeline-control-'),'actor')
    service=PipelineControlServices(scope,None,None,object.__new__(PipelineSourceClaimOwner))
    events=[]
    @contextmanager
    def store():
        events.append('open')
        try:yield object()
        finally:events.append('close')
    monkeypatch.setattr(module,'_authoritative_store',store)
    state={'fail':False}
    def execute(**kwargs):
        events.append(kwargs)
        if state['fail']:raise RuntimeError('execution stopped')
        return {'output_ref':'dataset://catalog/fixture'}
    def build(**kwargs):
        assert kwargs['schedule_binding']==binding and kwargs['claims'] is service.claims
        return SimpleNamespace(execute=execute,resume_saved=lambda **kw:execute(**kw,resumed=True))
    monkeypatch.setattr(module,'ControlledSnapshotExecutor',build)
    execution=module.ControlledScheduleExecution(service=service,binding=binding,eng=object())
    args=dict(pipeline=SimpleNamespace(id='pipeline',executor_id='ec-live-v1',execution_mode='live',write_mode='SNAPSHOT'),
        nodes=[],node_id=None,sample_input={},execution_kind='direct_sync',scope=scope,run_id='run',
        deadline=None,cancel_event=None,run_started_at=1,durable_ingress=True)
    return module,execution,args,events,state


@pytest.mark.parametrize('fail',[False,True])
def test_worker_resources_live_until_actual_execution_exit(configured,fail):
    _,execution,args,events,state=configured
    state['fail']=fail
    if fail:
        with pytest.raises(RuntimeError,match='execution stopped'):execution.invoke(**args)
    else:assert execution.invoke(**args)['output_ref']=='dataset://catalog/fixture'
    assert events[0]=='open' and events[-1]=='close'
    assert events[1]['actor']=='actor' and events[1]['run_id']=='run'


@pytest.mark.parametrize('change',[{'durable_ingress':False},{'node_id':'source'},{'sample_input':{'row':1}},
    {'scope':TenantScope('dev-org','dev-project')},{'execution_kind':'preview'}])
def test_invalid_dispatch_never_opens_worker_resources(configured,change):
    _,execution,args,events,_=configured
    with pytest.raises((ValueError,PermissionError)):execution.invoke(**(args|change))
    assert events==[]


def test_recovery_mode_selects_only_saved_execution(configured):
    module,execution,args,events,_=configured
    recovered=module.ControlledScheduleExecution(service=execution.service,binding=execution.binding,eng=execution.eng,recovery=True)
    recovered.invoke(**args)
    assert events[1]['resumed'] is True


def _dispatch_engine(monkeypatch, args):
    from aos_api.phase5_pipeline_engine import Pipeline, PipelineEngine
    engine = object.__new__(PipelineEngine)
    pipeline = Pipeline(id='pipeline', name='controlled', executor_id='ec-live-v1', execution_mode='live')
    engine._evidence_resolvers = {'dataset': lambda ref: ref == 'dataset://catalog/fixture'}
    engine._executors = {'ec-live-v1': lambda **kw: pytest.fail('legacy executor must not run')}
    monkeypatch.setattr(engine, 'get_pipeline', lambda scope, identifier: pipeline)
    monkeypatch.setattr(engine, 'list_nodes', lambda scope, identifier: [])
    return engine, pipeline


def test_engine_dispatch_uses_controlled_worker_and_preserves_disabled_gate(configured, monkeypatch):
    _, execution, args, events, _ = configured
    engine, pipeline = _dispatch_engine(monkeypatch, args)
    pipeline.execution_mode = 'disabled'
    blocked = engine.execute_pipeline_once(args['scope'], pipeline.id, run_id='run', durable_ingress=True,
        controlled_execution=execution)
    assert blocked['ok'] is False and events == []
    pipeline.execution_mode = 'live'
    result = engine.execute_pipeline_once(args['scope'], pipeline.id, run_id='run', durable_ingress=True,
        controlled_execution=execution)
    assert result['ok'] is True and result['executor_stopped'] is True
    assert events[0] == 'open' and events[-1] == 'close'


@pytest.mark.parametrize('controlled,durable', [(object(), True), (None, False)])
def test_engine_rejects_invalid_controlled_dispatch_before_thread(configured, monkeypatch, controlled, durable):
    _, execution, args, events, _ = configured
    engine, pipeline = _dispatch_engine(monkeypatch, args)
    with pytest.raises((TypeError, ValueError)):
        engine.execute_pipeline_once(args['scope'], pipeline.id, run_id='run', durable_ingress=durable,
            controlled_execution=controlled if controlled is not None else execution)
    assert events == []


def test_engine_timeout_keeps_worker_resources_until_actual_exit(configured, monkeypatch):
    import threading
    module, execution, args, events, _ = configured
    engine, pipeline = _dispatch_engine(monkeypatch, args)
    pipeline.execution_timeout_seconds = .1
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    def build(**kwargs):
        def execute(**kw):
            entered.set()
            try:
                assert release.wait(5)
                assert kw['cancel_event'].is_set()
                return {'output_ref':'dataset://catalog/fixture'}
            finally: finished.set()
        return SimpleNamespace(execute=execute)
    monkeypatch.setattr(module, 'ControlledSnapshotExecutor', build)
    try:
        result = engine.execute_pipeline_once(args['scope'], pipeline.id, run_id='run', durable_ingress=True,
            controlled_execution=execution)
        assert entered.is_set() and result['ok'] is False
        assert result['error_code'] == 'PIPELINE_EXECUTOR_TIMEOUT'
        assert result['executor_stopped'] is False and events == ['open']
    finally:
        release.set()
        if entered.is_set():
            assert finished.wait(5)


@pytest.mark.parametrize('factory', [None, object()])
def test_bound_schedule_without_exact_factory_never_falls_back(configured, monkeypatch, factory):
    module, execution, args, events, _ = configured
    import aos_api.pipeline_schedule_claim as claims
    monkeypatch.setattr(claims, 'read_schedule_binding', lambda *a: execution.binding)
    with pytest.raises((RuntimeError, TypeError)):
        module.resolve_schedule_execution(args['scope'], 'schedule', 'pipeline', control_factory=factory, recovery=False)
    assert events == []


def test_unbound_schedule_needs_no_control_factory(configured, monkeypatch):
    module, _, args, events, _ = configured
    import aos_api.pipeline_schedule_claim as claims
    monkeypatch.setattr(claims, 'read_schedule_binding', lambda *a: None)
    assert module.resolve_schedule_execution(args['scope'], 'schedule', 'pipeline', control_factory=None, recovery=False) is None
    assert events == []
