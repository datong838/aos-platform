"""New original fixed-window approval and signed Source; never business execution."""
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
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

def new_rate_approval(material,approved_command):
    from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityBasisCandidate
    from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
    from aos_api.aip_provider_capacity_source_action import propose_provider_capacity_source,decide_provider_capacity_source
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_action_store import canonical_hash
    from aos_api.tenant_scope import TenantScope
    f,old_command,basis,source,config=material
    maker,checker=approved_command[:2]
    raw=basis.model_dump(mode='python',by_alias=True)
    raw['tokenLimit']=dict(mode='fixed_window_rate',unit='token',maxTokens=basis.token_limit.max_tokens,
        windowSeconds=60,windowAnchor=f['now'])
    basis=ProviderCapacityBasisCandidate.model_validate(raw)
    saved=ProviderCapacityCandidateStore().create_basis(TenantScope(*SCOPE),maker,'fixed-window-basis-'+uuid4().hex,basis)
    source=source.model_copy(update={'basis_ref':FormalExactRef(assetType='ProviderCapacityBasisCandidateRevision',
        assetId=saved['candidate_id'],revision=1,contentHash=saved['content_hash'])})
    proposal=propose_provider_capacity_source(maker,source,'fixed-window-proposal-'+uuid4().hex,source.valid_until)
    approved=decide_provider_capacity_source(checker,proposal.proposal.id,'fixed-window-approve-'+uuid4().hex,
        DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,
            expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',
            reason='isolated original fixed-window counterexample',approvalExpiresAt=source.valid_until))
    f['attestation']['tokenLimit']=basis.token_limit.model_dump(mode='python',by_alias=True)
    f['attestation']['observedAt']=basis.observed_at
    f['policy']['allowedTokenModes']=[basis.token_limit.mode]
    def actual_command():
        command,policy,attestation=old_command()
        return command.model_copy(update={
            'approved_proposal':FormalExactRef(assetType='ActionProposal',assetId=approved.proposal.id,
                revision=2,contentHash=approved.proposal.proposal_hash),
            'approval_event':FormalExactRef(assetType='ActionApprovalEvent',assetId=approved.approvals[0].id,
                revision=1,contentHash=canonical_hash(approved.approvals[0].model_dump(mode='json',by_alias=True)))}),policy,attestation
    return f,actual_command,basis,source,config

