"""Real independent claim/Ingress commits; source and signed asset authority are fake."""
from contextlib import contextmanager
from datetime import datetime,timezone
from types import SimpleNamespace

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.pipeline_selected_snapshot import SelectedSnapshotResult
from aos_api.ec_ingress_journal import IngressJournalConflict
import aos_api.pipeline_controlled_snapshot_ingress as module


@pytest.fixture
def executor_case(claim_case,monkeypatch):
    conn,claims,args,controls,draft,selections=claim_case
    spec=MappingReadSpec('ns_site','Shop','site_id',('site_id','site_name'),(('site_id',1),))
    compiled=compile_snapshot_mapping({'source_table':'ns_site','target_ot':'Shop','primary_key':'site_id',
        'incremental_strategy':'snapshot','site_filter':'site_id=1',
        'field_mappings':[{'source':'site_id','target':'siteId','type':'int'},{'source':'site_name','target':'name','type':'string'}],
        'validation':{'required':['site_id','site_name']},'unique_key_pattern':'niushop:1:{pk}',
        'snapshot_materialization':{'schema_version':'aos.snapshot-materialization/v1','platform':'niushop',
            'shop_key':'site_id','source_timezone':'+08:00','property_defaults':{'status':'active','currency':'CNY','timezone':'+08:00'}}},spec)
    state={'calls':0,'empty':False,'source_error':False,'deny':False}
    def fake_assets(db,item,actor,callback,*,snapshot=False):
        if state['deny']:raise PermissionError('current denied')
        return callback(compiled if snapshot else spec)
    selections._guarded=fake_assets
    @contextmanager
    def connect():
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True,row_factory=dict_row) as db:
            db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(claims._journal.schema)))
            db.execute('SET SESSION AUTHORIZATION aos_runtime')
            yield db
    store=object.__new__(EcomConsistencyStore)
    store.get_checkpoint=lambda command:None
    store.apply_batch=lambda *a:pytest.fail('preparation applied objects')
    def source(**kwargs):
        state['calls']+=1
        # Another connection must see committed claim before the source query.
        assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':1}
        assert kwargs['scope']==args['scope'] and kwargs['read_spec']==spec
        if state['source_error']:raise ValueError('SELECTED_SNAPSHOT_READ_FAILED')
        now=datetime.now(timezone.utc)
        return SelectedSnapshotResult([] if state['empty'] else [{'site_id':1,'site_name':'fixture-shop'}],draft.source_configuration_ref,now,now)
    monkeypatch.setattr(module,'read_selected_snapshot',source)
    executor=module.ControlledSnapshotIngress(claims=claims,store=store,connect=connect)
    return executor,conn,args,state


@pytest.mark.parametrize('empty',[False,True])
def test_independent_claim_then_original_batch_commit_and_exact_replay(executor_case,empty):
    executor,conn,args,state=executor_case
    state['empty']=empty
    first=executor.prepare(**args)
    again=executor.prepare(**args)
    assert state['calls']==1 and first.rows_read==(0 if empty else 1)
    assert first.replayed is False and again.replayed is True and again.rows_read==0
    assert first.parent==again.parent
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':1}
    assert conn.execute('SELECT count(*) FROM ecommerce_ingress_command').fetchone()=={'count':1}
    assert conn.execute('SELECT status FROM meta_schedule_run WHERE id=%s',(args['run_id'],)).fetchone()=={'status':'running'}
    if empty:assert first.parent['kind']=='empty_observation_v1'
    else:assert first.parent['outputRows'][0]['properties']['name']=='fixture-shop'


@pytest.mark.parametrize('failure',['source','save_rollback','claim_commit_unknown','denied_after_claim'])
def test_uncertain_outcome_never_reissues_source(executor_case,monkeypatch,failure):
    executor,conn,args,state=executor_case
    original=executor._transaction
    count=0
    @contextmanager
    def interrupted(scope):
        nonlocal count
        count+=1
        with original(scope) as db:
            yield db
            if failure=='save_rollback' and count==2:raise RuntimeError('save rollback')
        if count==1:
            if failure=='claim_commit_unknown':raise RuntimeError('commit acknowledgement lost')
            if failure=='denied_after_claim':state['deny']=True
    monkeypatch.setattr(executor,'_transaction',interrupted)
    state['source_error']=failure=='source'
    with pytest.raises((RuntimeError,ValueError,PermissionError)):executor.prepare(**args)
    assert state['calls']==(1 if failure in {'source','save_rollback'} else 0)
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':1}
    assert conn.execute('SELECT count(*) FROM ecommerce_ingress_command').fetchone()=={'count':0}
    state['deny']=False;state['source_error']=False
    monkeypatch.setattr(executor,'_transaction',original)
    before=state['calls']
    with pytest.raises(IngressJournalConflict,match='SOURCE_OUTCOME_UNCONFIRMED'):executor.prepare(**args)
    assert state['calls']==before


@pytest.mark.parametrize('mode',['role','nonidle','mapping'])
def test_preparation_rejects_before_reserving_or_reading(executor_case,monkeypatch,mode):
    executor,conn,args,state=executor_case
    original=executor._connect
    @contextmanager
    def bad_connection():
        with original() as db:
            if mode=='role':
                db.execute('RESET SESSION AUTHORIZATION')
                yield db
            else:
                with db.transaction():yield db
    if mode=='mapping':
        def invalid(*a,**kw):raise ValueError('SNAPSHOT_MAPPING_INVALID')
        monkeypatch.setattr(executor._claims._controls,'run_current_snapshot',invalid)
    else:monkeypatch.setattr(executor,'_connect',bad_connection)
    with pytest.raises((PermissionError,IngressJournalConflict,ValueError)):executor.prepare(**args)
    assert state['calls']==0
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':0}


@pytest.mark.parametrize('when',['before','after_source'])
def test_cancelled_read_never_saves_or_reissues(executor_case,monkeypatch,when):
    from threading import Event
    executor,conn,args,state=executor_case
    cancel=Event()
    if when=='before':cancel.set()
    original=module.read_selected_snapshot
    def source(**kwargs):
        result=original(**kwargs)
        cancel.set()
        return result
    monkeypatch.setattr(module,'read_selected_snapshot',source)
    with pytest.raises(IngressJournalConflict,match='CANCELLED'):executor.prepare(**args,cancel_event=cancel)
    assert state['calls']==(0 if when=='before' else 1)
    assert conn.execute('SELECT count(*) FROM ecommerce_ingress_command').fetchone()=={'count':0}
    if when=='after_source':
        cancel.clear()
        with pytest.raises(IngressJournalConflict,match='SOURCE_OUTCOME_UNCONFIRMED'):executor.prepare(**args,cancel_event=cancel)
        assert state['calls']==1


def test_concurrent_same_run_preparations_share_one_committed_source_result(executor_case):
    from concurrent.futures import ThreadPoolExecutor
    executor,conn,args,state=executor_case
    def attempt(_):
        try:return executor.prepare(**args)
        except IngressJournalConflict as exc:
            # The contender may acquire the second transaction before the
            # creator has saved input. That window must fail closed, not reread.
            assert str(exc)=='SOURCE_OUTCOME_UNCONFIRMED'
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(attempt,range(2)))
    assert state['calls']==1
    created=[item for item in results if item is not None and not item.replayed]
    assert len(created)==1
    replay=executor.prepare(**args)
    assert replay.replayed and replay.parent==created[0].parent
    assert state['calls']==1
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':1}
