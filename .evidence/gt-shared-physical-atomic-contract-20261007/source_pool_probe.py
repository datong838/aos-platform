"""Instrument an existing current signed Source fixture, never business admission."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from psycopg.types.json import Jsonb
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.aip_provider_capacity_occupation_source import consume_capacity_source_for_occupation
from tests.aip._runtime_guard_history_fixture import isolated_owner

BASE=Path(__file__).resolve().parent
SCOPE=('org-org','dev-project')
TARGET='test_occupation_source_consumption_uses_actual_business_caller'

def counterexample(caller,source,command,sign,subject):
    from aos_api.tenant_scope import TenantScope,apply_transaction_scope
    assert source.execution_allowed is False and len(source.provider_refs)>=2
    assert source.token_limit.mode=='inflight_upper_bound'
    limit=source.max_concurrency
    assert 1<=limit<=16 and source.token_limit.max_tokens>=limit+1
    scope=TenantScope(*SCOPE)
    providers=source.provider_refs[:2]
    suffix=uuid4().hex
    resolutions=[]
    with isolated_owner() as owner:
        mapping=owner.execute('''SELECT provider_id,account_id FROM aos_capacity_publication_private.global_provider
            WHERE provider_id IN (%s,%s) ORDER BY provider_id''',tuple(p.asset_id for p in providers)).fetchall()
        assert len(mapping)==2 and {str(row['account_id']) for row in mapping}=={str(source.physical_account_id)}
        for index,provider in enumerate(providers):
            def ref(kind,name):return VersionedAssetRef(assetType=kind,assetId='test:joint-probe:'+name+':'+suffix,revision=1,contentHash='c'*64)
            route=ref('ModelRouteRevision','route-'+str(index));model=ref('RegisteredModelRevision','model-'+str(index))
            pool='test:joint-probe:pool:'+str(index)+':'+suffix
            owner.execute('INSERT INTO aip_model_capacity_pool_head(org_id,project_id,pool_id,current_revision,version) VALUES (%s,%s,%s,1,1)',(*SCOPE,pool))
            owner.execute('''INSERT INTO aip_model_capacity_pool_revision
                (org_id,project_id,pool_id,revision,content_hash,route_ref,model_ref,provider_ref,
                 route_id,route_revision,route_hash,model_id,model_revision,model_hash,
                 provider_id,provider_revision,provider_hash,max_concurrency,max_token_units,
                 token_unit_per_reservation,lease_seconds,lifecycle,created_by)
                VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,1,%s,%s,1,%s,%s,%s,%s,%s,%s,1,300,'active','isolated-counterexample')''',
                (*SCOPE,pool,'c'*64,Jsonb(route.model_dump(mode='json',by_alias=True)),
                 Jsonb(model.model_dump(mode='json',by_alias=True)),Jsonb(provider.model_dump(mode='json',by_alias=True)),
                 route.asset_id,route.content_hash,model.asset_id,model.content_hash,provider.asset_id,
                 provider.revision,provider.content_hash,limit,source.token_limit.max_tokens))
            resolutions.append(ModelRouteResolution(tenant=TenantContext(orgId=SCOPE[0],projectId=SCOPE[1]),route=route,
                policy=ref('RuntimePolicyRevision','policy'),readiness=ModelRuntimeReadiness.READY,
                selectedModel=model,selectedProvider=VersionedAssetRef(assetType=provider.asset_type,
                    assetId=provider.asset_id,revision=provider.revision,contentHash=provider.content_hash),
                selectedPriceSnapshot=ref('ModelPriceSnapshotRevision','price'),
                blockerCodes=[],resolvedAt=datetime.now(UTC)))
    caller.execute("SET LOCAL TimeZone='UTC'")
    apply_transaction_scope(caller,scope)
    identity=caller.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    assert consume_capacity_source_for_occupation(caller,command.model_copy(update={'bearer_token':sign(subject)}))==source
    def forbidden(*args,**kwargs):raise AssertionError('Caller kernel opened another connection')
    gate=AipModelCapacityReservationGate(forbidden)
    held=[]
    for index in range(limit):
        held.append(gate.reserve_pool_in_transaction(caller,scope,resolutions[0],'test:joint-probe:'+suffix+':'+str(index)))
    held.append(gate.reserve_pool_in_transaction(caller,scope,resolutions[1],'test:joint-probe:'+suffix+':other'))
    assert caller.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()==identity
    with isolated_owner() as observer:
        assert observer.execute('SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE reservation_id=ANY(%s)',(held,)).fetchone()['n']==0
    caller.commit()
    with isolated_owner() as observer:
        observer.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        rows=observer.execute('''SELECT reservation_id,pool_id,request_units,token_units,status FROM aip_model_capacity_reservation
            WHERE reservation_id=ANY(%s) ORDER BY reservation_id''',(held,)).fetchall()
        events=observer.execute('SELECT count(*) AS n FROM aip_model_capacity_event WHERE reservation_id=ANY(%s)',(held,)).fetchone()['n']
        assert len(rows)==limit+1 and events==limit+1 and all(row['status']=='reserved' for row in rows)
        assert observer.execute("SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE org_id='dev-org'").fetchone()['n']==0
        assert observer.execute('SELECT count(*) AS n FROM aip_agent_run').fetchone()['n']==0
        cluster=str(observer.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier'])
        assert cluster=='7693564235776004128'
    result=dict(classification='CURRENT_SIGNED_SOURCE_PLUS_OLD_CALLER_POOLS_OVERSUBSCRIBE_ACCOUNT',
        database=caller.info.dbname,cluster=cluster,source_hash=source.content_hash if hasattr(source,'content_hash') else command.source_ref.content_hash,
        physical_account_id=str(source.physical_account_id),signed_concurrency_limit=limit,
        actual_committed_request_units=sum(row['request_units'] for row in rows),events=events,rows=rows,
        actual_caller=identity,execution_allowed=False,canary=0,
        limitations=['Synthetic Route/Model pool DTOs, no lawful business READY or AgentRun',
            'Not a physical joint Owner; no budget/Intent composition or fixed-window proof'])
    (BASE/'source-pool-counterexample.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
    print(result['classification'],'signed_limit=',limit,'committed=',len(rows),'same_xid_pid observer0beforecommit canary0',flush=True)

class ProbePlugin:
    module=None
    original=None
    def pytest_runtest_setup(self,item):
        if item.originalname==TARGET:
            self.module=item.module
            self.original=self.module._assert_occupation_epoch_concurrency
            def wrapped(*args):
                counterexample(*args)
                return self.original(*args)
            self.module._assert_occupation_epoch_concurrency=wrapped
    def pytest_runtest_teardown(self,item,nextitem):
        if self.module is not None:
            self.module._assert_occupation_epoch_concurrency=self.original
            self.module=None
