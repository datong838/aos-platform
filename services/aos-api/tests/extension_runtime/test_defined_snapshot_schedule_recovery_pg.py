"""Committed exact claims and stop races on independent runtime connections."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from uuid import uuid4
import pytest

pytest_plugins=('test_pipeline_snapshot_schedule_service_pg',)
from test_pipeline_snapshot_schedule_races_pg import observe_wait
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner


@pytest.fixture
def committed(service,definition_case):
    api,command,database,controls=service
    _,definitions,args=definition_case
    first=api.configure(**command)
    common={k:command[k] for k in ('definition_id','actor')}
    enabled=api.transition(**common,intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    with api._connection() as db:
        slot=db.execute("SELECT date_trunc('minute',clock_timestamp()) AS t").fetchone()['t']
    owner=PipelineSnapshotScheduleClaimOwner(controls=controls)
    claim=dict(scope=api.scope,group_id=str(uuid4()),actor=command['actor'],scheduled_for=slot,
        trigger='manual',bindings=args['bindings'],definition_ref=enabled['ref'])
    return api,definitions,owner,claim,common,enabled,database,controls


def test_committed_exact_claim_recovers_on_new_owner_and_connection(committed):
    api,_,owner,args,_,_,_,controls=committed
    with api._connection() as db:value=owner.claim(db,**args)
    recovered=PipelineSnapshotScheduleClaimOwner(controls=controls)
    with api._connection() as db:
        assert recovered.read(db,scope=api.scope,group_id=args['group_id'])==value
        assert recovered.claim(db,**args)==value
        assert db.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==12
        assert db.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


@pytest.mark.parametrize('winner',['claim','stop'])
def test_stop_and_claim_serialize_without_new_authority_after_stop(committed,winner):
    api,definitions,owner,args,common,enabled,database,_=committed
    ready,pid=Event(),[]
    def contender():
        with api._connection() as db:
            db.execute("SET LOCAL statement_timeout='10s'")
            pid.append(db.info.backend_pid);ready.set()
            if winner=='claim':
                return definitions.transition(db,scope=api.scope,**common,intent='disable',
                    expected_ref=enabled['ref'],idempotency_key='stop')
            return owner.claim(db,**args)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with api._connection() as db:
            if winner=='claim':value=owner.claim(db,**args)
            else:definitions.transition(db,scope=api.scope,**common,intent='disable',
                expected_ref=enabled['ref'],idempotency_key='stop')
            future=pool.submit(contender)
            observe_wait(database,ready,pid,db.info.backend_pid)
        if winner=='stop':
            with pytest.raises(ValueError,match='current enabled'):future.result(timeout=12)
        else:assert future.result(timeout=12)['body']['state']=='disabled'
    assert api.read(**common)['body']['state']=='disabled'
    with api._connection() as db:
        assert db.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==(12 if winner=='claim' else 0)
        assert db.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0
        if winner=='claim':assert owner.read(db,scope=api.scope,group_id=args['group_id'])==value
