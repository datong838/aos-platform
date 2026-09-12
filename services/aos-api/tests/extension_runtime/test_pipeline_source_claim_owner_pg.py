"""Real claims, control history and schedule bindings; asset authority is a named fake."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_runtime_control_owner_pg import control_case, append as approve_control
from aos_api.ec_ingress_journal import _digest, IngressJournalConflict, IngressJournal
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def claim_case(owner_case):
    conn,selections,selection,calls=owner_case
    graph={'pipeline_id':selection.pipeline_id,'nodes':[{'node_type':'source','config':{'source_id':selection.source_id}}]}
    selection=selection.model_copy(update={'graph_hash':_digest(graph)})
    conn,controls,draft,_,_,_=control_case.__wrapped__((conn,selections,selection,calls))
    ref=approve_control(conn,controls,draft)
    conn.execute('RESET ROLE')
    conn.execute('''CREATE TABLE meta_schedule_run(org_id text,project_id text,id text,schedule_id text,status text,UNIQUE(org_id,project_id,id));
        CREATE TABLE meta_schedule(org_id text,project_id text,id text,pipeline_id text,enabled boolean,ingest jsonb);
        CREATE TABLE phase5_pipeline_graph(org_id text,project_id text,pipeline_id text,revision bigint,payload jsonb);
        CREATE TABLE meta_source(org_id text,project_id text,id text,type text,status text,configuration_revision uuid);
        GRANT SELECT,UPDATE ON meta_schedule_run,meta_schedule,phase5_pipeline_graph,meta_source TO aos_runtime;''')
    scope=TenantScope(draft.org_id,draft.project_id)
    for run_id in ('run-one','run-two'):
        conn.execute('INSERT INTO meta_schedule_run VALUES(%s,%s,%s,%s,%s)',(*scope.key,run_id,'schedule','running'))
    conn.execute('INSERT INTO meta_schedule VALUES(%s,%s,%s,%s,true,%s)',(*scope.key,'schedule',draft.pipeline_id,Jsonb({'kind':'pipeline-live-v1','pipelineId':draft.pipeline_id})))
    conn.execute('INSERT INTO phase5_pipeline_graph VALUES(%s,%s,%s,1,%s)',(*scope.key,draft.pipeline_id,Jsonb(graph)))
    conn.execute('INSERT INTO meta_source VALUES(%s,%s,%s,%s,%s,%s)',(*scope.key,draft.source_id,'jdbc-mysql-ssh','registered',draft.source_configuration_ref.resource_id.removeprefix('source-config-')))
    journal_path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_005_ingress_command_journal.py'
    journal_spec=importlib.util.spec_from_file_location('claim_original_journal_migration',journal_path)
    journal_module=importlib.util.module_from_spec(journal_spec);journal_spec.loader.exec_module(journal_module)
    journal_module.op=SimpleNamespace(execute=conn.execute);journal_module.upgrade()
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_024_pipeline_controlled_source_claim.py'
    spec=importlib.util.spec_from_file_location('claim_owner_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    owner=PipelineSourceClaimOwner(controls=controls)
    owner._journal=IngressJournal(storage_schema=conn.execute('SELECT current_schema()').fetchone()[0])
    conn.row_factory=dict_row
    conn.execute('SET ROLE aos_runtime')
    return conn,owner,dict(scope=scope,run_id='run-one',control_ref=ref,actor='test-actor'),controls,draft,selections


def reserve(case,**changes):
    conn,owner,args,*_=case
    with conn.transaction():return owner.reserve(conn,**(args|changes))


def test_claim_replay_does_not_consume_again_and_budget_is_bounded(claim_case):
    first=reserve(claim_case);second=reserve(claim_case)
    assert first.created is True and second.created is False
    assert first.record==second.record and first.record.call_ordinal==1
    with pytest.raises(RuntimeConflict,match='budget'):reserve(claim_case,run_id='run-two')
    conn,owner,args,*_=claim_case
    with conn.transaction():assert owner.read_current(conn,**args)==first.record
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':1}


def test_claim_rollback_keeps_budget_available(claim_case):
    conn,owner,args,*_=claim_case
    with pytest.raises(RuntimeError,match='rollback'),conn.transaction():
        owner.reserve(conn,**args)
        raise RuntimeError('rollback')
    assert reserve(claim_case).created is True


@pytest.mark.parametrize('mode',['actor','run_status','schedule_disabled','graph','source','denied','superseded','tenant'])
def test_replay_rechecks_all_current_bindings(claim_case,mode):
    reserve(claim_case)
    conn,owner,args,controls,draft,selections=claim_case
    if mode=='actor':args['actor']='other-actor'
    elif mode=='tenant':args['scope']=TenantScope('dev-org','dev-project')
    elif mode=='denied':
        def deny(*a):raise PermissionError('current denied')
        selections._guarded=deny
    elif mode=='superseded':approve_control(conn,controls,draft,'next',args['control_ref'])
    else:
        conn.execute('RESET ROLE')
        if mode=='run_status':conn.execute("UPDATE meta_schedule_run SET status='succeeded'")
        elif mode=='schedule_disabled':conn.execute('UPDATE meta_schedule SET enabled=false')
        elif mode=='graph':conn.execute("UPDATE phase5_pipeline_graph SET revision=2")
        else:conn.execute("UPDATE meta_source SET status='disabled'")
        conn.execute('SET ROLE aos_runtime')
    with pytest.raises((RuntimeConflict,RuntimeRevisionConflict,PermissionError,LookupError,IngressJournalConflict)):
        reserve(claim_case)
    with pytest.raises((RuntimeConflict,RuntimeRevisionConflict,PermissionError,LookupError,IngressJournalConflict)),conn.transaction():
        owner.read_current(conn,**args)


def test_missing_claim_is_not_a_read_grant(claim_case):
    conn,owner,args,*_=claim_case
    with pytest.raises(LookupError),conn.transaction():owner.read_current(conn,**args)


def test_invalid_owner_dependency_is_rejected():
    with pytest.raises(TypeError):PipelineSourceClaimOwner(controls=SimpleNamespace(run_current=lambda *a:True))


@pytest.mark.parametrize('same_run',[False,True])
def test_concurrent_connections_cannot_double_spend_one_call(claim_case,same_run):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import psycopg
    from psycopg import sql
    _,owner,args,*_=claim_case
    barrier=Barrier(2)
    def attempt(run_id):
        # Fixed ephemeral test database, never an inherited application DSN.
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True,row_factory=dict_row) as db:
            db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(owner._journal.schema)))
            db.execute('SET ROLE aos_runtime')
            db.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",args['scope'].key)
            db.execute("SET statement_timeout='5s'")
            barrier.wait(timeout=5)
            try:
                with db.transaction():return owner.reserve(db,**(args|{'run_id':run_id})).created
            except RuntimeConflict as exc:
                assert 'budget' in str(exc)
                return 'budget'
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(attempt,['run-one','run-one' if same_run else 'run-two']))
    assert outcomes.count(True)==1
    assert outcomes.count(False if same_run else 'budget')==1


def legacy_args(case):
    _,_,args,_,draft,_=case
    return dict(run_id=args['run_id'],pipeline_id=draft.pipeline_id,source_id=draft.source_id,
        source_revision=draft.source_configuration_ref.resource_id.removeprefix('source-config-'),
        pipeline_hash=draft.graph_hash,graph_revision=draft.graph_revision)


def test_claimed_run_cannot_use_legacy_ingress_path(claim_case):
    conn,owner,args,*_=claim_case
    with conn.transaction():owner._journal.verify_running_schedule(conn,args['scope'],**legacy_args(claim_case))
    reserve(claim_case)
    with pytest.raises(IngressJournalConflict,match='INGRESS_CURRENT_CONTROL_REQUIRED'),conn.transaction():
        owner._journal.verify_running_schedule(conn,args['scope'],**legacy_args(claim_case))
    with pytest.raises(IngressJournalConflict,match='INGRESS_CURRENT_CONTROL_REQUIRED'),conn.transaction():
        owner._journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(claim_case))
    assert reserve(claim_case).created is False


def test_existing_uncontrolled_batch_cannot_be_adopted(claim_case):
    conn,owner,args,*_=claim_case
    with conn.transaction():owner._journal.save_empty_for_running_schedule(conn,args['scope'],**legacy_args(claim_case))
    with pytest.raises(RuntimeConflict,match='uncontrolled ingress'):reserve(claim_case)
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':0}


@pytest.mark.parametrize('claimed',[False,True])
def test_claim_table_permission_failure_never_means_uncontrolled(claim_case,claimed):
    import psycopg
    if claimed:reserve(claim_case)
    conn,owner,args,*_=claim_case
    conn.execute('RESET ROLE')
    conn.execute('REVOKE SELECT ON pipeline_controlled_source_claim FROM aos_runtime')
    conn.execute('SET ROLE aos_runtime')
    with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
        owner._journal.verify_running_schedule(conn,args['scope'],**legacy_args(claim_case))


def test_legacy_recovery_rejection_rolls_back_claim_and_run_change(claim_case):
    from contextlib import contextmanager
    from uuid import uuid4
    from aos_api.ec_ingress_claim import claim_failed_run
    conn,owner,args,*_=claim_case
    reserve(claim_case)
    # A valid saved empty batch simulates later controlled preparation only.
    binding=legacy_args(claim_case)
    with conn.transaction():
        owner._journal._save_envelope(conn,args['scope'],dict(runId=binding['run_id'],pipelineId=binding['pipeline_id'],
            sourceId=binding['source_id'],sourceRevision=binding['source_revision'],pipelineHash=binding['pipeline_hash'],
            kind='empty_observation_v1',command=None,outputRows=[]))
    conn.execute('RESET ROLE')
    conn.execute('ALTER TABLE meta_schedule_run ADD COLUMN executor_stopped boolean, ADD COLUMN finished_at timestamptz')
    conn.execute("UPDATE meta_schedule_run SET status='failed',executor_stopped=true,finished_at=clock_timestamp()")
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_009_ingress_recovery_claim.py'
    spec=importlib.util.spec_from_file_location('legacy_recovery_claim_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    @contextmanager
    def connection(scope):
        assert scope==args['scope']
        yield conn
    with pytest.raises(IngressJournalConflict,match='INGRESS_CURRENT_CONTROL_REQUIRED'):
        claim_failed_run(connection,args['scope'],args['run_id'],str(uuid4()),journal=owner._journal)
    assert conn.execute('SELECT count(*) FROM ecommerce_ingress_recovery_claim').fetchone()=={'count':0}
    assert conn.execute('SELECT status,executor_stopped FROM meta_schedule_run WHERE id=%s',(args['run_id'],)).fetchone()=={'status':'failed','executor_stopped':True}
