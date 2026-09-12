"""Real schedule binding/CAS with the explicitly fake package authority fixture."""
import pytest
from test_pipeline_schedule_control_binding_pg import binding_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_selection_schema_pg import ledger
from test_lifecycle_pg import database,pytestmark
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict,RuntimeRevisionConflict


def setup(binding_case,claim_case):
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    conn,*_=binding_case
    _,_,args,controls,_,_=claim_case
    conn.execute("UPDATE meta_schedule_run SET status='succeeded',executor_stopped=true")
    return conn,PipelineScheduleControlOwner(controls=controls),dict(scope=args['scope'],schedule_id='schedule',
        control_ref=args['control_ref'],actor=args['actor'],idempotency_key='binding-first')


def bind(conn,owner,args,**changes):
    with conn.transaction():return owner.bind(conn,**(args|changes))


def test_current_binding_replay_and_cas(binding_case,claim_case):
    conn,owner,args=setup(binding_case,claim_case)
    first=bind(conn,owner,args)
    assert bind(conn,owner,args)==first
    second=bind(conn,owner,args,idempotency_key='binding-next',previous_ref=first.ref)
    assert second.ref.revision==2 and second.ref.resource_id==first.ref.resource_id
    with pytest.raises(RuntimeRevisionConflict):bind(conn,owner,args,idempotency_key='stale')
    with conn.transaction():assert owner.read_latest(conn,scope=args['scope'],schedule_id='schedule')==second
    assert conn.execute('SELECT count(*) FROM pipeline_schedule_control_binding').fetchone()=={'count':2}


@pytest.mark.parametrize('mode',['pipeline','ingest','denied'])
def test_binding_rejects_changed_plan_or_current_denial(binding_case,claim_case,mode):
    conn,owner,args=setup(binding_case,claim_case)
    if mode=='denied':
        def deny(*a,**kw):raise PermissionError('denied')
        claim_case[-1]._guarded=deny
    else:
        conn.execute('RESET ROLE')
        if mode=='pipeline':conn.execute("UPDATE meta_schedule SET pipeline_id='other'")
        else:conn.execute("UPDATE meta_schedule SET ingest='{}'")
        conn.execute('SET ROLE aos_runtime')
    with pytest.raises((RuntimeConflict,PermissionError)):bind(conn,owner,args)
    assert conn.execute('SELECT count(*) FROM pipeline_schedule_control_binding').fetchone()=={'count':0}


def test_binding_is_transaction_owned_and_may_be_prepared_while_disabled(binding_case,claim_case):
    conn,owner,args=setup(binding_case,claim_case)
    conn.execute('UPDATE meta_schedule SET enabled=false')
    with pytest.raises(RuntimeError,match='rollback'),conn.transaction():
        owner.bind(conn,**args)
        raise RuntimeError('rollback')
    assert conn.execute('SELECT count(*) FROM pipeline_schedule_control_binding').fetchone()=={'count':0}
    assert bind(conn,owner,args).control_ref==args['control_ref']
    assert conn.execute('SELECT enabled FROM meta_schedule').fetchone()=={'enabled':False}


def test_changed_idempotent_actor_and_corrupt_history_are_rejected(binding_case,claim_case):
    from aos_api.pipeline_schedule_control_owner import decode_binding
    conn,owner,args=setup(binding_case,claim_case)
    bind(conn,owner,args)
    with pytest.raises(RuntimeConflict,match='idempotency'):
        bind(conn,owner,args,actor='other-authorized-fixture-actor')
    row=conn.execute('SELECT * FROM pipeline_schedule_control_binding').fetchone()
    for key,value in {'actor':'changed','pipeline_id':'changed','request_hash':'sha256:'+'f'*64}.items():
        with pytest.raises(ValueError):decode_binding(row|{key:value})


def test_concurrent_same_request_has_one_binding(binding_case,claim_case):
    from concurrent.futures import ThreadPoolExecutor
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    conn,owner,args=setup(binding_case,claim_case)
    schema=claim_case[1]._journal.schema
    def attempt(_):
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True,row_factory=dict_row) as db:
            db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            db.execute('SET SESSION AUTHORIZATION aos_runtime')
            with db.transaction():
                apply_asset_transaction_scope(db,org_id=args['scope'].org_id,project_id=args['scope'].project_id)
                return owner.bind(db,**args)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
    assert results[0]==results[1]
    assert conn.execute('SELECT count(*) FROM pipeline_schedule_control_binding').fetchone()=={'count':1}


def test_request_path_pipeline_mismatch_is_rejected_before_binding(binding_case,claim_case):
    conn,owner,args=setup(binding_case,claim_case)
    with pytest.raises(ValueError,match='request pipeline differs'):
        bind(conn,owner,args,expected_pipeline_id='another-pipeline')
    assert conn.execute('SELECT count(*) FROM pipeline_schedule_control_binding').fetchone()=={'count':0}


@pytest.mark.parametrize('status,stopped', [('running',True),('running',False),('failed',False),('failed',None)])
def test_first_binding_rejects_running_or_unconfirmed_old_execution(binding_case,claim_case,status,stopped):
    conn,owner,args=setup(binding_case,claim_case)
    conn.execute('UPDATE meta_schedule_run SET status=%s,executor_stopped=%s',(status,stopped))
    with pytest.raises(RuntimeConflict,match='stopped'):
        bind(conn,owner,args)
    assert conn.execute('SELECT count(*) FROM pipeline_schedule_control_binding').fetchone()=={'count':0}
