"""Original publication prefix, isolated only; no synthetic active Model rows."""
from datetime import datetime, UTC
from uuid import uuid4
from pathlib import Path
import json
import pytest
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope
from aos_api.aip_model_runtime_contracts import RegisteredModelRevision
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, canonical_hash
from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from tests.aip.test_budget_cost_consumer_pg import caller, consume
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, command
pytest_plugins = ('tests.conftest',)

def create_prefix(caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path):
    from tests.aip.test_budget_cost_proposal_pg import case
    from tests.aip._runtime_guard_history_fixture import produce_formal_provider
    from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
    from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
    from tests.aip.test_budget_cost_configuration_pg import derive
    from tests.aip.test_quota_policy_activation_pg import approved_quota
    from tests.aip.test_guard_policy_activation_pg import guard_consume_command
    from aos_api.aip_quota_policy_consumer import QuotaPolicyConsumer
    from psycopg.conninfo import conninfo_to_dict
    scope=TenantScope('org-org','dev-project');suffix=uuid4().hex
    maker,checker,_,basis,key=case()
    provider=produce_formal_provider(scope,maker.subject,'joint-prefix-provider-'+suffix)
    basis.basis.provider=basis.basis.provider.model_copy(update={'asset_id':provider.provider_instance_id,'content_hash':provider.content_hash})
    saved=BudgetCostProposalStore().create(maker,basis,key)
    decision=BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],checker,saved))
    with caller() as c:
        consume(c,saved,decision); configured=derive(c,saved,decision)
    refs=configured['receipt'];runtime=AipModelRuntimeStore()
    price=runtime.get_price_snapshot(scope,refs['priceRef']['assetId'],refs['priceRef']['revision'])
    qm,_,bundle,_,approval=approved_quota(https_signer[0],guard_issuer_factory,tmp_path)
    factory,database=guard_consumer_factory;folder=tmp_path/'model-prefix-quota';folder.mkdir(mode=0o700)
    quota_result=QuotaPolicyConsumer(factory,folder,expected_database=database).execute(guard_consume_command(https_signer[0],qm,bundle,approval))
    assert quota_result['status']=='observed'
    qr=quota_result['result'];quota=AipModelGovernancePolicyStore().require_exact_active(scope,VersionedAssetRef(assetType=qr['resourceType'],assetId=qr['resourceId'],revision=qr['revision'],contentHash=qr['contentHash']))
    def ref(kind,identity,revision,digest):return dict(assetType=kind,assetId=identity,revision=revision,contentHash=digest)
    raw=dict(tenant=dict(orgId=scope.org_id,projectId=scope.project_id),registeredModelId='joint-prefix-model-'+suffix,revision=1,contentHash='0'*64,
        provider=ref('ProviderInstanceRevision',provider.provider_instance_id,provider.revision,provider.content_hash),providerModelId=basis.basis.provider_model_id,
        inputModalities=['text'],outputModalities=['text'],capabilities=['text-generation'],contextWindow=8000,
        quotaPolicyRef=ref('QuotaPolicyRevision',quota.policy_id,quota.revision,quota.content_hash),budgetPolicyRef=refs['policyRef'],
        priceSnapshotRef=ref('ModelPriceSnapshotRevision',price.price_snapshot_id,price.revision,price.content_hash),evalGateRef=None,
        lifecycle='validated',createdBy=maker.subject,createdAt=datetime.now(UTC))
    draft=RegisteredModelRevision.model_validate(raw);payload=draft.model_dump(mode='json',by_alias=True)
    draft=draft.model_copy(update={'content_hash':canonical_hash({k:v for k,v in payload.items() if k not in runtime._META_FIELDS})})
    model=runtime.publish_model(scope,maker.subject,'model-prefix-'+suffix,draft,expected_version=0)
    assert runtime.get_model(scope,model.registered_model_id).content_hash==model.content_hash
    with connect(scope) as c:
        head=c.execute('SELECT current_revision,version FROM aip_registered_model_head WHERE org_id=%s AND project_id=%s AND registered_model_id=%s',(*scope.key,model.registered_model_id)).fetchone()
        receipts=c.execute("SELECT count(*) AS n FROM aip_model_runtime_receipt WHERE operation='registered_model.publish' AND idempotency_key=%s",('model-prefix-'+suffix,)).fetchone()['n']
    assert head=={'current_revision':1,'version':1} and receipts==1
    with connect(TenantScope('dev-org','dev-project')) as c:
        assert c.execute('SELECT count(*) AS n FROM aip_registered_model_revision').fetchone()['n']==0
    output={'status':'LEGAL_MODEL_PUBLICATION_PREFIX_ONLY','database':conninfo_to_dict(get_dsn())['dbname'],'model_id':model.registered_model_id,'model_hash':model.content_hash,'model_head':head,'publication_receipts':receipts,'quota_ref':raw['quotaPolicyRef'],'budget_refs':refs,'pending':['Original Suite/Contract governance provenance','Eval request approval and unique execution Intent','Joint physical transaction'],'no_provider_execution':True}
    (Path(__file__).parent/'legal-model-prefix-application-r4.json').write_text(json.dumps(output,indent=2)+'\n')
