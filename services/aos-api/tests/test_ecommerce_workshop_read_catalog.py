"""Candidate read gate tests; no HTTP activation or real database effects."""
from types import SimpleNamespace
import pytest
from aos_api.asset_registry.errors import AssetNotFoundError, RegistryIntegrityCorruptError
from tests.asset_registry.test_ecommerce_installed_readonly_catalog import catalog
from tests.asset_registry.test_ecommerce_workshop_catalog import _active, _persisted, _loaded_growth

ARGS = dict(module_id='ecommerce.customer', org_id='org-org', project_id='dev-project', roles=['operator'], markings=['public'])

class MissingLegacy:
    def get_readiness(self, **kwargs):
        raise AssetNotFoundError('Workshop module is not installed')

def make(*, granted=True):
    from aos_api.ecommerce_workshop_read_catalog import EcommerceWorkshopReadCatalog
    loaded = _loaded_growth()
    scopes = sorted({s for m in loaded.workshop_modules for s in m.permissions.data_scopes}) if granted else []
    installed, source = catalog([_active(_persisted(loaded), target_data_scopes=scopes)])
    return EcommerceWorkshopReadCatalog(legacy=MissingLegacy(), installed=installed), source

def test_exact_granted_installed_asset_can_pass_read_gate_without_runtime_promotion():
    c, _ = make()
    result = c.get_readiness(**ARGS)
    assert result.item.module_id == ARGS['module_id']
    assert result.item.readiness.value == 'disabled'
    assert any(b.reason_code == 'INSTALLED_ASSET_READONLY' for b in result.item.blockers)

def test_declared_scope_without_current_lock_grant_is_rejected():
    c, _ = make(granted=False)
    with pytest.raises(AssetNotFoundError): c.get_readiness(**ARGS)

@pytest.mark.parametrize('changes', [{'org_id':'dev-org'}, {'project_id':'other'}])
def test_cross_tenant_denied_before_candidate_source_access(changes):
    c, source = make()
    with pytest.raises(AssetNotFoundError): c.get_readiness(**{**ARGS, **changes})
    assert source.calls == []

def test_installation_revocation_is_checked_each_time():
    c, source = make()
    c.get_readiness(**ARGS)
    source.rows = []
    with pytest.raises(AssetNotFoundError): c.get_readiness(**ARGS)
    assert len(source.calls) == 2

def test_legacy_success_is_preserved_without_reading_candidate():
    from aos_api.ecommerce_workshop_read_catalog import EcommerceWorkshopReadCatalog
    sentinel = object()
    c = EcommerceWorkshopReadCatalog(legacy=SimpleNamespace(get_readiness=lambda **kw: sentinel), installed=None)
    assert c.get_readiness(**ARGS) is sentinel

def test_legacy_integrity_error_never_falls_back():
    from aos_api.ecommerce_workshop_read_catalog import EcommerceWorkshopReadCatalog
    def corrupt(**kwargs): raise RegistryIntegrityCorruptError()
    c = EcommerceWorkshopReadCatalog(legacy=SimpleNamespace(get_readiness=corrupt), installed=None)
    with pytest.raises(RegistryIntegrityCorruptError): c.get_readiness(**ARGS)

def test_grant_reference_must_match_current_exact_lock():
    c, _ = make()
    result = c.get_readiness(**ARGS)
    refs = [r.model_copy(update={'content_hash':'sha256:'+'f'*64}) if r.resource_type == 'DataScopeGrant' else r for r in result.item.dependency_refs]
    item = result.item.model_copy(update={'dependency_refs':refs})
    c._installed = SimpleNamespace(get_readiness=lambda **kw: result.model_copy(update={'item':item}))
    with pytest.raises(AssetNotFoundError): c.get_readiness(**ARGS)

@pytest.mark.parametrize('field,value', [('revision','installation:4/lock:1'), ('authority','client:declaration')])
def test_grant_from_another_revision_or_authority_is_rejected(field, value):
    c, _ = make()
    result = c.get_readiness(**ARGS)
    refs = [r.model_copy(update={field:value}) if r.resource_type == 'DataScopeGrant' else r for r in result.item.dependency_refs]
    c._installed = SimpleNamespace(get_readiness=lambda **kw: result.model_copy(update={'item':result.item.model_copy(update={'dependency_refs':refs})}))
    with pytest.raises(AssetNotFoundError): c.get_readiness(**ARGS)

def test_candidate_bundle_content_drift_is_not_hidden_by_fallback():
    from dataclasses import replace
    c, source = make()
    row = source.rows[0]
    source.rows = [replace(row, bundle=replace(row.bundle, content_hash='sha256:'+'f'*64))]
    with pytest.raises(RegistryIntegrityCorruptError): c.get_readiness(**ARGS)

@pytest.mark.parametrize('changes', [{'roles':[]}, {'markings':[]}])
def test_original_role_and_marking_filter_still_denies_installed_candidate(changes):
    c, _ = make()
    loaded = _loaded_growth()
    modules = [m.model_copy(update={'permissions':m.permissions.model_copy(update={'roles':['operator'],'markings':['public']})}) for m in loaded.workshop_modules]
    # Permission boundary fixture only, not independently signed production proof.
    c._installed._loader = SimpleNamespace(load=lambda ref: loaded.model_copy(update={'workshop_modules':modules}))
    with pytest.raises(AssetNotFoundError): c.get_readiness(**{**ARGS, **changes})

def test_metadata_projection_with_registry_blocker_cannot_open_business_read():
    from aos_api.ecommerce_workshop_contracts import WorkshopReadinessBlocker
    c, _ = make()
    result = c.get_readiness(**ARGS)
    blocker = WorkshopReadinessBlocker(dependencyType='registry', dependencyId='bundle', state='blocked', reasonCode='REGISTRY_REVOKED', recoverable=False, requiredAction='Current registration required')
    c._installed = SimpleNamespace(get_readiness=lambda **kw: result.model_copy(update={'item':result.item.model_copy(update={'blockers':[*result.item.blockers,blocker]})}))
    with pytest.raises(AssetNotFoundError): c.get_readiness(**ARGS)
