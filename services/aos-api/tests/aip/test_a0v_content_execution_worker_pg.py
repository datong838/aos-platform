import importlib.util
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from psycopg.types.json import Jsonb
from test_aip_budget_reservation_pg import database, seed, runtime_connection, ROOT, content_generate_command
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
from aos_api.aip_model_runtime_contracts import ModelRouteResolution
from aos_api.ecommerce_content_execution_worker import ContentExecutionWorker, PreparedContentInvocation, ContentExecutionFailure
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal
from aos_api.ecommerce_growth_runtime_adapters import ContentGenerateHostService
from aos_api.ecommerce_content_execution_composition import CurrentContentRunner
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PostgreSQL opt-in')


def setup(database, command_factory=None, request_transform=None):
    spec=importlib.util.spec_from_file_location('journal_migration',ROOT/'alembic/versions/a0v_003_content_execution_journal.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=database.owner.execute);migration.upgrade()
    scope=TenantScope('org-org','dev-project'); factory=runtime_connection(database)
    request,refs,_=seed(database,scope,task_id='worker',now=datetime.now(UTC))
    if request_transform is not None: request=request_transform(request)
    store=AipBudgetReservationStore(factory,authority_schema=database.schema)
    held=store.reserve(scope,request,actor='test'); rid=held.reservation_ref.resource_id
    with factory(scope) as conn:
        ContentExecutionJournal(storage_schema=database.schema).enqueue(conn,scope,rid,budget_request_hash=request.request_hash(),command=command_factory(request) if command_factory else {'requestHash':'a'*64})
    def ref(kind,identity,digest='a'*64):
        return dict(assetType=kind,assetId=identity,revision=1,contentHash=digest)
    resolution=ModelRouteResolution(tenant={'orgId':scope.org_id,'projectId':scope.project_id},
        route=ref('ModelRouteRevision','route'),policy=ref('RuntimePolicyRevision','policy'),readiness='ready',
        selectedModel=ref('RegisteredModelRevision','model'),selectedProvider=ref('ProviderInstanceRevision',refs['provider'].resource_id,refs['provider'].content_hash.removeprefix('sha256:')),
        selectedPriceSnapshot=ref('ModelPriceSnapshotRevision',request.pricing_ref.resource_id,request.pricing_ref.content_hash.removeprefix('sha256:')),resolvedAt=datetime.now(UTC))
    prepare=lambda *_:PreparedContentInvocation(resolution,'approved public facts','public_catalog')
    return scope,factory,store,rid,prepare


def test_concurrent_worker_commits_before_send_and_restart_replays(database):
    scope,factory,store,rid,prepare=setup(database)
    started=Event(); finish=Event();calls=[]
    def invoke(*_):
        # Another connection can acquire the reservation lock: send is outside transaction.
        with factory(scope) as conn:
            conn.execute("SET LOCAL lock_timeout='500ms'")
            row=conn.execute('SELECT state FROM aip_budget_reservation WHERE reservation_id=%s FOR UPDATE',(rid,)).fetchone()
            assert row['state']=='submitted'
        calls.append(1);started.set()
        assert finish.wait(5)
        return {'answer':'public result'}
    worker=ContentExecutionWorker(factory,prepare=prepare,invoke=invoke,storage_schema=database.schema)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(worker.run_one,scope,rid)
        assert started.wait(5)
        assert worker.run_one(scope,rid)['status']=='RECONCILE_ONLY'
        finish.set();result=first.result(timeout=5)
    restarted=ContentExecutionWorker(factory,prepare=prepare,invoke=lambda *_:pytest.fail('duplicate send'),storage_schema=database.schema)
    assert restarted.run_one(scope,rid)==result
    assert calls==[1]


def test_unknown_outcome_never_resubmits_after_restart(database):
    scope,factory,store,rid,prepare=setup(database)
    def fail(*_): raise TimeoutError('sensitive provider detail')
    worker=ContentExecutionWorker(factory,prepare=prepare,invoke=fail,storage_schema=database.schema)
    with pytest.raises(ContentExecutionFailure,match='reconciliation required') as exc:
        worker.run_one(scope,rid)
    assert 'sensitive' not in str(exc.value)
    assert store.get(scope,rid).state.value=='unknown'
    worker.invoke=lambda *_:pytest.fail('duplicate send')
    assert worker.run_one(scope,rid)['status']=='RECONCILE_ONLY'


def test_preparation_failure_keeps_unsubmitted_reservation(database):
    scope,factory,store,rid,_=setup(database)
    def reject(*_): raise PermissionError('current authority unavailable')
    worker=ContentExecutionWorker(factory,prepare=reject,invoke=lambda *_:pytest.fail('must not send'),storage_schema=database.schema)
    with pytest.raises(PermissionError): worker.run_one(scope,rid)
    reservation=store.get(scope,rid)
    assert reservation.state.value=='held'
    assert reservation.provider_request_receipt_ref is None


def test_preparation_precedes_reservation_lock_to_preserve_host_lock_order(database):
    scope,factory,store,rid,base_prepare=setup(database)
    def prepare(conn, prepared_scope, command):
        with factory(scope) as second:
            second.execute("SET LOCAL lock_timeout='300ms'")
            row=second.execute('''SELECT state FROM aip_budget_reservation
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s FOR UPDATE''',
                (*scope.key,rid)).fetchone()
            assert row['state']=='held'
        return base_prepare(conn,prepared_scope,command)
    worker=ContentExecutionWorker(factory,prepare=prepare,
        invoke=lambda *_:{'answer':'public result'},storage_schema=database.schema)
    assert worker.run_one(scope,rid)['status']=='RESULT_RECORDED'


def test_worker_passes_prepared_output_cap_after_provider_intent_commit(database):
    scope,factory,store,rid,base_prepare=setup(database)
    calls=[]
    def prepare(conn, prepared_scope, command):
        original=base_prepare(conn,prepared_scope,command)
        return PreparedContentInvocation(original.resolution,original.prompt,
            original.data_classification,max_output_tokens=23)
    def invoke(*args,**kwargs):
        with factory(scope) as second:
            assert second.execute('SELECT state FROM aip_budget_reservation WHERE reservation_id=%s',(rid,)).fetchone()['state']=='submitted'
        calls.append(kwargs)
        return {'answer':'public result'}
    worker=ContentExecutionWorker(factory,prepare=prepare,invoke=invoke,storage_schema=database.schema)
    assert worker.run_one(scope,rid)['status']=='RESULT_RECORDED'
    assert calls==[{'max_output_tokens':23}]


def test_result_persistence_failure_is_not_a_resubmission_license(database):
    scope,factory,store,rid,prepare=setup(database)
    calls=[]
    def invoke(*_): calls.append(1); return {'answer':'public result'}
    worker=ContentExecutionWorker(factory,prepare=prepare,invoke=invoke,storage_schema=database.schema)
    def fail(*_a,**_k): raise RuntimeError('database error details')
    worker.journal.record_result=fail
    with pytest.raises(ContentExecutionFailure,match='do not resubmit'):
        worker.run_one(scope,rid)
    restarted=ContentExecutionWorker(factory,prepare=prepare,invoke=invoke,storage_schema=database.schema)
    assert restarted.run_one(scope,rid)['status']=='RECONCILE_ONLY'
    assert calls==[1]


def test_real_invoker_result_shape_is_persisted_and_replayed(database):
    from test_aip_exact_provider_invoker import assembly
    scope,factory,store,rid,prepare=setup(database)
    invoker,resolution,_,_,transport=assembly()
    response=invoker(resolution,'approved facts','approved_internal_knowledge')
    assert isinstance(response['usageReceipts'][0]['observedAt'],datetime)
    worker=ContentExecutionWorker(factory,prepare=prepare,invoke=lambda *_:response,storage_schema=database.schema)
    saved=worker.run_one(scope,rid)
    worker.invoke=lambda *_:pytest.fail('duplicate send')
    assert worker.run_one(scope,rid)==saved
    assert isinstance(saved['result']['usageReceipts'][0]['observedAt'],str)
    assert saved['result']['tokens']==12 and len(transport.calls)==1


def test_selector_only_exposes_exact_pending_v2_command(database):
    scope,factory,store,rid,_=setup(database,command_factory=content_generate_command)
    journal=ContentExecutionJournal(storage_schema=database.schema)
    database.owner.execute('''CREATE TABLE ecommerce_growth_runtime_command_receipt (
        org_id text,project_id text,operation_id text,idempotency_key text,
        request_hash text,response jsonb)''')
    database.owner.execute('GRANT SELECT ON ecommerce_growth_runtime_command_receipt TO aos_runtime')
    with factory(scope) as conn:
        assert journal.list_held(conn,scope)==[]
        command=journal.read(conn,scope,rid)['command']
    request=ContentGenerateHostService._budget_request(command)
    receipt=ContentGenerateHostService._pending_receipt(
        command,store.get(scope,rid),request,replayed=False)
    database.owner.execute('''INSERT INTO ecommerce_growth_runtime_command_receipt
        VALUES(%s,%s,'ecommerce_growth_content_generate',%s,%s,%s)''',
        (*scope.key,command['idempotencyKey'],command['requestHash'],Jsonb(receipt)))
    with factory(scope) as conn:
        assert journal.list_held(conn,scope)==[rid]
        assert journal.list_held(conn,TenantScope('dev-org','dev-project'))==[]
    database.owner.execute('''UPDATE ecommerce_growth_runtime_command_receipt
        SET response=jsonb_set(response,'{budgetReservationRef,resourceId}','"wrong"'::jsonb)''')
    with factory(scope) as conn:
        with pytest.raises(Exception,match='pending runtime Receipt drifted'):
            journal.list_held(conn,scope)


def test_runner_uses_pending_selector_and_returns_only_status(database):
    scope,factory,store,rid,prepare=setup(database,command_factory=content_generate_command)
    journal=ContentExecutionJournal(storage_schema=database.schema)
    database.owner.execute('''CREATE TABLE ecommerce_growth_runtime_command_receipt (
        org_id text,project_id text,operation_id text,idempotency_key text,
        request_hash text,response jsonb)''')
    database.owner.execute('GRANT SELECT ON ecommerce_growth_runtime_command_receipt TO aos_runtime')
    with factory(scope) as conn: command=journal.read(conn,scope,rid)['command']
    receipt=ContentGenerateHostService._pending_receipt(command,store.get(scope,rid),
        ContentGenerateHostService._budget_request(command),replayed=False)
    database.owner.execute('''INSERT INTO ecommerce_growth_runtime_command_receipt
        VALUES(%s,%s,'ecommerce_growth_content_generate',%s,%s,%s)''',
        (*scope.key,command['idempotencyKey'],command['requestHash'],Jsonb(receipt)))
    runner=CurrentContentRunner(connect_factory=factory,storage_schema=database.schema)
    runner.worker=ContentExecutionWorker(factory,prepare=prepare,
        invoke=lambda *_:{'answer':'sensitive text'},storage_schema=database.schema)
    assert runner.run_pending(scope)==[{'reservationId':rid,'status':'RESULT_RECORDED'}]
    assert runner.run_pending(scope)==[]


def test_recorded_result_selector_recovers_without_provider_resend(database):
    scope,factory,store,rid,prepare=setup(database,command_factory=content_generate_command)
    journal=ContentExecutionJournal(storage_schema=database.schema)
    with factory(scope) as conn:
        assert journal.list_recorded(conn,scope)==[]
    calls=[]
    ContentExecutionWorker(factory,prepare=prepare,
        invoke=lambda *_:calls.append(1) or {'answer':'public result'},
        storage_schema=database.schema).run_one(scope,rid)
    with factory(scope) as conn:
        assert journal.list_recorded(conn,scope)==[rid]
        assert journal.list_recorded(conn,TenantScope('dev-org','dev-project'))==[]
    assert calls==[1]


def test_runner_drains_recorded_results_without_invoking_provider(database):
    scope,factory,store,rid,prepare=setup(database,command_factory=content_generate_command)
    ContentExecutionWorker(factory,prepare=prepare,
        invoke=lambda *_:{'answer':'public result'},storage_schema=database.schema).run_one(scope,rid)
    runner=CurrentContentRunner(connect_factory=factory,storage_schema=database.schema)
    calls=[]
    runner.worker.invoke=lambda *_:pytest.fail('result drain must not send')
    runner.consumer=SimpleNamespace(consume=lambda conn,read_scope,read_id:calls.append(read_id))
    assert runner.run_recorded(scope)==[{'reservationId':rid,'status':'RESULT_RECORDED_UNSETTLED'}]
    assert calls==[rid]
