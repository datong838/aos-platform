"""Real original journal/group commits; source and signed assets are explicit doubles."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timezone
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest
from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_pipeline_snapshot_group_owner_pg import mapping
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.pipeline_selected_snapshot_group import SelectedSnapshotGroupResult
from aos_api.ec_ingress_journal import IngressJournalConflict
import aos_api.pipeline_controlled_snapshot_group_ingress as module

@pytest.fixture
def prepared_case(group_claim_case,monkeypatch):
    conn,owner,args,state,claims=group_claim_case
    plans={}
    with conn.transaction():
        def collect(group):
            for _,draft,plan in group.members:
                plans[draft.pipeline_id]=replace(plan,defaults=(('status','active'),('currency','CNY'),('timezone','+08:00')))
        owner._groups.run_current(conn,scope=args['scope'],refs=tuple(r for r,_ in args['bindings']),actor=args['actor'],execute=collect)
    def assets(db,item,actor,callback,*,snapshot=False):
        if state['deny']:raise PermissionError('fixture current denied')
        plan=plans[item.pipeline_id];return callback(plan if snapshot else plan.read_spec)
    claims._controls._selections._guarded=assets
    @contextmanager
    def connect():
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True,row_factory=dict_row) as db:
            db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(claims._journal.schema)))
            db.execute('SET SESSION AUTHORIZATION aos_runtime');yield db
    store=object.__new__(EcomConsistencyStore);store.get_checkpoint=lambda command:None
    store.apply_batch=lambda *a:pytest.fail('preparation cannot apply objects')
    def source(**kwargs):
        state['calls']+=1
        assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==2
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n']==1
        if state.get('source_error'):raise ValueError('source rejected')
        now=datetime.now(timezone.utc);group=kwargs['group']
        rows={plan.read_spec.table:[] if state['empty'] else [{'site_id':1,'site_name':'fixture'}] for _,_,plan in group.members}
        return SelectedSnapshotGroupResult(rows,group.members[0][1].source_configuration_ref,now,now)
    monkeypatch.setattr(module,'read_selected_snapshot_group',source)
    return module.ControlledSnapshotGroupIngress(claims=claims,store=store,connect=connect),conn,args,state

@pytest.mark.parametrize('empty',[False,True])
def test_atomic_original_inputs_and_exact_group_replay(prepared_case,empty):
    executor,conn,args,state=prepared_case;state['empty']=empty
    first=executor.prepare(**args);again=executor.prepare(**args)
    assert not first.replayed and again.replayed and again.rows_read==0
    assert first.parents==again.parents and len(first.parents)==2
    assert first.rows_read==(0 if empty else 2) and state['calls']==1
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_command').fetchone()['n']==2
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_input').fetchone()['n']==1
    assert conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE status='running'").fetchone()['n']==2

@pytest.mark.parametrize('failure',['source','save_rollback','claim_commit_unknown','denied_after_claim','partial_save'])
def test_failed_or_uncertain_group_never_reissues(prepared_case,monkeypatch,failure):
    executor,conn,args,state=prepared_case;original=executor._transaction;count=0
    @contextmanager
    def interrupted(scope):
        nonlocal count
        count+=1
        with original(scope) as db:
            yield db
            if failure=='save_rollback' and count==2:raise RuntimeError('rollback')
        if count==1:
            if failure=='claim_commit_unknown':raise RuntimeError('ack lost')
            if failure=='denied_after_claim':state['deny']=True
    monkeypatch.setattr(executor,'_transaction',interrupted)
    state['source_error']=failure=='source'
    save=module.ControlledIngressJournal.save_for_running_schedule;saved=0
    def partial(*a,**kw):
        nonlocal saved
        saved+=1
        if saved==2:raise RuntimeError('second save failed')
        return save(*a,**kw)
    if failure=='partial_save':monkeypatch.setattr(module.ControlledIngressJournal,'save_for_running_schedule',partial)
    with pytest.raises((RuntimeError,ValueError,PermissionError)):executor.prepare(**args)
    assert state['calls']==(0 if failure in {'claim_commit_unknown','denied_after_claim'} else 1)
    if failure=='partial_save':assert saved==2
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_command').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_input').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==2
    state['source_error']=False;state['deny']=False;monkeypatch.setattr(executor,'_transaction',original)
    before=state['calls']
    with pytest.raises(IngressJournalConflict,match='GROUP_OUTCOME_UNCONFIRMED'):executor.prepare(**args)
    assert state['calls']==before

@pytest.mark.parametrize('when',['before','after_source'])
def test_cancellation_does_not_save_or_reissue(prepared_case,monkeypatch,when):
    from threading import Event
    executor,conn,args,state=prepared_case;cancel=Event();source=module.read_selected_snapshot_group
    if when=='before':cancel.set()
    def interrupted(**kwargs):
        result=source(**kwargs);cancel.set();return result
    monkeypatch.setattr(module,'read_selected_snapshot_group',interrupted)
    with pytest.raises(IngressJournalConflict,match='CANCELLED'):executor.prepare(**args,cancel_event=cancel)
    assert state['calls']==(0 if when=='before' else 1)
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_command').fetchone()['n']==0
    if when=='after_source':
        cancel.clear()
        with pytest.raises(IngressJournalConflict,match='GROUP_OUTCOME_UNCONFIRMED'):executor.prepare(**args,cancel_event=cancel)
        assert state['calls']==1


def test_lost_input_commit_ack_replays_original_complete_group(prepared_case,monkeypatch):
    executor,conn,args,state=prepared_case;original=executor._transaction;count=0
    @contextmanager
    def interrupted(scope):
        nonlocal count
        count+=1
        with original(scope) as db:yield db
        if count==2:raise RuntimeError('input commit acknowledgement lost')
    monkeypatch.setattr(executor,'_transaction',interrupted)
    with pytest.raises(RuntimeError,match='acknowledgement'):executor.prepare(**args)
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_command').fetchone()['n']==2
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_input').fetchone()['n']==1
    monkeypatch.setattr(executor,'_transaction',original)
    replay=executor.prepare(**args)
    assert replay.replayed and len(replay.parents)==2 and state['calls']==1


@pytest.mark.parametrize('fault',['version','tables','denied_after_read'])
def test_read_result_or_authority_drift_rejects_whole_input(prepared_case,monkeypatch,fault):
    executor,conn,args,state=prepared_case;source=module.read_selected_snapshot_group
    def drift(**kwargs):
        result=source(**kwargs)
        if fault=='version':return replace(result,source_configuration_ref=result.source_configuration_ref.model_copy(update={'content_hash':'sha256:'+'e'*64}))
        if fault=='tables':return replace(result,rows_by_table={})
        state['deny']=True;return result
    monkeypatch.setattr(module,'read_selected_snapshot_group',drift)
    with pytest.raises((IngressJournalConflict,PermissionError)):executor.prepare(**args)
    assert state['calls']==1
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_command').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_input').fetchone()['n']==0
