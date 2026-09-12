"""Real association/transaction guards; source and package authority are fixtures."""
import pytest
from test_controlled_snapshot_ingress_pg import executor_case
from test_pipeline_schedule_control_binding_pg import binding_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_selection_schema_pg import ledger
from test_lifecycle_pg import database,pytestmark
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.pipeline_controlled_snapshot_ingress import ControlledSnapshotIngress
from aos_api.extension_runtime.lifecycle_store import RuntimeRevisionConflict


@pytest.fixture
def bound_case(executor_case,binding_case):
    original,conn,args,state=executor_case
    owner=PipelineScheduleControlOwner(controls=original._claims._controls)
    bind_args=dict(scope=args['scope'],schedule_id='schedule',control_ref=args['control_ref'],actor=args['actor'])
    with original._transaction(args['scope']) as db:
        binding=owner.bind(db,**bind_args,idempotency_key='binding')
    bound=ControlledSnapshotIngress(claims=original._claims,store=original._store,connect=original._connect,schedule_binding=binding)
    return bound,original,conn,args,state,owner,bind_args,binding


def test_bound_preparation_uses_exact_current_association(bound_case):
    bound,_,conn,args,state,*_=bound_case
    assert bound.prepare(**args).rows_read==1
    assert bound.prepare(**args).replayed
    assert state['calls']==1


def test_rebound_schedule_stops_old_execution_before_source(bound_case):
    bound,original,conn,args,state,owner,bind_args,binding=bound_case
    with original._transaction(args['scope']) as db:
        owner.bind(db,**bind_args,idempotency_key='new-binding',previous_ref=binding.ref)
    with pytest.raises(RuntimeRevisionConflict):bound.prepare(**args)
    assert state['calls']==0
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':0}


def test_binding_change_during_stage_rolls_back_before_commit(bound_case):
    bound,_,conn,args,state,owner,bind_args,binding=bound_case
    with pytest.raises(RuntimeRevisionConflict),bound._transaction(args['scope']) as db:
        db.execute('UPDATE meta_schedule SET enabled=false')
        owner.bind(db,**bind_args,idempotency_key='new-binding',previous_ref=binding.ref)
    assert conn.execute('SELECT enabled FROM meta_schedule').fetchone()=={'enabled':True}
    assert conn.execute('SELECT count(*) FROM pipeline_schedule_control_binding').fetchone()=={'count':1}
    assert state['calls']==0


def test_binding_actor_mismatch_rejected_before_connection(bound_case,monkeypatch):
    bound,_,_,args,state,*_=bound_case
    monkeypatch.setattr(bound,'_connect',lambda:pytest.fail('mismatched binding connected'))
    with pytest.raises(PermissionError):bound.prepare(**(args|{'actor':'different'}))
    assert state['calls']==0


def test_same_pipeline_other_schedule_run_is_not_covered(bound_case):
    from aos_api.ec_ingress_journal import IngressJournalConflict
    bound,_,conn,args,state,*_=bound_case
    conn.execute('RESET ROLE')
    conn.execute("INSERT INTO meta_schedule SELECT org_id,project_id,'other-schedule',pipeline_id,enabled,ingest FROM meta_schedule WHERE id='schedule'")
    conn.execute("UPDATE meta_schedule_run SET schedule_id='other-schedule' WHERE id=%s",(args['run_id'],))
    conn.execute('SET ROLE aos_runtime')
    with pytest.raises(IngressJournalConflict,match='SCHEDULE_BINDING'):
        bound.prepare(**args)
    assert state['calls']==0
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':0}
