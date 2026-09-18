"""Original claim with named execution stop; no source/Store acceptance here."""
from threading import Event
import pytest
from aos_api.pipeline_snapshot_schedule_worker import PipelineSnapshotScheduleWorker
from aos_api.pipeline_snapshot_group_recovery_runtime import PipelineSnapshotGroupRecoveryRuntime
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.ec_ingress_journal import IngressJournalConflict

pytest_plugins=('test_snapshot_schedule_runtime_pg',)


def worker_for(runtime,scope):
    recovery=PipelineSnapshotGroupRecoveryRuntime(
        claims=PipelineSourceClaimOwner(controls=runtime._claims._groups._controls),
        store=runtime._completion._store,connect=runtime._connect,
        eng=runtime._completion._retirement._links._objects._single._eng)
    return PipelineSnapshotScheduleWorker(scope=scope,runtime=runtime,recovery=recovery)


def test_lock_covers_execution_and_unknown_claim_blocks_next_tick(runtime_case,monkeypatch):
    runtime,args,state,_,common,enabled,_=runtime_case
    worker=worker_for(runtime,args['scope']);other=worker_for(runtime,args['scope'])
    import aos_api.pipeline_snapshot_schedule_dispatch as dispatch
    monkeypatch.setattr(dispatch,'cron_matches',lambda *_:True)
    calls=[]
    def stopped(**execution):
        calls.append(execution)
        assert worker.active_definition_id==common['definition_id']
        assert other.run_definition(common['definition_id'])['status']=='busy'
        with runtime._transaction(args['scope']) as conn:
            bindings=runtime._definitions._saved_bindings(conn,args['scope'],enabled['body'])
            runtime._claims.claim(conn,**{k:v for k,v in execution.items() if k not in ('deadline','cancel_event')},bindings=bindings)
        raise OSError('named executor acknowledgement loss')
    monkeypatch.setattr(runtime,'execute',stopped)
    with pytest.raises(OSError):worker.run_definition(common['definition_id'])
    assert worker.active_definition_id is None
    result=other.run_definition(common['definition_id'])
    assert result['status']=='original_group_pending' and result['groupIds']==[calls[0]['group_id']]
    assert len(calls)==1 and state['calls']==0
    assert calls[0]['definition_ref']==enabled['ref'] and calls[0]['actor']==enabled['body']['executor']


def test_stopped_worker_and_disabled_definition_never_execute(runtime_case,monkeypatch):
    runtime,args,state,api,common,enabled,_=runtime_case
    worker=worker_for(runtime,args['scope'])
    def forbidden(**kwargs):raise AssertionError('must not execute')
    monkeypatch.setattr(runtime,'execute',forbidden)
    stop=Event();stop.set()
    with pytest.raises(IngressJournalConflict,match='CANCELLED'):
        worker.run_definition(common['definition_id'],cancel_event=stop)
    api.transition(**common,intent='disable',expected_ref=enabled['ref'],idempotency_key='worker-disable')
    assert worker.run_definition(common['definition_id'])['status']=='disabled'
    assert worker.tick()==[] and state['calls']==0


def test_tick_records_unknown_without_exposing_exception_or_marking_stopped(runtime_case,monkeypatch):
    runtime,args,state,_,common,_,_=runtime_case
    worker=worker_for(runtime,args['scope'])
    import aos_api.pipeline_snapshot_schedule_dispatch as dispatch
    import aos_api.pipeline_snapshot_schedule_worker as worker_module
    monkeypatch.setattr(dispatch,'cron_matches',lambda *_:True)
    warnings=[]
    monkeypatch.setattr(worker_module.log,'warning',lambda *args:warnings.append(args))
    def fail(**_):raise RuntimeError('named secret must not be exposed')
    monkeypatch.setattr(runtime,'execute',fail)
    assert worker.tick()==[dict(definitionId=common['definition_id'],status='unknown',errorCode='SNAPSHOT_EXECUTION_UNCONFIRMED')]
    assert warnings==[('snapshot_execution_unconfirmed definition_id=%s error_type=%s error_origin=%s reason_code=%s',
        common['definition_id'],'RuntimeError','fail','RUNTIMEERROR')]
    assert 'named secret' not in repr(warnings)
    assert state['calls']==0
