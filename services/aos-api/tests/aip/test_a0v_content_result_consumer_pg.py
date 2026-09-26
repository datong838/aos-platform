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
from aos_api.ecommerce_content_execution_composition import CurrentContentRunner
from aos_api.ecommerce_content_budget_command_owner import ContentBudgetCommandOwner
from aos_api.ecommerce_content_result_consumer import ContentResultConsumer
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, canonical_hash
from aos_api.ecommerce_content_execution_composition import CurrentContentStatusReader
from aos_api.ecommerce_content_execution_journal import ContentExecutionConflict, ContentExecutionJournal, _payload
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
from aos_api.tenant_scope import TenantScope
from content_consumer_pg_baseline import install_artifact,install_lineage

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PostgreSQL opt-in')


def test_exact_owner_envelope_runs_once_to_measured_readable_artifact(database):
    def owner_command(request):
        fixture=content_generate_command(request)
        return ContentBudgetCommandOwner._command_envelope(
            authority_refs=fixture['authorityRefs'],
            source_artifact_refs=fixture['sourceArtifactRefs'],
            fact_source_refs=fixture['factSourceRefs'],
            approved_fen=fixture['upperBoundFen'],
            max_input_tokens=fixture['maxInputTokens'],
            max_output_tokens=fixture['maxOutputTokens'],
            review_key=fixture['idempotencyKey'],
        )

    scope,factory,budget,rid,prepare=setup(database,command_factory=owner_command)
    install_lineage(database.owner)
    install_artifact(database.owner)
    database.owner.execute('CREATE TABLE aip_task_run(org_id text,project_id text,run_id text,task_id text)')
    database.owner.execute("INSERT INTO aip_task_run SELECT org_id,project_id,'run',task_ref->>'resourceId' FROM aip_budget_reservation")
    database.owner.execute('GRANT SELECT,INSERT ON aip_artifact,aip_lineage_event,aip_usage_receipt TO aos_runtime')
    database.owner.execute('GRANT SELECT ON aip_task_run TO aos_runtime')
    spec=importlib.util.spec_from_file_location('lineage_migration',ROOT/'alembic/versions/a0v_004_content_usage_lineage.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=database.owner.execute);migration.upgrade()
    database.owner.execute('''CREATE TABLE ecommerce_growth_runtime_command_receipt (
        org_id text,project_id text,operation_id text,idempotency_key text,
        request_hash text,response jsonb)''')
    database.owner.execute('GRANT SELECT ON ecommerce_growth_runtime_command_receipt TO aos_runtime')
    with factory(scope) as conn:
        command=ContentExecutionJournal(storage_schema=database.schema).read(conn,scope,rid)['command']
    assert command==owner_command(ContentGenerateHostService._budget_request(command))
    receipt=ContentGenerateHostService._pending_receipt(command,budget.get(scope,rid),
        ContentGenerateHostService._budget_request(command),replayed=False)
    database.owner.execute('''INSERT INTO ecommerce_growth_runtime_command_receipt
        VALUES(%s,%s,'ecommerce_growth_content_generate',%s,%s,%s::jsonb)''',
        (*scope.key,command['idempotencyKey'],'sha256:'+_payload(command)[1],json.dumps(receipt)))
    invoker,resolution,_,_,transport=assembly()
    response=invoker(resolution,'公开业务事实','approved_internal_knowledge')
    runner=CurrentContentRunner(connect_factory=factory,storage_schema=database.schema)
    calls=[]
    runner.worker=ContentExecutionWorker(factory,prepare=prepare,
        invoke=lambda *_: calls.append(1) or response,storage_schema=database.schema)
    runner.consumer=ContentResultConsumer(
        context_reader=lambda *_:dict(runId='run',productNames=['玫瑰面霜'],
            channels=['微信小店'],constraintChecks=['库存待核']),storage_schema=database.schema)
    result=runner.run_once(scope)
    assert result['pending']==[{'reservationId':rid,'status':'RESULT_RECORDED'}]
    assert result['recordedAfter']==[{'reservationId':rid,'status':'COMPLETED'}]
    assert calls==[1] and len(transport.calls)==1
    with factory(scope) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_capability_provider_request_receipt').fetchone()['n']==1
        assert conn.execute('SELECT count(*) AS n FROM aip_usage_receipt').fetchone()['n']==2
        artifact=conn.execute('SELECT metadata FROM aip_artifact').fetchone()['metadata']['ecommerceGrowthContentArtifact']
        assert artifact['body']==response['answer'] and artifact['productNames']==['玫瑰面霜']
    assert runner.run_once(scope)=={'recordedBefore':[],'pending':[],'recordedAfter':[]}
    assert runner.run_once(TenantScope('dev-org','dev-project'))=={'recordedBefore':[],'pending':[],'recordedAfter':[]}
    assert calls==[1]


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
