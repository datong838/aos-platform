"""Signed configuration sources, honest missing Eval/Health, no Provider calls."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
from aos_api.aip_provider_plugin_authority import ProviderPluginAuthority
from aos_api.aip_model_runtime_contracts import RegisteredModelRevision, ModelRouteRevision, RuntimePolicyRevision, ModelRuntimeLifecycle
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeDependencyBlocked, canonical_hash
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevisionCreate
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.db import connect
from aos_api.errors import register_exception_handlers
from aos_api.routers.aip_model_runtime import router
from tests.aip._runtime_guard_history_fixture import produce_formal_provider, seed_historical_runtime_guard, produce_formal_network_policy
from tests.aip.test_budget_cost_proposal_pg import case
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, command
from tests.aip.test_budget_cost_consumer_pg import caller, consume
from tests.aip.test_budget_cost_configuration_pg import derive
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE


def hashed(model, payload):
    item = model.model_validate({**payload, 'contentHash': '0'*64})
    body = item.model_dump(mode='json', by_alias=True)
    item.content_hash = canonical_hash({k:v for k,v in body.items() if k not in AipModelRuntimeStore._META_FIELDS})
    return item


def ref(kind, identity, item):
    return dict(assetType=kind,assetId=identity,revision=item.revision,contentHash=item.content_hash)


@pytest.fixture
def configuration(caller, issuer_factory, https_signer):
    maker, checker, _, proposal, key = case()
    uid = uuid4().hex
    provider = produce_formal_provider(SCOPE, maker.subject, 'model-provider-'+uid)
    plugin = ProviderPluginAuthority().validate_ref(SCOPE, provider.plugin_ref)
    # Read the existing manifest authority; no discovered/healthy model is invented.
    model_id = plugin.default_models[0]
    proposal.basis.provider = proposal.basis.provider.model_copy(update={
        'asset_id':provider.provider_instance_id,'content_hash':provider.content_hash})
    proposal.basis.provider_model_id = model_id
    saved = BudgetCostProposalStore().create(maker, proposal, key)
    decision = BudgetCostIssuer(issuer_factory).execute(command(https_signer[0], checker, saved))
    with caller() as conn:
        consume(conn,saved,decision)
        derived = derive(conn,saved,decision)['receipt']
    now = datetime.now(UTC)
    quota = seed_historical_runtime_guard(SCOPE,maker.subject,QuotaPolicyRevisionCreate(
        policyId='model-quota-'+uid,revision=1,environment='development',
        effectiveFrom=now-timedelta(minutes=1),effectiveUntil=now+timedelta(hours=1),
        owner=maker.subject,approvalRef='isolated-signed-quota',lifecycle='active',
        maxConcurrency=1,maxInputTokens=1000,maxOutputTokens=1000,
        hourlyRequestLimit=10,dailyRequestLimit=10,reservationLeaseSeconds=60,
        overflowBehavior='reject',allowPublicProviderFallback=False,allowAutoScale=False))
    quota_ref = ref('QuotaPolicyRevision',quota.policy_id,quota)
    common = dict(tenant=proposal.tenant,revision=1,lifecycle='validated',
                  createdBy=maker.subject,createdAt=now)
    model = hashed(RegisteredModelRevision,dict(**common,registeredModelId='model-'+uid,
        provider=ref('ProviderInstanceRevision',provider.provider_instance_id,provider),
        providerModelId=model_id,inputModalities=['text'],outputModalities=['text'],
        capabilities=['chat'],contextWindow=2000,quotaPolicyRef=quota_ref,
        budgetPolicyRef=derived['policyRef'],priceSnapshotRef=derived['priceRef']))
    network = produce_formal_network_policy(SCOPE,maker.subject,NetworkPolicyRevisionCreate(
        policyId='model-network-'+uid,revision=1,allowedSchemes=['https'],
        allowedHosts=['api.agnes-ai.cn'],allowedPorts=[443],tlsRequired=True,
        publicFallbackAllowed=False,egressPolicyRef=provider.egress_policy_ref,
        effectiveFrom=now-timedelta(minutes=1),effectiveUntil=now+timedelta(minutes=30),
        owner=maker.subject,approvalRef='isolated-network',lifecycle='active'))
    policy = hashed(RuntimePolicyRevision,dict(**common,policyId='model-policy-'+uid,
        networkPolicyRef=ref('NetworkPolicyRevision',network.policy_id,network),
        egressPolicyRef=provider.egress_policy_ref,dataClassificationPolicyRef=provider.data_classification_policy_ref,
        quotaPolicyRef=quota_ref,budgetPolicyRef=derived['policyRef'],deadlineMs=30000,maxAttempts=1,
        allowedFallbackReasons=[],unknownUsageBehavior='block',unknownPriceBehavior='block',killSwitchEnabled=True))
    app = FastAPI();register_exception_handlers(app);app.include_router(router)
    headers={'Authorization':'Bearer '+https_signer[0](maker.subject),'If-Match':'0',
             'X-Org-Id':SCOPE.org_id,'X-Project-Id':SCOPE.project_id}
    with TestClient(app) as client:
        def publish(path,item):
            response=client.post('/v1/aip/model-runtime/'+path,json=item.model_dump(mode='json',by_alias=True),
                headers={**headers,'Idempotency-Key':'configuration-'+uuid4().hex})
            assert response.status_code==201,response.text
            return type(item).model_validate(response.json())
        model=publish('models',model);policy=publish('policies',policy)
        route=hashed(ModelRouteRevision,dict(**common,routeId='route-'+uid,taskTypes=['copy.generate'],
            requiredInputModality='text',requiredOutputModality='text',requiredCapabilities=['chat'],
            candidates=[dict(model=ref('RegisteredModelRevision',model.registered_model_id,model),weight=100)],
            strategy='failover',runtimePolicyRef=ref('RuntimePolicyRevision',policy.policy_id,policy)))
        route=publish('routes',route)
        yield maker,model,route,provider,client,headers


def test_signed_configuration_is_readable_and_missing_eval_health_remain_blocked(configuration):
    _,model,route,provider,client,headers=configuration
    assert model.eval_gate_ref is None and route.eval_gate_ref is None
    resolution=AipModelRuntimeResolver().resolve(SCOPE,route.route_id)
    assert resolution.readiness.value=='blocked'
    assert {'route_eval_gate_not_passed','model_eval_gate_not_passed'} <= set(resolution.blocker_codes)
    assert resolution.selected_model is None
    response=client.get('/v1/aip/model-runtime/chain-overview',headers=headers)
    assert response.status_code==200,response.text
    chain = next(item for item in response.json()['chains'] if item['route']['assetId']==route.route_id)
    eval_node = next(item for item in chain['nodes'] if item['stage']=='eval')
    assert eval_node['status']=='blocked' and eval_node['exactRef'] is None
    with connect(SCOPE) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_provider_health_observation WHERE provider_ref->>\'assetId\'=%s',
            (provider.provider_instance_id,)).fetchone()['n']==0
    # Even model_copy cannot evade the original runtime exact gate.
    store=AipModelRuntimeStore()
    for item,publish in ((model,store.publish_model),(route,store.publish_route)):
        with pytest.raises(ModelRuntimeDependencyBlocked,match='eval gate is unavailable'):
            publish(SCOPE,item.created_by,'forbidden-'+uuid4().hex,
                item.model_copy(update={'lifecycle':ModelRuntimeLifecycle.ACTIVE}),expected_version=1)
