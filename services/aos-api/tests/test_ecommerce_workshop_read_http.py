"""HTTP scope fence: only explicitly audited GETs use installed read admission."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop as routes

ROOTS = {
    'task-cockpit', 'operations', 'content-campaign', 'creator-growth',
    'media-studio', 'analyst', 'price-governance', 'customer',
}


class RejectingCatalog:
    def __init__(self):
        self.calls = []

    def get_readiness(self, **scope):
        self.calls.append(scope)
        raise AssetNotFoundError('not installed in current scoped catalog')


def client_with_catalogs():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(routes.router)
    legacy, reader = RejectingCatalog(), RejectingCatalog()
    app.dependency_overrides[routes.get_ecommerce_workshop_catalog] = lambda: legacy
    app.dependency_overrides[routes.get_ecommerce_workshop_read_catalog] = lambda: reader
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject='scope-test', org_id='org-org', project_id='dev-project',
        roles=['admin'], markings=[],
    )
    return TestClient(app), legacy, reader


@pytest.mark.parametrize('module', sorted(ROOTS))
def test_root_get_uses_scoped_read_admission_before_business_reader(module):
    client, legacy, reader = client_with_catalogs()
    response = client.get(f'/v1/ecommerce-workshop/views/{module}')
    assert response.status_code == 404
    assert not legacy.calls
    assert len(reader.calls) == 1
    assert reader.calls[0] == dict(module_id=f'ecommerce.{module}',
        org_id='org-org', project_id='dev-project', roles=['admin'], markings=[])


@pytest.mark.parametrize('path', [
    '/views/customer/contributions', '/views/creator-growth/contributions',
    '/modules/ecommerce.operations/readiness',
])
def test_unreviewed_get_still_uses_legacy_admission(path):
    client, legacy, reader = client_with_catalogs()
    response = client.get('/v1/ecommerce-workshop' + path)
    assert response.status_code == 404
    assert legacy.calls
    assert not reader.calls


def test_read_dependency_only_reaches_explicit_audited_get_routes():
    actual = set()
    for route in routes.router.routes:
        uses_read = any(d.call is routes.get_ecommerce_workshop_read_catalog
                        for d in route.dependant.dependencies)
        if uses_read:
            assert route.methods == {'GET'}
            actual.add(route.path)
    assert actual == {f'/v1/ecommerce-workshop/views/{m}' for m in ROOTS} | {
        '/v1/ecommerce-workshop/views/operations/cases',
        '/v1/ecommerce-workshop/commands/operations/readiness',
        '/v1/ecommerce-workshop/views/task-cockpit/feedback',
        '/v1/ecommerce-workshop/views/task-cockpit/dispatch-scenario',
        '/v1/ecommerce-workshop/views/task-cockpit/batch-scenario',
    }


def test_unknown_query_rejected_before_catalog_call():
    client, legacy, reader = client_with_catalogs()
    assert client.get('/v1/ecommerce-workshop/views/operations?orgId=dev-org').status_code == 400
    assert not legacy.calls and not reader.calls


class ReadReached(RuntimeError):
    pass


@pytest.mark.parametrize('module', sorted(ROOTS))
def test_admitted_root_reaches_reader_with_authenticated_tenant(module):
    client, legacy, reader = client_with_catalogs()
    def admit(**scope):
        reader.calls.append(scope)
    reader.get_readiness = admit
    factory = getattr(routes, 'get_ecommerce_workshop_' + module.replace('-', '_'))
    class ProbeReader:
        def read(self, **scope):
            assert scope['org_id'] == 'org-org'
            assert scope['project_id'] == 'dev-project'
            raise ReadReached(module)
        read_core = read
    client.app.dependency_overrides[factory] = lambda: ProbeReader()
    with pytest.raises(ReadReached, match=module):
        client.get('/v1/ecommerce-workshop/views/' + module)
    assert not legacy.calls
    assert len(reader.calls) == 1


def test_legacy_success_does_not_build_installed_configuration(monkeypatch):
    from aos_api import ecommerce_installed_readonly_catalog as installed
    sentinel = object()
    class Legacy:
        def get_readiness(self, **scope):
            return sentinel
    def forbidden():
        pytest.fail('successful legacy must not inspect selected configuration')
    monkeypatch.setattr(installed, 'build_installed_readonly_catalog', forbidden)
    catalog = routes.get_ecommerce_workshop_read_catalog(Legacy())
    assert catalog.get_readiness(module_id='ecommerce.operations') is sentinel


def test_installed_factory_is_deferred_until_legacy_not_found(monkeypatch):
    from aos_api import ecommerce_installed_readonly_catalog as installed
    calls = []
    def selected():
        calls.append('selected')
        raise ValueError('configuration sentinel')
    monkeypatch.setattr(installed, 'build_installed_readonly_catalog', selected)
    catalog = routes.get_ecommerce_workshop_read_catalog(RejectingCatalog())
    assert not calls
    with pytest.raises(ValueError, match='configuration sentinel'):
        catalog.get_readiness(module_id='ecommerce.operations')
    assert calls == ['selected']
