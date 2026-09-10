import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from test_aip_budget_reservation_pg import database, seed, seed_usage, runtime_connection, ROOT
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, BudgetReservationConflict, BudgetReservationBlocked, BudgetReservationNotFound, canonical_hash
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PostgreSQL opt-in')


def test_pending_execution_commits_and_replays_with_real_receipts(database):
    spec=importlib.util.spec_from_file_location('pending_migration', ROOT/'alembic/versions/a0v_002_cost_pending.py')
    migration=importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=database.owner.execute); migration.upgrade()
    scope=TenantScope('org-org','dev-project')
    now=datetime.now(UTC)
    request,refs,_=seed(database,scope,task_id='pending',now=now)
    row=database.owner.execute('SELECT payload FROM aip_model_price_snapshot_revision').fetchone()
    payload=row['payload']
    payload.update(inputTokenPrice=None,outputTokenPrice=None,cachedTokenPrice=None,
        developmentCostAuthorization=dict(tenant={'orgId':'org-org','projectId':'dev-project'},
            provider={'assetType':'ProviderInstanceRevision','assetId':'provider-1','revision':1,'contentHash':'3'*64},
            providerModelId='test-model',approvalRef='test-development',environment='development',
            effectiveFrom=(now-timedelta(days=1)).isoformat(),effectiveUntil=(now+timedelta(days=1)).isoformat()))
    payload['contentHash']=canonical_hash({k:v for k,v in payload.items() if k not in {'tenant','revision','contentHash','createdBy','createdAt'}})
    database.owner.execute('UPDATE aip_model_price_snapshot_revision SET content_hash=%s,payload=%s::jsonb',(payload['contentHash'],json.dumps(payload)))
    request=request.model_copy(update={'pricing_ref':refs['price'].model_copy(update={'content_hash':'sha256:'+payload['contentHash']})})
    store=AipBudgetReservationStore(runtime_connection(database),authority_schema=database.schema)
    held=store.reserve(scope,request,actor='tester')
    rid=held.reservation_ref.resource_id
    store.submit(scope,rid,provider_ref=refs['provider'],provider_idempotency_hash='8'*64,actor='tester')
    usage=seed_usage(database,scope,receipt_id='pending-usage',quantity=20,reservation_id=rid,provider_result_hash='9'*64)
    args=dict(provider_result_hash='9'*64,usage_receipt_refs=(usage,),evidence_refs=(),actor='tester')
    with pytest.raises(BudgetReservationBlocked):
        store.complete_cost_pending(scope,rid,**(args|{'provider_result_hash':'7'*64}))
    assert database.owner.execute('SELECT count(*) AS n FROM aip_capability_provider_receipt').fetchone()['n']==0
    result=store.complete_cost_pending(scope,rid,**args)
    assert result.state=='cost_pending' and result.actual_minor is None
    replay=store.complete_cost_pending(scope,rid,**args)
    assert replay.replayed and replay.reservation_ref==result.reservation_ref
    assert database.owner.execute('SELECT state FROM aip_capability_invocation').fetchone()['state']=='completed'
    assert database.owner.execute('SELECT count(*) AS n FROM aip_capability_provider_receipt').fetchone()['n']==1
    assert all(b.settled_minor==0 for b in result.buckets)
    with pytest.raises(BudgetReservationNotFound):
        store.complete_cost_pending(TenantScope('dev-org','dev-project'),rid,**args)
