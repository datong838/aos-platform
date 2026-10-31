"""Offline full-subject binding; none of these fixtures is execution authority."""
import json
from datetime import UTC, datetime

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_route_eval_subject_binding import canonical_eval_subject_binding_bytes
from aos_api.aip_model_runtime_contracts import (
    ModelEvalCandidate, ModelRouteRevision, ModelRuntimeLifecycle, ModelModality, RouteStrategy,
    RegisteredModelRevision, RuntimePolicyRevision,
)
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore, canonical_hash, evaluation_candidate_ref,
)
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')
TENANT = {'orgId': SCOPE.org_id, 'projectId': SCOPE.project_id}
NOW = datetime(2026, 10, 28, tzinfo=UTC)


def ref(kind, name):
    return VersionedAssetRef(assetType=kind, assetId=name, revision=1, contentHash='a' * 64)


def seal(item):
    body = item.model_dump(mode='json', by_alias=True)
    digest = canonical_hash({k: v for k, v in body.items() if k not in AipModelRuntimeStore._META_FIELDS})
    return item.model_copy(update={'content_hash': digest})


def model(name='m1', *, lifecycle='active'):
    return seal(RegisteredModelRevision(
        tenant=TENANT, registeredModelId=name, revision=1, contentHash='a' * 64,
        provider=ref('ProviderInstanceRevision', 'provider'), providerModelId=name,
        inputModalities=['text'], outputModalities=['text'], capabilities=['structured_output'],
        contextWindow=4096, quotaPolicyRef=ref('QuotaPolicyRevision', 'quota'),
        budgetPolicyRef=ref('BudgetPolicyRevision', 'budget'),
        priceSnapshotRef=ref('ModelPriceSnapshotRevision', 'price'),
        evalGateRef=ref('EvalGateDecision', 'model-gate') if lifecycle == 'active' else None,
        lifecycle=lifecycle, createdBy='offline-test', createdAt=NOW,
    ))


def exact_ref(item, kind, name):
    return VersionedAssetRef(assetType=kind, assetId=name, revision=item.revision, contentHash=item.content_hash)


def inputs(*, weighted=False):
    models = [model(), model('m2')]
    policy = seal(RuntimePolicyRevision(
        tenant=TENANT, policyId='policy', revision=1, contentHash='a' * 64,
        networkPolicyRef=ref('NetworkPolicyRevision', 'network'),
        egressPolicyRef=ref('EgressPolicyRevision', 'egress'),
        dataClassificationPolicyRef=ref('DataClassificationPolicyRevision', 'data'),
        quotaPolicyRef=ref('QuotaPolicyRevision', 'quota'),
        budgetPolicyRef=ref('BudgetPolicyRevision', 'budget'),
        deadlineMs=30000, maxAttempts=1, unknownUsageBehavior='block', unknownPriceBehavior='block',
        killSwitchEnabled=False, lifecycle='active', createdBy='offline-test', createdAt=NOW,
    ))
    route = seal(ModelRouteRevision(
        tenant=TENANT, routeId='route', revision=2, contentHash='a' * 64,
        taskTypes=['copy.generate'], requiredInputModality='text', requiredOutputModality='text',
        requiredCapabilities=['structured_output'],
        candidates=[{'model': exact_ref(m, 'RegisteredModelRevision', m.registered_model_id),
                     'weight': ([100, 0][i] if weighted else 100)} for i, m in enumerate(models)],
        strategy='weighted' if weighted else 'failover',
        runtimePolicyRef=exact_ref(policy, 'RuntimePolicyRevision', 'policy'),
        lifecycle='draft', createdBy='offline-test', createdAt=NOW,
    ))
    return route, models, policy


def candidate(source):
    return ModelEvalCandidate(
        sourceRef=evaluation_candidate_ref(source).model_copy(update={'content_hash': source.content_hash}),
        targetRef=evaluation_candidate_ref(source.model_copy(update={
            'revision': source.revision + 1, 'lifecycle': ModelRuntimeLifecycle.ACTIVE, 'eval_gate_ref': None})),
        expectedHeadVersion=7, sourceLifecycle=source.lifecycle.value,
    )


def bind(source, models=(), policy=None, *, claim=None, scope=SCOPE):
    return canonical_eval_subject_binding_bytes(scope, candidate(source) if claim is None else claim,
                                               source, models=models, runtime_policy=policy)


def test_binds_complete_model_and_route_and_never_grants_execution():
    source = model(lifecycle='draft')
    assert b'RegisteredModelRevision' in bind(source)
    route, models, policy = inputs()
    raw = bind(route, models, policy)
    body = json.loads(raw.split(b'\n', 1)[1])
    assert body['executionAllowed'] is False
    assert body['source'] == route.model_dump(mode='json', by_alias=True)
    assert body['models'] == [m.model_dump(mode='json', by_alias=True) for m in models]
    assert body['runtimePolicy'] == policy.model_dump(mode='json', by_alias=True)
    assert raw == bind(route, list(reversed(models)), policy)
    models[0].capabilities.append('later-mutation')
    assert b'later-mutation' not in raw


@pytest.mark.parametrize('change', ['missing', 'extra', 'duplicate', 'zero_weight_missing'])
def test_cannot_replace_route_with_one_easy_model(change):
    route, models, policy = inputs(weighted=change == 'zero_weight_missing')
    if change in {'missing', 'zero_weight_missing'}: models = models[:1]
    elif change == 'extra': models.append(model('m3'))
    else: models.append(models[0])
    with pytest.raises(ValueError): bind(route, models, policy)


