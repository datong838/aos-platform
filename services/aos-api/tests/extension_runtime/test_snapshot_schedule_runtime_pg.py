"""Real configuration/claims/Store; source and installed assets explicitly named."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import time
from functools import wraps
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest
from sqlalchemy import create_engine, event

pytest_plugins=('test_pipeline_snapshot_schedule_service_pg',)
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.phase5_pipeline_engine import PipelineEngine
from aos_api.pipeline_selected_snapshot_group import SelectedSnapshotGroupResult
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.pipeline_snapshot_schedule_runtime import PipelineSnapshotScheduleRuntime


def _install_test_stage_timing(runtime, monkeypatch):
    """Opt-in test diagnostics only; preserve exact arguments, returns and errors."""
    if os.environ.get('AOS_TEST_SCHEDULE_TIMING') != '1':
        return
    for owner, name, label in (
        (runtime._claims, 'claim', 'claim'),
        (runtime._ingress, 'prepare', 'ingress_prepare'),
        (runtime._completion, 'complete', 'completion_complete'),
        (runtime._completion._retirement, 'execute', 'retirement_execute'),
        (runtime._completion._retirement._links, 'execute', 'links_execute'),
        (runtime._completion._retirement._links._objects, 'execute', 'objects_execute'),
        (runtime._completion._retirement._links._objects._single,
         'resume_saved', 'single_resume_saved'),
        (runtime._completion, '_finish', 'completion_finish'),
    ):
        original = getattr(owner, name)

        @wraps(original)
        def timed(*args, _original=original, _label=label, **kwargs):
            start = time.perf_counter()
            try:
                return _original(*args, **kwargs)
            finally:
                print(f'W5C6R_TIMING {_label} {time.perf_counter() - start:.3f}s',
                      file=sys.stderr, flush=True)

        monkeypatch.setattr(owner, name, timed)


def test_stage_timing_is_opt_in_and_transparent(monkeypatch, capsys):
    def same(*args, **kwargs):
        return args, kwargs
    def fail(*args, **kwargs):
        raise LookupError('original failure')
    runtime = SimpleNamespace(
        _claims=SimpleNamespace(claim=same),
        _ingress=SimpleNamespace(prepare=fail),
        _completion=SimpleNamespace(
            complete=same, _finish=same,
            _retirement=SimpleNamespace(
                execute=same, _links=SimpleNamespace(
                    execute=same, _objects=SimpleNamespace(
                        execute=same, _single=SimpleNamespace(resume_saved=same))))),
    )
    monkeypatch.delenv('AOS_TEST_SCHEDULE_TIMING', raising=False)
    _install_test_stage_timing(runtime, monkeypatch)
    assert runtime._claims.claim is same
    monkeypatch.setenv('AOS_TEST_SCHEDULE_TIMING', '1')
    _install_test_stage_timing(runtime, monkeypatch)
    assert runtime._claims.claim(1, key='value') == ((1,), {'key': 'value'})
    with pytest.raises(LookupError, match='original failure'):
        runtime._ingress.prepare(2)
    assert runtime._completion.complete(3) == ((3,), {})
    assert runtime._completion._retirement.execute(4) == ((4,), {})
    assert runtime._completion._retirement._links.execute(5) == ((5,), {})
    assert runtime._completion._retirement._links._objects.execute(6) == ((6,), {})
    assert runtime._completion._retirement._links._objects._single.resume_saved(7) == ((7,), {})
    assert runtime._completion._finish(8) == ((8,), {})
    output = capsys.readouterr().err
    assert output.count('W5C6R_TIMING ') == 8
    assert all(label in output for label in (
        'claim ', 'ingress_prepare ', 'completion_complete ',
        'retirement_execute ', 'links_execute ', 'objects_execute ',
        'single_resume_saved ', 'completion_finish '))


@pytest.fixture
def runtime_case(service,monkeypatch):
    api,command,database,controls=service
    assets=controls._selections._artifacts
    document=json.loads(assets.read_artifact())
    document.update(schemaVersion='aos.snapshot-relationships/v2',retirement=dict(
        mode='present-rows-only',requireCompleteReferences=True,rejectNewerThanObservation=True,allowMissingRowDeletion=False))
    raw=json.dumps(document).encode()
    digest='sha256:'+hashlib.sha256(raw).hexdigest()
    original_record=assets.load_record
    def record(*args):
        value=original_record(*args)
        value.artifacts=[dict(relativePath='content/policies/native.json',digest=digest,size=len(raw),mediaType='application/json')]
        return value
    assets.load_record=record
    assets.read_artifact=lambda *args:raw
    command=command|dict(policy_ref=command['policy_ref'].model_copy(update={'content_hash':digest}))
    first=api.configure(**command)
    common={k:command[k] for k in ('definition_id','actor')}
    enabled=api.transition(**common,intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    @contextmanager
    def connect():
        with psycopg.connect(database,autocommit=True,row_factory=dict_row) as db:
            db.execute('SET SESSION AUTHORIZATION aos_runtime')
            yield db
    engine=create_engine(database.replace('postgresql://','postgresql+psycopg://',1))
    @event.listens_for(engine,'connect')
    def identity(dbapi_conn,_record):
        dbapi_conn.execute('SET SESSION AUTHORIZATION aos_runtime');dbapi_conn.commit()
    pipeline_engine=object.__new__(PipelineEngine)
    pipeline_engine._datasets,pipeline_engine._builds={},{}
    runtime=PipelineSnapshotScheduleRuntime(claims=PipelineSourceClaimOwner(controls=controls),
        store=EcomConsistencyStore(engine),connect=connect,eng=pipeline_engine)
    state={'calls':0}
    def source(**kwargs):
        state['calls']+=1
        with connect() as db,db.transaction():
            db.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",api.scope.key)
            assert db.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==12
            assert db.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_claim').fetchone()['n']==1
        now=datetime.now(timezone.utc)
        group=kwargs['group']
        return SelectedSnapshotGroupResult(
            {plan.read_spec.table:[dict(site_id=1,site_name='named runtime fixture')]
             for _,_,plan in group.members},group.members[0][1].source_configuration_ref,now,now)
    import aos_api.pipeline_controlled_snapshot_group_ingress as module
    monkeypatch.setattr(module,'read_selected_snapshot_group',source)
    with connect() as db:slot=db.execute("SELECT date_trunc('minute',clock_timestamp()) AS t").fetchone()['t']
    args=dict(scope=api.scope,definition_ref=enabled['ref'],actor=command['actor'],
        group_id=str(uuid4()),scheduled_for=slot,trigger='manual')
    try:yield runtime,args,state,api,common,enabled,database
    finally:engine.dispose()


def test_claim_ack_and_input_ack_loss_recover_original_group_once(runtime_case,monkeypatch):
    runtime,args,state,_,_,_,database=runtime_case
    _install_test_stage_timing(runtime, monkeypatch)
    original=runtime._transaction
    @contextmanager
    def lost_claim(scope):
        with original(scope) as db:yield db
        raise RuntimeError('claim acknowledgement lost')
    monkeypatch.setattr(runtime,'_transaction',lost_claim)
    with pytest.raises(RuntimeError,match='claim acknowledgement'):runtime.execute(**args)
    assert state['calls']==0
    monkeypatch.setattr(runtime,'_transaction',original)
    original_input=runtime._ingress._transaction
    count=0
    @contextmanager
    def lost_input(scope):
        nonlocal count
        with original_input(scope) as db:yield db
        count+=1
        if count==2:raise RuntimeError('input acknowledgement lost')
    monkeypatch.setattr(runtime._ingress,'_transaction',lost_input)
    with pytest.raises(RuntimeError,match='input acknowledgement'):runtime.execute(**args)
    assert state['calls']==1
    monkeypatch.setattr(runtime._ingress,'_transaction',original_input)
    result=runtime.execute(**args)
    assert result['status']=='succeeded'
    with psycopg.connect(database,row_factory=dict_row) as db:
        tables=('meta_schedule_run','pipeline_controlled_source_claim','ecom_object','ecom_ingest_receipt','ecommerce_ingress_dataset_receipt','ecom_link')
        before={t:db.execute(f'SELECT count(*) AS n FROM {t}').fetchone()['n'] for t in tables}
        assert before==dict(meta_schedule_run=12,pipeline_controlled_source_claim=12,ecom_object=12,
            ecom_ingest_receipt=13,ecommerce_ingress_dataset_receipt=12,ecom_link=1)
        # Twelve object batches plus the one approved Shop.hasWeapp link batch.
        assert db.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='succeeded' AND executor_stopped").fetchone()['n']==12
    assert runtime.execute(**args)['replayed'] is True
    assert state['calls']==1
    with psycopg.connect(database,row_factory=dict_row) as db:
        assert before=={t:db.execute(f'SELECT count(*) AS n FROM {t}').fetchone()['n'] for t in tables}


def test_unknown_source_claim_without_input_never_reads_again(runtime_case,monkeypatch):
    from aos_api.ec_ingress_journal import IngressJournalConflict
    runtime,args,state,_,_,_,_=runtime_case
    original=runtime._ingress._transaction
    @contextmanager
    def lost_source_claim(scope):
        with original(scope) as db:yield db
        raise RuntimeError('source claim acknowledgement lost')
    monkeypatch.setattr(runtime._ingress,'_transaction',lost_source_claim)
    with pytest.raises(RuntimeError,match='source claim acknowledgement'):runtime.execute(**args)
    monkeypatch.setattr(runtime._ingress,'_transaction',original)
    with pytest.raises(IngressJournalConflict,match='GROUP_OUTCOME_UNCONFIRMED'):runtime.execute(**args)
    assert state['calls']==0


def test_disabled_definition_never_enters_source(runtime_case):
    runtime,args,state,api,common,enabled,database=runtime_case
    api.transition(**common,intent='disable',expected_ref=enabled['ref'],idempotency_key='stop')
    with pytest.raises(ValueError):runtime.execute(**args)
    assert state['calls']==0
    with psycopg.connect(database) as db:
        assert db.execute('SELECT count(*) FROM meta_schedule_run').fetchone()[0]==0


@pytest.mark.parametrize('fault',['tenant','cancel','deadline'])
def test_wrong_tenant_or_cancelled_execution_leaves_no_run(runtime_case,fault):
    from threading import Event
    from time import monotonic
    from aos_api.tenant_scope import TenantScope
    runtime,args,state,_,_,_,database=runtime_case
    changed=dict(args)
    if fault=='tenant':changed['scope']=TenantScope('dev-org','dev-project')
    elif fault=='cancel':
        cancelled=Event();cancelled.set();changed['cancel_event']=cancelled
    else:changed['deadline']=monotonic()-1
    from aos_api.ec_ingress_journal import IngressJournalConflict
    message={'tenant':'definition unavailable','cancel':'INGRESS_CANCELLED','deadline':'INGRESS_DEADLINE_EXCEEDED'}[fault]
    with pytest.raises(LookupError if fault=='tenant' else IngressJournalConflict,match=message):
        runtime.execute(**changed)
    assert state['calls']==0
    with psycopg.connect(database) as db:
        assert db.execute('SELECT count(*) FROM meta_schedule_run').fetchone()[0]==0


def test_mixed_run_state_is_not_rewritten_or_retried(runtime_case,monkeypatch):
    from aos_api.ec_ingress_journal import IngressJournalConflict
    runtime,args,state,_,_,_,database=runtime_case
    original=runtime._transaction
    @contextmanager
    def lost_claim(scope):
        with original(scope) as db:yield db
        raise RuntimeError('claim acknowledgement lost')
    monkeypatch.setattr(runtime,'_transaction',lost_claim)
    with pytest.raises(RuntimeError,match='claim acknowledgement'):runtime.execute(**args)
    monkeypatch.setattr(runtime,'_transaction',original)
    with psycopg.connect(database) as db:
        db.execute("UPDATE meta_schedule_run SET status='failed',executor_stopped=false WHERE id=(SELECT id FROM meta_schedule_run ORDER BY id LIMIT 1)")
    with pytest.raises(IngressJournalConflict,match='GROUP_RUN_STATE_MIXED'):runtime.execute(**args)
    assert state['calls']==0
    with psycopg.connect(database) as db:
        assert db.execute("SELECT count(*) FROM meta_schedule_run WHERE status='failed' AND NOT executor_stopped").fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()[0]==0
