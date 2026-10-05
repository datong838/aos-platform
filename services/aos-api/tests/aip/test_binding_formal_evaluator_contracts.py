"""Transport rejection tests; accepted input never establishes business authority."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from aos_api.aip_binding_formal_evaluator_contracts import FormalBindingEvaluationRequest


def request_body():
    kinds = {
        'providerRef': 'ProviderInstanceRevision', 'modelRef': 'RegisteredModelRevision',
        'policyRef': 'RuntimePolicyRevision', 'routeRef': 'ModelRouteRevision',
        'priceRef': 'ModelPriceSnapshotRevision', 'capacityRef': 'ModelCapacityPoolRevision',
        'routeEvalGateRef': 'EvalGateDecision', 'modelEvalGateRef': 'EvalGateDecision',
        'evalContractRef': 'EvalContractRevision', 'budgetPolicyRef': 'BudgetPolicyRevision',
    }
    body = dict(schemaVersion=1, tenant={'orgId': 'org-org', 'projectId': 'dev-project'},
                expectedVersion=1, installationId='12345678-1234-4234-8234-123456789abc',
                installationRevision=1, installationEtag=1)
    for name, kind in kinds.items():
        body[name] = dict(assetType=kind, assetId=name, revision=1, contentHash='a' * 64)
    body['sourceRefs'] = [dict(assetType='EvidenceBundleRevision', assetId='source',
                               revision=1, contentHash='b' * 64)]
    body['dataDependencyRefs'] = []
    body['toolDependencyRefs'] = []
    return body


@pytest.mark.parametrize('field', ['actor', 'roles', 'ready', 'facts', 'clock', 'bearer', 'health'])
def test_client_cannot_supply_authority_or_server_facts(field):
    body = request_body()
    body[field] = 'untrusted'
    with pytest.raises(ValidationError):
        FormalBindingEvaluationRequest.model_validate(body)


@pytest.mark.parametrize('field', ['schemaVersion', 'expectedVersion', 'installationRevision', 'installationEtag'])
@pytest.mark.parametrize('value', [True, 1.0, '1', 0])
def test_versions_are_positive_strict_integers(field, value):
    body = request_body()
    body[field] = value
    with pytest.raises(ValidationError):
        FormalBindingEvaluationRequest.model_validate(body)


@pytest.mark.parametrize('fault', ['tenant', 'uuid', 'kind', 'hash', 'revision', 'blank', 'empty_source', 'duplicate'])
def test_exact_scope_and_reference_rejection(fault):
    body = request_body()
    if fault == 'tenant': body['tenant']['orgId'] = 'dev-org'
    elif fault == 'uuid': body['installationId'] = body['installationId'].upper()
    elif fault == 'kind': body['providerRef']['assetType'] = 'RegisteredModelRevision'
    elif fault == 'hash': body['providerRef']['contentHash'] = 'A' * 64
    elif fault == 'revision': body['providerRef']['revision'] = True
    elif fault == 'blank': body['providerRef']['assetId'] = ' source '
    elif fault == 'empty_source': body['sourceRefs'] = []
    else: body['sourceRefs'].append(deepcopy(body['sourceRefs'][0]))
    with pytest.raises(ValidationError):
        FormalBindingEvaluationRequest.model_validate(body)


def test_reparse_does_not_trust_mutated_model_instances():
    parsed = FormalBindingEvaluationRequest.model_validate(request_body())
    mutated = parsed.model_copy(update={'provider_ref': parsed.provider_ref.model_copy(update={'revision': True})})
    with pytest.raises(ValidationError):
        FormalBindingEvaluationRequest.model_validate(mutated)


def test_transport_acceptance_has_no_ready_or_authorization_result():
    parsed = FormalBindingEvaluationRequest.model_validate(request_body())
    assert parsed.model_dump(by_alias=True) == request_body()
    assert not hasattr(parsed, 'ready')


@pytest.mark.parametrize('field', list(request_body()))
def test_no_required_dependency_or_scope_can_be_omitted(field):
    body = request_body()
    del body[field]
    with pytest.raises(ValidationError):
        FormalBindingEvaluationRequest.model_validate(body)


@pytest.mark.parametrize('field', ['sourceRefs', 'dataDependencyRefs', 'toolDependencyRefs'])
def test_unknown_authority_and_multiple_revisions_of_one_resource_are_rejected(field):
    body = request_body()
    ref = deepcopy(body['sourceRefs'][0])
    ref['assetType'] = 'ClientAssertedReady'
    body[field] = [ref]
    with pytest.raises(ValidationError):
        FormalBindingEvaluationRequest.model_validate(body)
    ref['assetType'] = 'EvidenceBundleRevision'
    other = {**ref, 'revision': 2}
    body[field] = [ref, other]
    with pytest.raises(ValidationError):
        FormalBindingEvaluationRequest.model_validate(body)


def test_model_construct_and_mutated_tenant_still_require_validation():
    parsed = FormalBindingEvaluationRequest.model_validate(request_body())
    for mutated in (
        parsed.model_copy(update={'schema_version': True}),
        parsed.model_copy(update={'tenant': parsed.tenant.model_copy(update={'org_id': 'dev-org'})}),
        FormalBindingEvaluationRequest.model_construct(**{**parsed.__dict__, 'installation_etag': '1'}),
    ):
        with pytest.raises(ValidationError):
            FormalBindingEvaluationRequest.model_validate(mutated)
