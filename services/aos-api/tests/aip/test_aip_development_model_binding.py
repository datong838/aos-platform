from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_development_cost_authorization import DevelopmentCostAuthorization
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore, ModelGovernancePolicyDependencyBlocked
from aos_api.tenant_scope import TenantScope


def assembly():
    now = datetime.now(UTC)
    provider = VersionedAssetRef(assetType='ProviderInstanceRevision', assetId='p', revision=1, contentHash='a'*64)
    auth = DevelopmentCostAuthorization(tenant={'orgId':'org-org','projectId':'dev-project'},
        provider=provider, providerModelId='m', approvalRef='approved',
        effectiveFrom=now-timedelta(minutes=1), effectiveUntil=now+timedelta(minutes=1))
    budget = SimpleNamespace(development_cost_authorization=auth, approval_ref='approved')
    model = SimpleNamespace(quota_policy_ref='quota', budget_policy_ref='budget', provider=provider, provider_model_id='m')
    store = object.__new__(AipModelGovernancePolicyStore)
    reads = []
    def read(scope, ref):
        reads.append((scope.key, ref))
        return budget if ref == 'budget' else SimpleNamespace()
    store.require_exact_active = read
    return store, model, budget, reads


@pytest.mark.parametrize('drift', ['model','provider','approval','expired','tenant'])
def test_persisted_development_authorization_blocks_model_drift(drift):
    store, model, budget, reads = assembly()
    scope = TenantScope('org-org','dev-project')
    if drift == 'model': model.provider_model_id = 'other'
    if drift == 'provider': model.provider = model.provider.model_copy(update={'revision':2})
    if drift == 'approval': budget.approval_ref = 'other'
    if drift == 'expired': budget.development_cost_authorization.effective_until = datetime.now(UTC)-timedelta(seconds=1)
    if drift == 'tenant': scope = TenantScope('dev-org','dev-project')
    with pytest.raises(ModelGovernancePolicyDependencyBlocked):
        store.require_model_dependencies(scope, model)
    assert [r[1] for r in reads] == ['quota','budget']


def test_matching_and_legacy_models_keep_exact_policy_reads():
    store, model, budget, reads = assembly()
    scope = TenantScope('org-org','dev-project')
    store.require_model_dependencies(scope, model)
    budget.development_cost_authorization = None
    store.require_model_dependencies(scope, model)
    assert [r[1] for r in reads] == ['quota','budget','quota','budget']