def counterexample(caller,source,command,sign,subject):
    from aos_api.tenant_scope import TenantScope,apply_transaction_scope
    assert source.execution_allowed is False and len(source.provider_refs)==3
    assert source.token_limit.mode=='fixed_window_rate' and source.max_concurrency>=2
    quantum=source.token_limit.max_tokens//2+1
    assert quantum<=source.token_limit.max_tokens
    providers=source.provider_refs[:2]
    suffix=uuid4().hex
    resolutions=[]
    with isolated_owner() as owner:
        mapping=owner.execute('SELECT provider_id,account_id FROM aos_capacity_publication_private.global_provider WHERE provider_id=ANY(%s)',([p.asset_id for p in providers],)).fetchall()
        assert len(mapping)==2 and {str(x['account_id']) for x in mapping}=={str(source.physical_account_id)}
        for index,provider in enumerate(providers):
            def ref(kind,name):return VersionedAssetRef(assetType=kind,assetId='test:fixed-window:'+name+':'+suffix,revision=1,contentHash='d'*64)
            route=ref('ModelRouteRevision','route-'+str(index));model=ref('RegisteredModelRevision','model-'+str(index))
            pool='test:fixed-window:pool:'+str(index)+':'+suffix
            owner.execute('INSERT INTO aip_model_capacity_pool_head(org_id,project_id,pool_id,current_revision,version) VALUES(%s,%s,%s,1,1)',(*SCOPE,pool))
            owner.execute('''INSERT INTO aip_model_capacity_pool_revision
                (org_id,project_id,pool_id,revision,content_hash,route_ref,model_ref,provider_ref,
                 route_id,route_revision,route_hash,model_id,model_revision,model_hash,
                 provider_id,provider_revision,provider_hash,max_concurrency,max_token_units,
                 token_unit_per_reservation,lease_seconds,lifecycle,created_by)
                VALUES(%s,%s,%s,1,%s,%s,%s,%s,%s,1,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,300,'active','isolated-fixed-window')''',
                (*SCOPE,pool,'d'*64,Jsonb(route.model_dump(mode='json',by_alias=True)),
                 Jsonb(model.model_dump(mode='json',by_alias=True)),Jsonb(provider.model_dump(mode='json',by_alias=True)),
                 route.asset_id,route.content_hash,model.asset_id,model.content_hash,provider.asset_id,
                 provider.revision,provider.content_hash,source.max_concurrency,source.token_limit.max_tokens,quantum))
            resolutions.append(ModelRouteResolution(tenant=TenantContext(orgId=SCOPE[0],projectId=SCOPE[1]),route=route,
                policy=ref('RuntimePolicyRevision','policy'),readiness=ModelRuntimeReadiness.READY,
                selectedModel=model,selectedProvider=VersionedAssetRef(assetType=provider.asset_type,
                    assetId=provider.asset_id,revision=provider.revision,contentHash=provider.content_hash),
                selectedPriceSnapshot=ref('ModelPriceSnapshotRevision','price'),blockerCodes=[],resolvedAt=datetime.now(UTC)))
    caller.execute("SET LOCAL TimeZone='UTC'")
    scope=TenantScope(*SCOPE);apply_transaction_scope(caller,scope)
    identity=caller.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    assert consume_capacity_source_for_occupation(caller,command.model_copy(update={'bearer_token':sign(subject)}))==source
    def clock():
        return caller.execute('SELECT clock_timestamp() AS at,floor(extract(epoch FROM (clock_timestamp()-%s::timestamptz))/%s)::bigint AS window_index',
            (source.token_limit.window_anchor,source.token_limit.window_seconds)).fetchone()
    start=clock()
    def forbidden(*args,**kwargs):raise AssertionError('Caller kernel opened another connection')
    gate=AipModelCapacityReservationGate(forbidden)
    held=[gate.reserve_pool_in_transaction(caller,scope,r,'test:fixed-window:'+suffix+':'+str(i)) for i,r in enumerate(resolutions)]
    finish=clock();assert finish['window_index']==start['window_index'] and start['window_index']>=0
    assert caller.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()==identity
    with isolated_owner() as observer:
        assert observer.execute('SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE reservation_id=ANY(%s)',(held,)).fetchone()['n']==0
    caller.commit()
    with isolated_owner() as observer:
        observer.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        rows=observer.execute('SELECT reservation_id,pool_id,request_units,token_units,status FROM aip_model_capacity_reservation WHERE reservation_id=ANY(%s) ORDER BY reservation_id',(held,)).fetchall()
        events=observer.execute('SELECT count(*) AS n FROM aip_model_capacity_event WHERE reservation_id=ANY(%s)',(held,)).fetchone()['n']
        assert len(rows)==events==2 and all(x['status']=='reserved' for x in rows)
        assert sum(x['token_units'] for x in rows)>source.token_limit.max_tokens
        assert sum(x['request_units'] for x in rows)<=source.max_concurrency
        assert observer.execute('SELECT count(*) AS n FROM aip_agent_run').fetchone()['n']==0
        assert observer.execute("SELECT count(*) AS n FROM aip_model_capacity_reservation WHERE org_id='dev-org'").fetchone()['n']==0
        cluster=str(observer.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier'])
        assert cluster=='7693564235776004128'
    result=dict(classification='SIGNED_FIXED_WINDOW_SOURCE_OLD_POOLS_EXCEED_SHARED_TOKEN_UPPER_BOUND',
        database=caller.info.dbname,cluster=cluster,source_hash=command.source_ref.content_hash,
        physical_account_id=str(source.physical_account_id),token_limit=source.token_limit.model_dump(mode='json',by_alias=True),
        signed_concurrency_limit=source.max_concurrency,actual_request_units=sum(x['request_units'] for x in rows),
        actual_token_units=sum(x['token_units'] for x in rows),rows=rows,events=events,actual_caller=identity,
        window_start_observation=start,window_finish_observation=finish,execution_allowed=False,canary=0,
        limitations=['Synthetic Route/Model DTOs; no lawful business admission or AgentRun',
            'Reserved upper bounds only, not actual token spend; no budget/Intent/window-roll or unknown release proof'])
    (BASE/'fixed-window-counterexample.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
    print(result['classification'],'signed_tokens=',source.token_limit.max_tokens,'reserved_tokens=',result['actual_token_units'],
        'same_window same_xid_pid observer0beforecommit concurrency_within_limit canary0',flush=True)

class ProbePlugin:
    publication=None
    occupation=None
    old_distinct=None
    old_epoch=None
    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self,item):
        if item.originalname==TARGET:
            from tests.aip import test_capacity_source_publication_transaction_pg as publication
            self.publication=publication;self.occupation=item.module
            self.old_distinct=publication._distinct_native_fact_material
            self.old_epoch=item.module._assert_occupation_epoch_concurrency
            def distinct(material,approved):return new_rate_approval(self.old_distinct(material,approved),approved)
            def epoch(*args):
                counterexample(*args)
                return self.old_epoch(*args)
            publication._distinct_native_fact_material=distinct
            item.module._assert_occupation_epoch_concurrency=epoch
    def pytest_runtest_teardown(self,item,nextitem):
        if self.publication is not None:
            self.publication._distinct_native_fact_material=self.old_distinct
            self.occupation._assert_occupation_epoch_concurrency=self.old_epoch
            self.publication=None
