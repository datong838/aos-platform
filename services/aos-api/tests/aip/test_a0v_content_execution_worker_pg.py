import importlib.util
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from test_aip_budget_reservation_pg import database, seed, runtime_connection, ROOT
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
from aos_api.aip_model_runtime_contracts import ModelRouteResolution
from aos_api.ecommerce_content_execution_worker import ContentExecutionWorker, PreparedContentInvocation, ContentExecutionFailure
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PostgreSQL opt-in')


def setup(database):
    spec=importlib.util.spec_from_file_location('journal_migration',ROOT/'alembic/versions/a0v_003_content_execution_journal.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=database.owner.execute);migration.upgrade()
    scope=TenantScope('org-org','dev-project'); factory=runtime_connection(database)
    request,refs,_=seed(database,scope,task_id='worker',now=datetime.now(UTC))
    store=AipBudgetReservationStore(factory,authority_schema=database.schema)
    held=store.reserve(scope,request,actor='test'); rid=held.reservation_ref.resource_id
    with factory(scope) as conn:
        ContentExecutionJournal(storage_schema=database.schema).enqueue(conn,scope,rid,budget_request_hash=request.request_hash(),command={'requestHash':'a'*64})
    def ref(kind,identity,digest='a'*64):
        return dict(assetType=kind,assetId=identity,revision=1,contentHash=digest)
    resolution=ModelRouteResolution(tenant={'orgId':scope.org_id,'projectId':scope.project_id},
        route=ref('ModelRouteRevision','route'),policy=ref('RuntimePolicyRevision','policy'),readiness='ready',
        selectedModel=ref('RegisteredModelRevision','model'),selectedProvider=ref('ProviderInstanceRevision',refs['provider'].resource_id,refs['provider'].content_hash.removeprefix('sha256:')),
        selectedPriceSnapshot=ref('ModelPriceSnapshotRevision',refs['price'].resource_id,refs['price'].content_hash.removeprefix('sha256:')),resolvedAt=datetime.now(UTC))
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
