import importlib.util
import os
from types import SimpleNamespace
import pytest
from psycopg import errors
from test_aip_budget_reservation_pg import database,ROOT
from test_a0v_content_execution_worker_pg import setup
from test_aip_exact_provider_invoker import assembly
from aos_api.ecommerce_content_execution_worker import ContentExecutionWorker
from aos_api.ecommerce_content_usage import ContentUsageRecorder
from aos_api.ecommerce_content_execution_journal import ContentExecutionConflict
from aos_api.tenant_scope import TenantScope

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PostgreSQL opt-in')


@pytest.mark.parametrize('drift',['none','estimated','quantity','total','modality'])
def test_persisted_result_records_owned_lineage_usage_and_budget_exact_refs(database,drift):
    scope,factory,budget,rid,prepare=setup(database)
    database.owner.execute('CREATE TABLE aip_lineage_event (LIKE public.aip_lineage_event INCLUDING ALL)')
    # Budget fixture treats Usage as read-only dependency; this Owner test needs append permission.
    database.owner.execute('GRANT SELECT,INSERT ON aip_lineage_event,aip_usage_receipt TO aos_runtime')
    spec=importlib.util.spec_from_file_location('usage_lineage_migration',ROOT/'alembic/versions/a0v_004_content_usage_lineage.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=database.owner.execute);migration.upgrade()
    invoker,resolution,_,_,_=assembly()
    response=invoker(resolution,'public facts','approved_internal_knowledge')
    if drift=='estimated': response['usageReceipts'][0]['quality']='estimated'
    if drift=='quantity': response['usageReceipts'][0]['quantity']=True
    if drift=='total': response['tokens']+=1
    if drift=='modality': response['modality']='image'
    worker=ContentExecutionWorker(factory,prepare=prepare,invoke=lambda *_:response,storage_schema=database.schema)
    worker.run_one(scope,rid)
    recorder=ContentUsageRecorder(storage_schema=database.schema)
    if drift!='none':
        with factory(scope) as conn:
            with pytest.raises(ContentExecutionConflict): recorder.record(conn,scope,rid)
            assert conn.execute('SELECT count(*) AS n FROM aip_usage_receipt').fetchone()['n']==0
            assert conn.execute('SELECT count(*) AS n FROM aip_lineage_event').fetchone()['n']==0
        return
    with factory(scope) as conn:
        first=recorder.record(conn,scope,rid)
        row=recorder.journal._reservation(conn,scope,rid)
        for ref in first[1]:
            budget._usage_authority(conn,scope,ref,reservation=row,provider_result_hash=first[0])
    with factory(scope) as conn:
        assert recorder.record(conn,scope,rid)==first
        assert conn.execute('SELECT count(*) AS n FROM aip_usage_receipt').fetchone()['n']==2
        assert conn.execute('SELECT count(*) AS n FROM aip_lineage_event').fetchone()['n']==1
    with factory(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(ContentExecutionConflict): recorder.record(conn,scope,rid)
    with pytest.raises(errors.RaiseException),database.owner.transaction(): migration.downgrade()
