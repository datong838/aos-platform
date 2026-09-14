"""Real group/source claim transactions; signed asset authority is an explicit fixture."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case,approve
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_pipeline_snapshot_group_owner_pg import mapping
from test_pipeline_runtime_control_owner_pg import append
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft,PipelineRuntimeControlDraft
from aos_api.pipeline_snapshot_group_claim_owner import PipelineSnapshotGroupClaimOwner
from aos_api.ec_ingress_journal import _digest


@pytest.fixture
def group_claim_case(executor_case):
    executor,conn,args,state=executor_case;claims=executor._claims;controls=claims._controls;selections=controls._selections
    with conn.transaction():
        first=controls.run_current_snapshot(conn,scope=args['scope'],ref=args['control_ref'],actor=args['actor'],execute=lambda draft,plan:draft)
    plans={first.pipeline_id:mapping('ns_site'),'P02-group':mapping('ns_other')}
    def fake_assets(db,item,actor,callback,*,snapshot=False):
        if state['deny']:raise PermissionError('fixture current denied')
        plan=plans[item.pipeline_id];return callback(plan if snapshot else plan.read_spec)
    selections._guarded=fake_assets
    graph={'pipeline_id':'P02-group','write_mode':'SNAPSHOT','nodes':[{'id':'source-node','name':'source','pipeline_id':'P02-group','node_type':'source','config':{'source_id':first.source_id}}]}
    body=first.model_dump(exclude={'schema_version','source_selection_ref'});body.update(pipeline_id='P02-group',graph_hash=_digest(graph))
    second_selection=PipelineSourceSelectionDraft.model_validate(body)
    selected=approve(conn,selections,second_selection,'group-second-selection')
    body['source_selection_ref']=selected;second=PipelineRuntimeControlDraft.model_validate(body)
    ref2=append(conn,controls,second,'group-second-control')
    conn.execute('RESET ROLE')
    conn.execute('INSERT INTO meta_schedule VALUES(%s,%s,%s,%s,true,%s)',(*args['scope'].key,'schedule-two','P02-group',Jsonb({'kind':'pipeline-live-v1','pipelineId':'P02-group'})))
    conn.execute("UPDATE meta_schedule_run SET schedule_id='schedule-two' WHERE id='run-two'")
    conn.execute('INSERT INTO phase5_pipeline_graph VALUES(%s,%s,%s,1,%s)',(*args['scope'].key,'P02-group',Jsonb(graph)))
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_045_snapshot_group_journal.py'
    spec=importlib.util.spec_from_file_location('group_claim_schema',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade();conn.execute('SET ROLE aos_runtime')
    request=dict(scope=args['scope'],group_id=str(uuid4()),actor=args['actor'],bindings=((args['control_ref'],'run-one'),(ref2,'run-two')))
    return conn,PipelineSnapshotGroupClaimOwner(claims=claims),request,state,claims


def test_group_claim_atomically_reserves_two_members_and_replays(group_claim_case):
    conn,owner,args,state,_=group_claim_case
    with conn.transaction():first=owner.reserve(conn,**args)
    with conn.transaction():again=owner.reserve(conn,**args)
    with conn.transaction():current=owner.read_current(conn,**args)
    assert first.created and not again.created and first.record==again.record==current
    assert len(current.members)==2 and all(m.call_ordinal==1 for m in current.members)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==2
    assert state['calls']==0


def test_existing_individual_claim_cannot_authorize_new_group_read(group_claim_case):
    conn,owner,args,state,claims=group_claim_case
    ref,run_id=args['bindings'][1]
    with conn.transaction():claims.reserve(conn,scope=args['scope'],run_id=run_id,control_ref=ref,actor=args['actor'])
    with pytest.raises(RuntimeError),conn.transaction():owner.reserve(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n']==0
    assert state['calls']==0


def test_group_rollback_leaves_all_call_budgets_available(group_claim_case):
    conn,owner,args,_,_=group_claim_case
    with pytest.raises(RuntimeError,match='rollback'),conn.transaction():
        owner.reserve(conn,**args);raise RuntimeError('rollback')
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0
    with conn.transaction():assert owner.reserve(conn,**args).created


@pytest.mark.parametrize('fault',['run','actor','denied','stopped'])
def test_group_replay_cannot_bypass_current_binding(group_claim_case,fault):
    conn,owner,args,state,_=group_claim_case
    with conn.transaction():owner.reserve(conn,**args)
    if fault=='run':args=args|{'bindings':((args['bindings'][0][0],'different-run'),args['bindings'][1])}
    elif fault=='actor':args=args|{'actor':'different-actor'}
    elif fault=='denied':state['deny']=True
    else:
        conn.execute('RESET ROLE');conn.execute("UPDATE meta_schedule_run SET status='stopped' WHERE id='run-two'");conn.execute('SET ROLE aos_runtime')
    with pytest.raises((ValueError,RuntimeError,PermissionError)),conn.transaction():owner.reserve(conn,**args)
    assert state['calls']==0


def test_read_missing_group_never_creates_claims(group_claim_case):
    conn,owner,args,_,_=group_claim_case
    with pytest.raises(LookupError),conn.transaction():owner.read_current(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


def test_caught_group_failure_cannot_commit_half_reserved_members(group_claim_case):
    conn,owner,args,_,claims=group_claim_case
    ref,run_id=sorted(args['bindings'],key=lambda pair:pair[0].resource_id)[-1]
    with conn.transaction():claims.reserve(conn,scope=args['scope'],run_id=run_id,control_ref=ref,actor=args['actor'])
    with conn.transaction():
        with pytest.raises(RuntimeError):owner.reserve(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n']==0