@pytest.mark.parametrize('field', ['strategy', 'order', 'weights', 'policy'])
def test_full_route_semantics_change_the_bound_bytes(field):
    route, models, policy = inputs()
    original = bind(route, models, policy)
    if field == 'strategy': route = route.model_copy(update={'strategy': RouteStrategy.LOWEST_COST})
    elif field == 'order': route = route.model_copy(update={'candidates': list(reversed(route.candidates))})
    elif field == 'weights':
        route = route.model_copy(update={'strategy': RouteStrategy.WEIGHTED, 'candidates': [
            c.model_copy(update={'weight': 50}) for c in route.candidates]})
    else:
        policy = seal(policy.model_copy(update={'deadline_ms': 40000}))
        route = route.model_copy(update={'runtime_policy_ref': exact_ref(policy, 'RuntimePolicyRevision', 'policy')})
    route = seal(ModelRouteRevision.model_validate(route.model_dump()))
    assert bind(route, models, policy) != original


@pytest.mark.parametrize('change', [
    'source_hash', 'model_hash', 'policy_hash', 'source_org', 'model_project', 'policy_org',
    'head_bool', 'source_revision_bool', 'model_ref_revision_bool', 'extra_field',
    'execution_zero', 'execution_true', 'wrong_target', 'source_ref_hash', 'source_lifecycle',
    'policy_missing', 'policy_kill', 'policy_inactive', 'model_inactive', 'modality', 'capability',
])
def test_rejects_drift_and_unvalidated_copied_objects(change):
    route, models, policy = inputs()
    claim = candidate(route)
    if change == 'source_hash': route = route.model_copy(update={'content_hash': 'b' * 64})
    elif change == 'model_hash': models[0] = models[0].model_copy(update={'content_hash': 'b' * 64})
    elif change == 'policy_hash': policy = policy.model_copy(update={'content_hash': 'b' * 64})
    elif change == 'source_org': route = route.model_copy(update={'tenant': {'orgId': 'dev-org', 'projectId': SCOPE.project_id}})
    elif change == 'model_project': models[0] = models[0].model_copy(update={'tenant': {'orgId': SCOPE.org_id, 'projectId': 'other'}})
    elif change == 'policy_org': policy = policy.model_copy(update={'tenant': {'orgId': 'dev-org', 'projectId': SCOPE.project_id}})
    elif change == 'head_bool': claim = claim.model_copy(update={'expected_head_version': True})
    elif change == 'source_revision_bool': route = route.model_copy(update={'revision': True})
    elif change == 'model_ref_revision_bool':
        route = route.model_copy(update={'candidates': [route.candidates[0].model_copy(update={
            'model': route.candidates[0].model.model_copy(update={'revision': True})}), route.candidates[1]]})
    elif change == 'extra_field': route = route.model_copy(update={'ignored_authority': True})
    elif change == 'execution_zero': claim = claim.model_copy(update={'execution_allowed': 0})
    elif change == 'execution_true': claim = claim.model_copy(update={'execution_allowed': True})
    elif change == 'wrong_target': claim = claim.model_copy(update={'target_ref': claim.source_ref})
    elif change == 'source_ref_hash': claim = claim.model_copy(update={'source_ref': claim.source_ref.model_copy(update={'content_hash': 'b' * 64})})
    elif change == 'source_lifecycle': claim = claim.model_copy(update={'source_lifecycle': 'validated'})
    elif change == 'policy_missing': policy = None
    elif change == 'policy_kill': policy = seal(policy.model_copy(update={'kill_switch_enabled': True}))
    elif change == 'policy_inactive': policy = seal(policy.model_copy(update={'lifecycle': ModelRuntimeLifecycle.DRAFT}))
    elif change == 'model_inactive': models[0] = seal(models[0].model_copy(update={'lifecycle': ModelRuntimeLifecycle.DRAFT}))
    elif change == 'modality': models[0] = seal(models[0].model_copy(update={'input_modalities': [ModelModality.IMAGE]}))
    elif change == 'capability': models[0] = seal(models[0].model_copy(update={'capabilities': ['other']}))
    # Keep all unrelated hashes/references consistent so these cases exercise
    # actual lifecycle/capability/policy gates rather than an earlier hash gate.
    if change in {'policy_kill', 'policy_inactive'}:
        route = seal(route.model_copy(update={'runtime_policy_ref': exact_ref(policy, 'RuntimePolicyRevision', 'policy')}))
        claim = candidate(route)
    if change in {'model_inactive', 'modality', 'capability'}:
        route = seal(route.model_copy(update={'candidates': [
            c.model_copy(update={'model': exact_ref(m, 'RegisteredModelRevision', m.registered_model_id)})
            for c, m in zip(route.candidates, models)]}))
        claim = candidate(route)
    with pytest.raises(ValueError): bind(route, models, policy, claim=claim)


def test_model_does_not_accept_extra_route_dependencies_or_wrong_scope():
    source = model(lifecycle='draft')
    _, models, policy = inputs()
    for deps, pol in [(models, None), ((), policy)]:
        with pytest.raises(ValueError): bind(source, deps, pol)
    with pytest.raises(ValueError): bind(source, scope=TenantScope('dev-org', 'dev-project'))
