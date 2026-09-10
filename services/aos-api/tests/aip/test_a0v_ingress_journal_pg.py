import importlib.util
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from psycopg import errors
from test_aip_budget_reservation_pg import database, runtime_connection, ROOT
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PG opt-in')


def test_ingress_command_survives_connections_and_rejects_replacement(database):
    from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict
    from aos_api.ec_ot_writer import _normalize_rows, _build_sync_scope, _build_batch_command
    database.owner.execute('CREATE TABLE data_source_configuration_revision(org_id text,project_id text,source_id text,revision_id uuid,PRIMARY KEY(org_id,project_id,source_id,revision_id))')
    revision = uuid4()
    database.owner.execute("INSERT INTO data_source_configuration_revision VALUES('org-org','dev-project','source',%s)", (revision,))
    spec = importlib.util.spec_from_file_location('ingress_migration', ROOT/'alembic/versions/a0v_005_ingress_command_journal.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    migration.upgrade(); migration.downgrade(); migration.upgrade()
    scope = TenantScope('org-org', 'dev-project')
    sync = _build_sync_scope(scope, SimpleNamespace(id='p01'))
    objects, links = _normalize_rows([{'ot':'Shop','source_pk':'1','source_updated_at':datetime.now(timezone.utc),
        'properties':{'name':'fixture','status':'active','currency':'CNY','timezone':'Asia/Shanghai'}}], sync)
    command = _build_batch_command(sync_scope=sync, objects=objects, links=links, pipeline_id='p01',store=SimpleNamespace(get_checkpoint=lambda _:None))
    journal = IngressJournal(storage_schema=database.schema)
    factory = runtime_connection(database)
    args = dict(run_id='run',pipeline_id='p01',source_id='source',source_revision=str(revision),pipeline_hash='a'*64,command=command)
    with factory(scope) as conn:
        first = journal.save(conn, scope, **args)
    with factory(scope) as conn:
        assert journal.read(conn, scope, 'run') == first
        assert journal.save(conn, scope, **args) == first
        with pytest.raises(IngressJournalConflict):
            journal.save(conn, scope, **dict(args,pipeline_hash='b'*64))
    with factory(TenantScope('dev-org','dev-project')) as conn:
        assert journal.read(conn, scope, 'run') is None
    with pytest.raises(errors.RaiseException), database.owner.transaction():
        database.owner.execute('DELETE FROM ecommerce_ingress_command')
    with pytest.raises(errors.RaiseException), database.owner.transaction():
        migration.downgrade()


def test_running_schedule_binding_blocks_drift(database):
    from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict, _digest
    from unittest.mock import Mock
    import json
    database.owner.execute('CREATE TABLE meta_schedule_run(org_id text, project_id text,id text,schedule_id text,status text)')
    database.owner.execute('CREATE TABLE meta_schedule(org_id text,project_id text,id text,pipeline_id text,enabled boolean,ingest jsonb)')
    database.owner.execute('CREATE TABLE phase5_pipeline_graph(org_id text,project_id text,pipeline_id text,payload jsonb)')
    database.owner.execute('CREATE TABLE meta_source(org_id text,project_id text,id text,type text,status text,configuration_revision uuid)')
    scope = TenantScope('org-org','dev-project')
    revision = str(uuid4())
    graph = {'pipeline_id':'p01','nodes':[{'node_type':'source','config':{'source_id':'source'}}]}
    database.owner.execute("INSERT INTO meta_schedule_run VALUES('org-org','dev-project','run','schedule','running')")
    database.owner.execute("INSERT INTO meta_schedule VALUES('org-org','dev-project','schedule','p01',true,%s::jsonb)", (json.dumps({'kind':'pipeline-live-v1','pipelineId':'p01'}),))
    database.owner.execute("INSERT INTO phase5_pipeline_graph VALUES('org-org','dev-project','p01',%s::jsonb)", (json.dumps(graph),))
    database.owner.execute("INSERT INTO meta_source VALUES('org-org','dev-project','source','jdbc-mysql-ssh','registered',%s)", (revision,))
    for table in ('meta_schedule_run','meta_schedule','phase5_pipeline_graph','meta_source'):
        database.owner.execute(f'GRANT SELECT,UPDATE ON {table} TO aos_runtime')
    journal = IngressJournal(storage_schema=database.schema)
    journal.save = Mock(return_value='saved')
    args = dict(run_id='run',pipeline_id='p01',source_id='source',source_revision=revision,pipeline_hash=_digest(graph),command=None)
    factory = runtime_connection(database)
    with factory(scope) as conn:
        assert journal.save_for_running_schedule(conn, scope, **args) == 'saved'
    changes = [
        ("UPDATE meta_schedule_run SET status='failed'", "UPDATE meta_schedule_run SET status='running'"),
        ("UPDATE meta_schedule SET enabled=false", "UPDATE meta_schedule SET enabled=true"),
        ("UPDATE meta_source SET status='disabled'", "UPDATE meta_source SET status='registered'"),
    ]
    for change, restore in changes:
        database.owner.execute(change)
        journal.save.reset_mock()
        with factory(scope) as conn, pytest.raises(IngressJournalConflict):
            journal.save_for_running_schedule(conn, scope, **args)
        journal.save.assert_not_called()
        database.owner.execute(restore)
    for mismatch in ({'pipeline_hash':'b'*64}, {'source_revision':str(uuid4())}):
        with factory(scope) as conn, pytest.raises(IngressJournalConflict):
            journal.save_for_running_schedule(conn, scope, **dict(args, **mismatch))


def test_derived_commands_are_durable_and_bound_to_original_objects(database):
    from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict
    from aos_api.ec_ot_writer import _normalize_rows, _build_sync_scope, _build_batch_command, prepare_derived_commands
    database.owner.execute('CREATE TABLE data_source_configuration_revision(org_id text,project_id text,source_id text,revision_id uuid,PRIMARY KEY(org_id,project_id,source_id,revision_id))')
    revision = uuid4()
    database.owner.execute("INSERT INTO data_source_configuration_revision VALUES('org-org','dev-project','source',%s)", (revision,))
    for filename in ('a0v_005_ingress_command_journal.py','a0v_006_ingress_derived_journal.py'):
        spec = importlib.util.spec_from_file_location('migration', ROOT/'alembic/versions'/filename)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        migration.op = SimpleNamespace(execute=database.owner.execute); migration.upgrade()
    scope=TenantScope('org-org','dev-project'); pipeline=SimpleNamespace(id='p08')
    row={'ot':'CustomerLite','source_pk':'1','source_updated_at':datetime.now(timezone.utc),
        'properties':{'memberLevel':'1','status':'active','order_count':2}}
    store=SimpleNamespace(get_checkpoint=lambda _:None,get_latest_authoritative_revision=lambda _:7,get_derived_revision=lambda *a:0)
    objects,links=_normalize_rows([row],_build_sync_scope(scope,pipeline))
    command=_build_batch_command(sync_scope=_build_sync_scope(scope,pipeline),objects=objects,links=links,pipeline_id='p08',store=store)
    derived=prepare_derived_commands(SimpleNamespace(ecom_consistency_store=store),scope,pipeline,[row])
    journal=IngressJournal(storage_schema=database.schema); factory=runtime_connection(database)
    with factory(scope) as conn:
        parent=journal.save(conn,scope,run_id='run',pipeline_id='p08',source_id='source',source_revision=str(revision),pipeline_hash='a'*64,command=command,output_rows=[row])
        first=journal.save_derived(conn,scope,'run',derived)
    with factory(scope) as conn:
        assert journal.read(conn,scope,'run') == parent
        assert parent['outputRows'][0]['properties']['order_count'] == 2
        changed = dict(row,properties=dict(row['properties'],order_count=3))
        with pytest.raises(IngressJournalConflict):
            journal.save(conn,scope,run_id='run',pipeline_id='p08',source_id='source',source_revision=str(revision),pipeline_hash='a'*64,command=command,output_rows=[changed])
        assert journal.read_derived(conn,scope,'run')==first
        assert journal.save_derived(conn,scope,'run',derived)==first
        with pytest.raises(IngressJournalConflict):
            journal.save_derived(conn,scope,'run',[derived[0].model_copy(update={'expected_derived_revision':1})])
        wrong=derived[0].model_copy(update={'identity':derived[0].identity.model_copy(update={'external_id':'niushop:1:other'})})
        with pytest.raises(IngressJournalConflict): journal.save_derived(conn,scope,'run',[wrong])
    with factory(TenantScope('dev-org','dev-project')) as conn:
        assert journal.read_derived(conn,scope,'run') is None
    with pytest.raises(errors.RaiseException), database.owner.transaction(): migration.downgrade()


def test_recovery_cross_connection_commit_before_derived_submission(database,monkeypatch):
    """Real PG journal/binding transactions plus real SQLite consistency owner."""
    import json
    from sqlalchemy import create_engine,select,func
    from sqlalchemy.pool import StaticPool
    from aos_api.ecom_consistency_store import EcomConsistencyStore,metadata,ecom_ingest_receipt,ecom_derived_receipt
    from aos_api.ec_ingress_journal import IngressJournal,IngressJournalConflict,_digest
    from aos_api.ec_ingress_recovery import recover_saved_authoritative_stages
    from test_ec_ingress_input import prepared
    scope,pipeline,row,command,_ = prepared()
    revision = str(uuid4())
    database.owner.execute('CREATE TABLE data_source_configuration_revision(org_id text,project_id text,source_id text,revision_id uuid,PRIMARY KEY(org_id,project_id,source_id,revision_id))')
    database.owner.execute("INSERT INTO data_source_configuration_revision VALUES('org-org','dev-project','source',%s)",(revision,))
    for filename in ('a0v_005_ingress_command_journal.py','a0v_006_ingress_derived_journal.py','a0v_007_ingress_dataset_receipt.py'):
        spec=importlib.util.spec_from_file_location('migration',ROOT/'alembic/versions'/filename)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        migration.op=SimpleNamespace(execute=database.owner.execute);migration.upgrade()
        if filename.startswith('a0v_007'):
            migration.downgrade();migration.upgrade()
    database.owner.execute('CREATE TABLE meta_schedule_run(org_id text,project_id text,id text,schedule_id text,status text)')
    database.owner.execute('CREATE TABLE meta_schedule(org_id text,project_id text,id text,pipeline_id text,enabled boolean,ingest jsonb)')
    database.owner.execute('CREATE TABLE phase5_pipeline_graph(org_id text,project_id text,pipeline_id text,payload jsonb)')
    database.owner.execute('CREATE TABLE meta_source(org_id text,project_id text,id text,type text,status text,configuration_revision uuid)')
    graph={'pipeline_id':pipeline.id,'nodes':[{'node_type':'source','config':{'source_id':'source'}}]}
    database.owner.execute("INSERT INTO meta_schedule_run VALUES('org-org','dev-project','run','schedule','running')")
    database.owner.execute("INSERT INTO meta_schedule VALUES('org-org','dev-project','schedule',%s,true,%s::jsonb)",(pipeline.id,json.dumps({'kind':'pipeline-live-v1','pipelineId':pipeline.id})))
    database.owner.execute("INSERT INTO phase5_pipeline_graph VALUES('org-org','dev-project',%s,%s::jsonb)",(pipeline.id,json.dumps(graph)))
    database.owner.execute("INSERT INTO meta_source VALUES('org-org','dev-project','source','jdbc-mysql-ssh','registered',%s)",(revision,))
    for table in ('meta_schedule_run','meta_schedule','phase5_pipeline_graph','meta_source'):
        database.owner.execute(f'GRANT SELECT,UPDATE ON {table} TO aos_runtime')
    factory=runtime_connection(database)
    journal=IngressJournal(storage_schema=database.schema)
    with factory(scope) as conn:
        journal.save_for_running_schedule(conn,scope,run_id='run',pipeline_id=pipeline.id,source_id='source',
            source_revision=revision,pipeline_hash=_digest(graph),command=command,output_rows=[row])
    engine=create_engine('sqlite+pysqlite:///:memory:',poolclass=StaticPool)
    metadata.create_all(engine)
    store=EcomConsistencyStore(engine)
    try:
        original_save=journal.save_derived
        def fail_save(*args):
            raise RuntimeError('SIMULATED_SAVE_FAILURE')
        monkeypatch.setattr(journal,'save_derived',fail_save)
        with pytest.raises(RuntimeError,match='SIMULATED_SAVE_FAILURE'):
            recover_saved_authoritative_stages(factory,scope,'run',journal=journal,store=store)
        assert store.read_committed_batch(command) is not None
        with factory(scope) as conn:
            assert journal.read_derived(conn,scope,'run') is None
        with engine.connect() as conn:
            assert conn.execute(select(func.count()).select_from(ecom_derived_receipt)).scalar_one()==0
        monkeypatch.setattr(journal,'save_derived',original_save)
        original_submit=store.update_derived_metrics
        def verify_committed_then_submit(item):
            with factory(scope) as conn:
                assert journal.read_derived(conn,scope,'run') is not None
            return original_submit(item)
        monkeypatch.setattr(store,'update_derived_metrics',verify_committed_then_submit)
        assert recover_saved_authoritative_stages(factory,scope,'run',journal=journal,store=store)[0].updated
        assert recover_saved_authoritative_stages(factory,scope,'run',journal=journal,store=store)[0].replayed
        with engine.connect() as conn:
            assert conn.execute(select(func.count()).select_from(ecom_ingest_receipt)).scalar_one()==1
            assert conn.execute(select(func.count()).select_from(ecom_derived_receipt)).scalar_one()==1
        from aos_api.ec_ingress_dataset import finalize_saved_dataset
        from aos_api.phase5_pipeline_engine import PipelineEngine
        from sqlalchemy import update
        from aos_api.ecom_consistency_store import projection_outbox
        for table in ('meta_dataset','meta_dataset_history'):
            database.owner.execute(f'CREATE TABLE {table} (LIKE public.{table} INCLUDING ALL)')
            database.owner.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO aos_runtime')
        database.owner.execute('CREATE SEQUENCE local_dataset_history_id')
        database.owner.execute("ALTER TABLE meta_dataset_history ALTER COLUMN id SET DEFAULT nextval('local_dataset_history_id')")
        database.owner.execute('GRANT USAGE ON SEQUENCE local_dataset_history_id TO aos_runtime')
        eng=object.__new__(PipelineEngine);eng._datasets={};eng._builds={}
        with pytest.raises(IngressJournalConflict,match='INGRESS_PROJECTION_PENDING'):
            finalize_saved_dataset(factory,scope,'run',journal=journal,store=store,eng=eng)
        with engine.begin() as conn:
            conn.execute(update(projection_outbox).values(projected=True))
        database.owner.execute('ALTER TABLE ecommerce_ingress_dataset_receipt ADD CONSTRAINT reject_test CHECK(false)')
        with pytest.raises(errors.CheckViolation):
            finalize_saved_dataset(factory,scope,'run',journal=journal,store=store,eng=eng)
        assert database.owner.execute('SELECT count(*) AS n FROM meta_dataset').fetchone()['n']==0
        assert database.owner.execute('SELECT count(*) AS n FROM meta_dataset_history').fetchone()['n']==0
        assert eng._datasets=={}
        database.owner.execute('ALTER TABLE ecommerce_ingress_dataset_receipt DROP CONSTRAINT reject_test')
        real_add=eng.add_build
        def fail_publish(*args,**kwargs):
            raise RuntimeError('SIMULATED_MEMORY_PUBLISH_FAILURE')
        monkeypatch.setattr(eng,'add_build',fail_publish)
        with pytest.raises(RuntimeError,match='SIMULATED_MEMORY_PUBLISH_FAILURE'):
            finalize_saved_dataset(factory,scope,'run',journal=journal,store=store,eng=eng)
        committed=database.owner.execute('SELECT payload FROM ecommerce_ingress_dataset_receipt').fetchone()['payload']
        monkeypatch.setattr(eng,'add_build',real_add)
        first=finalize_saved_dataset(factory,scope,'run',journal=journal,store=store,eng=eng)
        assert first==committed
        assert finalize_saved_dataset(factory,scope,'run',journal=journal,store=store,eng=eng)==first
        assert len(eng.list_builds(scope,first['dataset']['rid']))==1
        eng.create_dataset(scope,id=first['dataset']['rid'],name='newer',updated_at=first['dataset']['updatedAt']+10)
        database.owner.execute("UPDATE meta_dataset SET name='newer'")
        assert finalize_saved_dataset(factory,scope,'run',journal=journal,store=store,eng=eng)==first
        assert eng.get_dataset(scope,first['dataset']['rid']).name=='newer'
        assert database.owner.execute('SELECT name FROM meta_dataset').fetchone()['name']=='newer'

        assert database.owner.execute('SELECT count(*) AS n FROM ecommerce_ingress_dataset_receipt').fetchone()['n']==1
        with factory(TenantScope('dev-org','dev-project')) as conn:
            assert conn.execute('SELECT * FROM ecommerce_ingress_dataset_receipt').fetchone() is None
        with pytest.raises(errors.RaiseException),database.owner.transaction():
            database.owner.execute('DELETE FROM ecommerce_ingress_dataset_receipt')
        with pytest.raises(errors.RaiseException),database.owner.transaction():
            migration.downgrade()
        database.owner.execute("UPDATE meta_source SET status='disabled'")
        with pytest.raises(IngressJournalConflict,match='INGRESS_SOURCE_CONFIGURATION_DRIFT'):
            recover_saved_authoritative_stages(factory,scope,'run',journal=journal,store=store)
    finally:
        engine.dispose()
