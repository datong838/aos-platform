"""Source reads use selected exact admission only when legacy visibility is zero."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.asset_registry.errors import AssetNotFoundError, RegistryIntegrityCorruptError
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_workshop_source_readiness import EcommerceWorkshopSourceReadiness
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop as routes
from tests.test_ecommerce_workshop_read_catalog import make
from tests.test_ecommerce_workshop_source_readiness import FakeReader, _envelope


def setup(*, count=0, granted=True, org='org-org', project='dev-project', drift=False):
    selected, source = make(granted=granted)
    calls = []

    class Legacy:
        def list_modules(self, **scope):
            calls.append(scope)
            return SimpleNamespace(count=count)

        def get_readiness(self, **scope):
            pytest.fail('zero-list fallback must not accept legacy get_readiness')

    legacy = Legacy()
    selected._legacy = legacy
    canonical = FakeReader(_envelope(status='blocked', org_id='dev-org' if drift else org))
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject='scope-test', org_id=org, project_id=project,
        roles=['operator'], markings=['public'],
    )
    app.dependency_overrides[routes.get_ecommerce_workshop_catalog] = lambda: legacy
    app.dependency_overrides[routes.get_ecommerce_workshop_read_catalog] = lambda: selected
    app.dependency_overrides[routes.get_ecommerce_workshop_source_readiness] = lambda: (
        EcommerceWorkshopSourceReadiness(canonical)
    )
    return TestClient(app), legacy, selected, source, canonical, calls


def test_legacy_nonempty_never_inspects_selected_configuration():
    client, _, selected, source, canonical, calls = setup(count=1)
    def forbidden():
        pytest.fail('nonempty legacy must not construct selected catalog')
    selected._installed_factory = forbidden
    response = client.get('/v1/ecommerce-workshop/source-readiness')
    assert response.status_code == 200
    assert response.json()['status'] == 'blocked'
    assert len(response.json()['sources']) == 12
    assert source.calls == []
    assert canonical.calls == [('org-org', 'dev-project')]
    assert calls == [dict(org_id='org-org', project_id='dev-project',
                          roles=['operator'], markings=['public'])]


def test_zero_legacy_uses_real_selected_grant_and_preserves_canonical_blockers():
    client, _, _, source, canonical, _ = setup()
    response = client.get('/v1/ecommerce-workshop/source-readiness')
    assert response.status_code == 200
    assert response.json() == canonical.envelope.model_dump(mode='json', by_alias=True)
    assert source.calls
    assert canonical.calls == [('org-org', 'dev-project')]


def test_zero_legacy_success_cannot_bypass_missing_selected_grant():
    client, legacy, _, source, canonical, _ = setup(granted=False)
    legacy.get_readiness = lambda **scope: object()
    response = client.get('/v1/ecommerce-workshop/source-readiness')
    assert response.status_code == 404
    assert response.json()['code'] == 'WORKSHOP_NOT_INSTALLED'
    assert source.calls
    assert canonical.calls == []


@pytest.mark.parametrize('changes', [{'org': 'dev-org'}, {'project': 'other'}])
def test_zero_cross_tenant_denied_without_selected_source_access(changes):
    client, _, _, source, canonical, _ = setup(**changes)
    assert client.get('/v1/ecommerce-workshop/source-readiness').status_code == 404
    assert source.calls == [] and canonical.calls == []


@pytest.mark.parametrize('error_at', ['legacy', 'selected'])
def test_integrity_error_stops_without_canonical_read_or_later_admission(error_at):
    client, legacy, selected, source, canonical, _ = setup()
    attempts = []
    def corrupt(**scope):
        attempts.append(scope)
        raise RegistryIntegrityCorruptError()
    if error_at == 'legacy':
        legacy.list_modules = corrupt
    else:
        selected.get_installed_readiness = corrupt
    response = client.get('/v1/ecommerce-workshop/source-readiness')
    assert response.status_code == 500
    assert response.json()['code'] == 'REGISTRY_INTEGRITY_CORRUPT'
    assert len(attempts) == 1
    assert source.calls == [] and canonical.calls == []


def test_first_module_invisible_can_try_later_selected_module_with_same_scope():
    client, _, selected, _, canonical, _ = setup()
    attempts = []
    original = selected.get_installed_readiness
    def read(**scope):
        attempts.append(scope)
        if scope['module_id'] != 'ecommerce.customer':
            raise AssetNotFoundError('module not visible')
        return original(**scope)
    selected.get_installed_readiness = read
    assert client.get('/v1/ecommerce-workshop/source-readiness').status_code == 200
    assert len(attempts) == 8
    assert all({k: v for k, v in x.items() if k != 'module_id'} == dict(
        org_id='org-org', project_id='dev-project', roles=['operator'], markings=['public']
    ) for x in attempts)
    assert canonical.calls == [('org-org', 'dev-project')]


def test_unknown_query_rejected_before_any_admission_or_source_call():
    client, _, _, source, canonical, calls = setup()
    assert client.get('/v1/ecommerce-workshop/source-readiness?orgId=dev-org').status_code == 400
    assert calls == [] and source.calls == [] and canonical.calls == []


def test_selected_admission_does_not_weaken_canonical_tenant_check():
    client, _, _, _, canonical, _ = setup(drift=True)
    response = client.get('/v1/ecommerce-workshop/source-readiness')
    assert response.status_code == 500
    assert response.json()['code'] == 'SOURCE_READINESS_TENANT_MISMATCH'
    assert canonical.calls == [('org-org', 'dev-project')]
