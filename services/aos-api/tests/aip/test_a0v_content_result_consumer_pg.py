import importlib.util
import os
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import pytest
from test_aip_budget_reservation_pg import database,ROOT,content_generate_command
from test_a0v_content_execution_worker_pg import setup
from test_aip_exact_provider_invoker import assembly
from aos_api.ecommerce_content_execution_worker import ContentExecutionWorker
from aos_api.ecommerce_content_result_consumer import ContentResultConsumer
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, canonical_hash
from aos_api.ecommerce_content_execution_composition import CurrentContentStatusReader
from aos_api.ecommerce_content_execution_journal import ContentExecutionConflict
from aos_api.tenant_scope import TenantScope
from content_consumer_pg_baseline import install_artifact,install_lineage

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PostgreSQL opt-in')


@pytest.mark.parametrize('deferred,fail_budget',[(False,False),(False,True),(True,False),(True,True)])
def test_usage_artifact_and_budget_commit_or_rollback_together(database,monkeypatch,deferred,fail_budget):
    def defer_price(request):
        if not deferred: return request
        row=database.owner.execute('SELECT payload FROM aip_model_price_snapshot_revision').fetchone()
        payload=row['payload'];now=datetime.now(UTC)
        payload.update(inputTokenPrice=None,outputTokenPrice=None,cachedTokenPrice=None,
            developmentCostAuthorization=dict(tenant={'orgId':'org-org','projectId':'dev-project'},
                provider={'assetType':'ProviderInstanceRevision','assetId':'provider-1','revision':1,'contentHash':'3'*64},
                providerModelId='test-model',approvalRef='test-development',environment='development',
                effectiveFrom=(now-timedelta(days=1)).isoformat(),effectiveUntil=(now+timedelta(days=1)).isoformat()))
        payload['contentHash']=canonical_hash({k:v for k,v in payload.items() if k not in {'tenant','revision','contentHash','createdBy','createdAt'}})
        database.owner.execute('UPDATE aip_model_price_snapshot_revision SET content_hash=%s,payload=%s::jsonb',(payload['contentHash'],json.dumps(payload)))
        return request.model_copy(update={'pricing_ref':request.pricing_ref.model_copy(update={'content_hash':'sha256:'+payload['contentHash']})})
    scope,factory,budget,rid,prepare=setup(database,command_factory=content_generate_command,request_transform=defer_price)
    pending_spec=importlib.util.spec_from_file_location('pending_migration',ROOT/'alembic/versions/a0v_002_cost_pending.py')
    pending=importlib.util.module_from_spec(pending_spec);pending_spec.loader.exec_module(pending)
    pending.op=SimpleNamespace(execute=database.owner.execute);pending.upgrade()
    install_lineage(database.owner)
    install_artifact(database.owner)
    database.owner.execute('CREATE TABLE aip_task_run(org_id text,project_id text,run_id text,task_id text)')
    database.owner.execute("INSERT INTO aip_task_run SELECT org_id,project_id,'run',task_ref->>'resourceId' FROM aip_budget_reservation")
    database.owner.execute('GRANT SELECT,INSERT ON aip_artifact,aip_lineage_event,aip_usage_receipt TO aos_runtime')
    database.owner.execute('GRANT SELECT ON aip_task_run TO aos_runtime')
    spec=importlib.util.spec_from_file_location('lineage_migration',ROOT/'alembic/versions/a0v_004_content_usage_lineage.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=database.owner.execute);migration.upgrade()
    invoker,resolution,_,_,_=assembly();response=invoker(resolution,'公开业务事实','approved_internal_knowledge')
    worker=ContentExecutionWorker(factory,prepare=prepare,invoke=lambda *_:response,storage_schema=database.schema)
    worker.run_one(scope,rid)
    consumer=ContentResultConsumer(context_reader=lambda *_:dict(runId='run',productNames=['玫瑰面霜'],channels=['店铺首页'],constraintChecks=['内容待人工评审']),storage_schema=database.schema)
    status_reader=CurrentContentStatusReader(storage_schema=database.schema)
    if fail_budget:
        def reject(*_a,**_k):raise RuntimeError('injected settlement failure')
        monkeypatch.setattr(AipBudgetReservationStore,'complete_cost_pending' if deferred else 'settle',reject)
        with factory(scope) as conn:
            with pytest.raises(RuntimeError,match='injected'):
                consumer.consume(conn,scope,rid)
            for table in ['aip_artifact','aip_usage_receipt','aip_lineage_event']:
                assert conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']==0
            assert conn.execute('SELECT count(*) AS n FROM ecommerce_content_execution_result').fetchone()['n']==1
        assert budget.get(scope,rid).state.value=='submitted'
        with factory(scope) as conn:
            assert status_reader(conn,scope,rid)=='RESULT_RECORDED_UNSETTLED'
    else:
        with factory(scope) as conn: first=consumer.consume(conn,scope,rid)
        with factory(scope) as conn:
            replay=consumer.consume(conn,scope,rid)
            assert replay['artifact']==first['artifact']
            assert replay['reservation'].replayed
            assert conn.execute('SELECT count(*) AS n FROM aip_artifact').fetchone()['n']==1
            assert conn.execute('SELECT count(*) AS n FROM aip_usage_receipt').fetchone()['n']==2
        assert first['reservation'].state.value==('cost_pending' if deferred else 'settled')
        if deferred: assert first['reservation'].actual_minor is None
        with factory(scope) as conn:
            assert status_reader(conn,scope,rid)==('COST_PENDING' if deferred else 'COMPLETED')
        database.owner.execute('DELETE FROM aip_artifact WHERE org_id=%s AND project_id=%s',scope.key)
        with factory(scope) as conn:
            with pytest.raises(ContentExecutionConflict,match='Artifact readback'):
                status_reader(conn,scope,rid)
    other=TenantScope('dev-org','dev-project')
    with factory(other) as conn:
        with pytest.raises(ContentExecutionConflict,match='reservation unavailable'):
            status_reader(conn,other,rid)
