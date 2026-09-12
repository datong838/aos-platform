"""Real PG owners, receipts, projection and dataset; source/package assets are fixtures."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine,event
from test_controlled_snapshot_ingress_pg import executor_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_selection_schema_pg import ledger
from test_lifecycle_pg import database,pytestmark
from aos_api.ecom_consistency_store import EcomConsistencyStore,metadata
from aos_api.pipeline_controlled_executor import ControlledSnapshotExecutor
from aos_api.phase5_pipeline_engine import PipelineEngine
from aos_api.tenant_scope import TenantScope


@pytest.fixture
def integrated(executor_case):
    preparation,conn,args,state=executor_case
    schema=preparation._claims._journal.schema
    assert schema.startswith('ar1c_')
    conn.execute('RESET ROLE')
    engine=create_engine('postgresql+psycopg://postgres@127.0.0.1:18432/postgres',
        connect_args={'options':f'-c search_path={schema}'})
    metadata.create_all(engine)
    conn.execute('CREATE SEQUENCE projection_input_revision_seq')
    root=Path(__file__).resolve().parents[2]/'alembic/versions'
    def migrate(filename):
        spec=importlib.util.spec_from_file_location('controlled_integration_migration',root/filename)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    for filename in ('a0v_006_ingress_derived_journal.py','a0v_007_ingress_dataset_receipt.py'):
        migrate(filename)
    conn.execute('''CREATE TABLE meta_object_type(id text PRIMARY KEY,name text,description text,published boolean,properties jsonb);
        CREATE TABLE obj_instance(org_id text,project_id text,object_type text,object_id text,props jsonb,PRIMARY KEY(org_id,project_id,object_type,object_id));
        CREATE TABLE graph_edge(org_id text,project_id text,src_type text,src_id text,rel text,dst_type text,dst_id text,PRIMARY KEY(org_id,project_id,src_type,src_id,rel,dst_type,dst_id));''')
    migrate('o1r2_001_projector_ownership_guard.py')
    migrate('a0v_010_projector_guard_both_sides.py')
    # Reuse canonical migration definitions without importing another test suite.
    definitions=[]
    for filename in ('228ti4d1_data_os_expand.py','228ti4d7_data_os_contract.py'):
        spec=importlib.util.spec_from_file_location('dataset_definition',root/filename)
        definition=importlib.util.module_from_spec(spec);spec.loader.exec_module(definition)
        definitions.append(definition)
    for table in ('meta_dataset','meta_dataset_history'):
        statements=[s for s in definitions[0].LEGACY_DATA_OS_SCHEMA if s.startswith(f'CREATE TABLE IF NOT EXISTS {table} (')]
        assert len(statements)==1
        conn.execute(statements[0])
        conn.execute(f'ALTER TABLE {table} ADD COLUMN org_id text NOT NULL, ADD COLUMN project_id text NOT NULL')
        columns=','.join(definitions[1].SCOPED_PRIMARY_KEYS[table])
        conn.execute(f'ALTER TABLE {table} DROP CONSTRAINT {table}_pkey, ADD PRIMARY KEY ({columns})')
    conn.execute('CREATE SEQUENCE local_dataset_history_id')
    conn.execute("ALTER TABLE meta_dataset_history ALTER COLUMN id SET DEFAULT nextval('local_dataset_history_id')")
    protected={table.name:('project_id' if table.name=='projection_outbox' else 'workspace_id') for table in metadata.tables.values()}
    protected.update({name:'project_id' for name in ('obj_instance','graph_edge','meta_dataset','meta_dataset_history')})
    for table,project in protected.items():
        conn.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO aos_runtime')
        conn.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        conn.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        predicate=f"org_id=current_setting('aos.org_id',true) AND {project}=current_setting('aos.project_id',true)"
        conn.execute(f'CREATE POLICY integration_scope ON {table} TO aos_runtime USING({predicate}) WITH CHECK({predicate})')
    conn.execute('GRANT SELECT,INSERT,UPDATE ON meta_object_type TO aos_runtime')
    conn.execute(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA {schema} TO aos_runtime')
    engine.dispose()
    @event.listens_for(engine,'connect')
    def runtime_identity(dbapi_conn,record):
        dbapi_conn.execute('SET SESSION AUTHORIZATION aos_runtime')
        dbapi_conn.commit()
    store=EcomConsistencyStore(engine)
    eng=object.__new__(PipelineEngine);eng._datasets={};eng._builds={}
    executor=ControlledSnapshotExecutor(claims=preparation._claims,store=store,connect=preparation._connect,eng=eng)
    try:yield executor,conn,args,state,eng
    finally:engine.dispose()


@pytest.mark.parametrize('interrupt',[False,True])
def test_real_saved_input_to_object_dataset_and_replay(integrated,monkeypatch,interrupt):
    executor,conn,args,state,eng=integrated
    if interrupt:
        conn.execute('ALTER TABLE ecommerce_ingress_dataset_receipt ADD CONSTRAINT fail_once CHECK(false)')
        with pytest.raises(Exception,match='fail_once'):executor.execute(**args)
        assert conn.execute('SELECT count(*) FROM obj_instance').fetchone()=={'count':1}
        assert conn.execute('SELECT count(*) FROM meta_dataset').fetchone()=={'count':0}
        assert state['calls']==1 and eng._datasets=={}
        conn.execute('ALTER TABLE ecommerce_ingress_dataset_receipt DROP CONSTRAINT fail_once')
    result=executor.execute(**args)
    assert result['rows_written']==1 and state['calls']==1
    assert result['completion']['pending']==0
    row=conn.execute('SELECT object_type,props FROM obj_instance').fetchone()
    assert row['object_type']=='Shop' and row['props']['name']=='fixture-shop'
    expected=('pipeline_controlled_source_claim','ecommerce_ingress_command','ecommerce_ingress_derived_command',
        'ecom_ingest_receipt','projection_outbox','obj_instance','ecommerce_ingress_dataset_receipt','meta_dataset','meta_dataset_history')
    before={table:conn.execute(f'SELECT count(*) FROM {table}').fetchone()['count'] for table in expected}
    assert all(count==1 for count in before.values())
    again=executor.execute(**args)
    assert again['completed_replay'] and again['rows_read']==0 and state['calls']==1
    assert before=={table:conn.execute(f'SELECT count(*) FROM {table}').fetchone()['count'] for table in expected}
    assert len(eng.list_builds(args['scope'],result['output_ref'].removeprefix('dataset://catalog/')))==1
    with executor._ingress._transaction(TenantScope('dev-org','dev-project')) as negative:
        for table in expected:
            assert negative.execute(f'SELECT count(*) FROM {table}').fetchone()=={'count':0}


def test_expired_control_renewal_finishes_saved_input_without_source(integrated,claim_case,monkeypatch):
    from test_controlled_saved_recovery_pg import renew
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    executor,conn,args,state,eng=integrated
    conn.execute('ALTER TABLE ecommerce_ingress_dataset_receipt ADD CONSTRAINT fail_once CHECK(false)')
    with pytest.raises(Exception,match='fail_once'):executor.execute(**args)
    conn.execute('ALTER TABLE ecommerce_ingress_dataset_receipt DROP CONSTRAINT fail_once')
    conn.execute('SET ROLE aos_runtime')
    ref=renew(claim_case,monkeypatch)
    renewed=args|{'control_ref':ref}
    with pytest.raises(RuntimeConflict):executor.execute(**renewed)
    result=executor.resume_saved(**renewed)
    assert result['rows_read']==0 and result['rows_written']==1 and state['calls']==1
    assert executor.resume_saved(**renewed)['completed_replay']
    conn.execute('RESET ROLE')
    for table in ('pipeline_controlled_source_claim','ecom_ingest_receipt','obj_instance','ecommerce_ingress_dataset_receipt'):
        assert conn.execute(f'SELECT count(*) FROM {table}').fetchone()=={'count':1}


def test_renewal_cannot_resume_unknown_source_outcome(integrated,claim_case,monkeypatch):
    from test_controlled_saved_recovery_pg import renew
    from aos_api.ec_ingress_journal import IngressJournalConflict
    executor,conn,args,state,eng=integrated
    state['source_error']=True
    with pytest.raises(ValueError,match='SELECTED_SNAPSHOT_READ_FAILED'):executor.execute(**args)
    state['source_error']=False
    conn.execute('SET ROLE aos_runtime')
    ref=renew(claim_case,monkeypatch)
    with pytest.raises(IngressJournalConflict,match='PARENT_REQUIRED'):
        executor.resume_saved(**(args|{'control_ref':ref}))
    assert state['calls']==1 and eng._datasets=={}
