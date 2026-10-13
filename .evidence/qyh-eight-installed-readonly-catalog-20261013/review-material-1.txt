"""Installed signed assets may be viewed without granting runtime readiness."""
from dataclasses import replace
from pathlib import Path
import pytest
from aos_api.asset_registry.errors import RegistryIntegrityCorruptError
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.ecommerce_installed_readonly_catalog import InstalledReadonlyWorkshopCatalog
from tests.asset_registry.test_ecommerce_workshop_catalog import _active, _persisted, _loaded_growth, NOW, INSTALLATION_ID

ROOT = Path(__file__).resolve().parents[4]

class RuntimeCandidates:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []
    def read_runtime_candidate_bundles(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows
    def read_active_bundles(self, **kwargs):
        raise AssertionError('legacy catalog must not be used')

def catalog(rows):
    source = RuntimeCandidates(rows)
    return InstalledReadonlyWorkshopCatalog(source=source,
        loader=ManifestLoader({'catalog': ROOT / 'bundles'}),
        installation_id=INSTALLATION_ID, org_id='org-org', project_id='dev-project',
        clock=lambda: NOW), source

def read(c, **changes):
    args = dict(org_id='org-org', project_id='dev-project', roles=['operator'], markings=['public'])
    args.update(changes)
    return c.list_modules(**args)

def test_signed_installed_modules_are_visible_but_never_executable():
    c,s = catalog([_active(_persisted(_loaded_growth()))])
    response = read(c)
    assert response.count == 7
    assert all(x.readiness.value == 'disabled' for x in response.items)
    assert all(any(b.reason_code == 'INSTALLED_ASSET_READONLY' for b in x.blockers) for x in response.items)
    assert all(str(x.installation_ref.installation_id) == INSTALLATION_ID for x in response.items)
    assert len(s.calls) == 1

@pytest.mark.parametrize('changes',[{'org_id':'dev-org'}, {'project_id':'other'}])
def test_cross_tenant_has_no_source_access(changes):
    c,s = catalog([_active(_persisted(_loaded_growth()))])
    assert read(c,**changes).count == 0
    assert s.calls == []

def test_unselected_installation_is_not_visible():
    row = replace(_active(_persisted(_loaded_growth())), installation_id='33333333-3333-4333-8333-333333333333')
    c,_ = catalog([row])
    assert read(c).count == 0

@pytest.mark.parametrize('changes',[{'roles':[]}, {'markings':[]}])
def test_original_permissions_remain_required(changes):
    c,_ = catalog([_active(_persisted(_loaded_growth()))])
    loaded = _loaded_growth()
    # Isolated permission-filter fixture; real signed source is verified separately.
    from types import SimpleNamespace
    modules = [m.model_copy(update={'permissions': m.permissions.model_copy(update={'roles':['operator'], 'markings':['public']})}) for m in loaded.workshop_modules]
    c._loader = SimpleNamespace(load=lambda ref: loaded.model_copy(update={'workshop_modules': modules}))
    assert read(c,**changes).count == 0

def test_content_drift_is_rejected():
    c,_ = catalog([_active(_persisted(_loaded_growth(),content_hash='sha256:'+'f'*64))])
    with pytest.raises(RegistryIntegrityCorruptError): read(c)

def test_revoked_installation_is_re_read_instead_of_cached():
    c,s = catalog([_active(_persisted(_loaded_growth()))])
    assert read(c).count == 7
    s.rows = []
    assert read(c).count == 0
    assert len(s.calls) == 2


def test_unconfigured_server_catalog_is_empty_without_database(monkeypatch):
    from aos_api.ecommerce_installed_readonly_catalog import build_installed_readonly_catalog
    monkeypatch.delenv('AOS_INSTALLED_READONLY_CATALOG', raising=False)
    assert read(build_installed_readonly_catalog()).count == 0

@pytest.mark.parametrize('config',['{}','null','{"installationId":"bad","orgId":"org-org","projectId":"dev-project"}'])
def test_invalid_server_configuration_fails_closed(monkeypatch, config):
    from aos_api.ecommerce_installed_readonly_catalog import build_installed_readonly_catalog
    monkeypatch.setenv('AOS_INSTALLED_READONLY_CATALOG',config)
    with pytest.raises(RegistryIntegrityCorruptError): build_installed_readonly_catalog()


def test_separate_http_view_does_not_replace_original_business_catalog(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from aos_api.auth import Principal, require_principal
    from aos_api.errors import register_exception_handlers
    from aos_api.routers import ecommerce_workshop
    from aos_api import ecommerce_installed_readonly_catalog as installed
    from tests.test_ecommerce_workshop_api import FakeCatalog
    c,_ = catalog([_active(_persisted(_loaded_growth()))])
    monkeypatch.setattr(installed,'build_installed_readonly_catalog',lambda: c)
    app = FastAPI(); register_exception_handlers(app); app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(subject='reader',org_id='org-org',project_id='dev-project',roles=['operator'],markings=['public'])
    business = FakeCatalog()
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_catalog] = lambda: business
    with TestClient(app) as client:
        response = client.get('/v1/ecommerce-workshop/installed-readonly-modules')
        assert response.status_code == 200
        assert response.json()['count'] == 7
        assert all(x['readiness']=='disabled' for x in response.json()['items'])
        assert client.get('/v1/ecommerce-workshop/installed-readonly-modules?installationId=other').status_code == 400
        original = client.get('/v1/ecommerce-workshop/modules')
        assert original.status_code == 200
        assert original.json()['count'] == 1
