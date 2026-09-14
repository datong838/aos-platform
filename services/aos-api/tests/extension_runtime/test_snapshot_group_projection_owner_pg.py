"""Actual Store object/event proofs; source and installation remain fixtures."""
from types import SimpleNamespace
import pytest
from sqlalchemy import text
from test_snapshot_group_completed_quality_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,
    prepared_case,assessment_case,journal_case,object_case,completed_group,
)
from aos_api.pipeline_snapshot_group_projection_owner import PipelineSnapshotGroupProjectionOwner
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ecom_consistency_store import EcomConsistencyError
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from test_pipeline_runtime_control_owner_pg import append


def mutate_store(executor, scope, statement):
    with executor._store._engine.begin() as db:
        db.execute(text("SELECT set_config('aos.org_id',:org,true),set_config('aos.project_id',:project,true)"),
            {'org':scope.org_id,'project':scope.project_id})
        assert db.execute(text(statement)).rowcount > 0


@pytest.fixture
def projection_case(completed_group):
    executor,conn,args,state,_=completed_group
    owner=PipelineSnapshotGroupProjectionOwner(claims=executor._claims,store=executor._store)
    call={key:args[key] for key in ('scope','group_id','actor','bindings')}
    return executor,conn,call,state,owner


def test_all_original_events_still_projected_without_source_or_writes(projection_case):
    _,conn,call,state,owner=projection_case
    with conn.transaction():first=owner.run_current(conn,**call,execute=lambda x:x)
    with conn.transaction():again=owner.run_current(conn,**call,execute=lambda x:x)
    assert first==again and state['calls']==1
    assert len(first.payload['members'])==2
    assert all(m['events'] and all(e['projected'] for e in m['events']) for m in first.payload['members'])
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_dataset_receipt').fetchone()['n']==2


@pytest.mark.parametrize('fault',['base','unprojected','event-missing'])
def test_actual_store_drift_cannot_reuse_saved_completion(projection_case,fault):
    executor,conn,call,state,owner=projection_case
    statements=dict(base="UPDATE ecom_object SET payload_hash=repeat('0',64)",
        unprojected='UPDATE projection_outbox SET projected=false',event_missing='DELETE FROM projection_outbox')
    mutate_store(executor,call['scope'],statements[fault.replace('-','_')])
    with pytest.raises((IngressJournalConflict,EcomConsistencyError)),conn.transaction():
        owner.run_current(conn,**call,execute=lambda x:pytest.fail('stale saved completion accepted'))
    assert state['calls']==1


def test_bad_original_dataset_receipt_blocks_projection_proof(projection_case):
    _,conn,call,_,owner=projection_case
    class Proxy:
        def __getattr__(self,name):return getattr(conn,name)
        def execute(self,query,params=()):
            result=conn.execute(query,params)
            if 'SELECT payload,payload_hash' in str(query):
                row=result.fetchone()
                return SimpleNamespace(fetchone=lambda:dict(row,payload_hash='bad'))
            return result
    with pytest.raises(IngressJournalConflict),conn.transaction():
        owner.run_current(Proxy(),**call,execute=lambda x:pytest.fail('bad dataset'))


@pytest.mark.parametrize('fault',['output','control','deferred','base'])
def test_projection_consumer_keeps_current_checks(projection_case,fault):
    executor,conn,call,state,owner=projection_case
    def consume(current):
        if fault=='output':current.payload['members'].clear()
        if fault=='control':
            ref,draft,_=current.input.group.members[0]
            append(conn,executor._claims._controls,draft,'projection-proof-next-control',ref)
        if fault=='deferred':return (item for item in [current])
        if fault=='base':
            mutate_store(executor,call['scope'],"UPDATE ecom_object SET payload_hash=repeat('0',64)")
    with pytest.raises((ValueError,PermissionError,IngressJournalConflict,EcomConsistencyError,RuntimeConflict)),conn.transaction():
        owner.run_current(conn,**call,execute=consume)


def test_current_source_denial_prevents_projection_consumption(projection_case):
    executor,conn,call,_,owner=projection_case
    def denied(*args,**kwargs):raise PermissionError('named current source denial')
    executor._claims._controls._selections._guarded=denied
    with pytest.raises(PermissionError),conn.transaction():
        owner.run_current(conn,**call,execute=lambda x:pytest.fail('denied source accepted'))
