from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_development_cost_authorization import DevelopmentCostAuthorization, DeferredTokenCost
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 9, 11, tzinfo=UTC)
PROVIDER = VersionedAssetRef(assetType='ProviderInstanceRevision', assetId='provider', revision=1, contentHash='a' * 64)


def payload():
    return dict(tenant={'orgId': 'org-org', 'projectId': 'dev-project'}, provider=PROVIDER,
                providerModelId='model', approvalRef='development-approval',
                effectiveFrom=NOW, effectiveUntil=NOW + timedelta(days=1))


def arguments():
    return dict(scope=TenantScope('org-org', 'dev-project'), provider=PROVIDER,
                provider_model_id='model', approval_ref='development-approval', now=NOW)


@pytest.mark.parametrize('replacement', [
    {'tenant': {'orgId': 'dev-org', 'projectId': 'dev-project'}},
    {'environment': 'production'}, {'approvalRef': ' '},
    {'effectiveUntil': NOW}, {'effectiveFrom': NOW.replace(tzinfo=None)},
    {'provider': PROVIDER.model_copy(update={'asset_type': 'RegisteredModelRevision'})},
])
def test_development_contract_rejects_unapproved_values(replacement):
    with pytest.raises(ValidationError):
        DevelopmentCostAuthorization(**(payload() | replacement))


@pytest.mark.parametrize('replacement', [
    {'scope': TenantScope('dev-org', 'dev-project')},
    {'scope': TenantScope('org-org', 'other')},
    {'provider': PROVIDER.model_copy(update={'content_hash': 'b' * 64})},
    {'provider': PROVIDER.model_copy(update={'revision': 2})},
    {'provider_model_id': 'another'}, {'approval_ref': 'another'},
    {'now': NOW - timedelta(seconds=1)}, {'now': NOW + timedelta(days=1)},
    {'now': NOW.replace(tzinfo=None)},
])
def test_current_scope_must_match_exact_authorization(replacement):
    authorization = DevelopmentCostAuthorization(**payload())
    with pytest.raises(ValueError, match='scope_blocked'):
        authorization.require_scope(**(arguments() | replacement))


def test_effective_boundary_and_unknown_cost_are_explicit():
    authorization = DevelopmentCostAuthorization(**payload())
    authorization.require_scope(**arguments())
    value = DeferredTokenCost(inputTokens=3, outputTokens=2, totalTokens=5)
    body = value.model_dump(by_alias=True)
    assert body['amountMinor'] is None
    assert body['costStatus'] == 'deferred'
    assert body['usageQuality'] == 'measured'


@pytest.mark.parametrize('replacement', [
    {'amountMinor': 0}, {'costStatus': 'settled'}, {'usageQuality': 'estimated'},
    {'inputTokens': True}, {'inputTokens': 3.0}, {'inputTokens': -1}, {'totalTokens': 4},
])
def test_deferred_cost_never_fabricates_price_or_usage(replacement):
    with pytest.raises(ValidationError):
        DeferredTokenCost(**(dict(inputTokens=3, outputTokens=2, totalTokens=5) | replacement))
