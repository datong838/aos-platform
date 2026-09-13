from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import require_principal, Principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import runtime_workshop


def app_for(catalog=None, authenticated=True):
    app = FastAPI()
    app.include_router(runtime_workshop.router)
    register_exception_handlers(app)
    if catalog is not None:
        app.state.extension_runtime_workshop_catalog = catalog
    if authenticated:
        app.dependency_overrides[require_principal] = lambda: Principal(
            subject='reader', org_id='org-org', project_id='dev-project', roles=['operator'], markings=['public'])
    return app


class Catalog:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def list_modules(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return dict(schemaVersion='aos.runtime-workshop-catalog/v1',
                    tenant=dict(orgId=kwargs['org_id'], projectId=kwargs['project_id']),
                    evaluatedAt=datetime.now(timezone.utc), dataCutoff=None, items=[], count=0)


def test_current_principal_is_only_scope_and_no_cache():
    catalog = Catalog()
    response = TestClient(app_for(catalog)).get('/v1/runtime-workshop/modules?orgId=dev-org&roles=admin')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['tenant']['orgId'] == 'org-org'
    assert catalog.calls == [dict(org_id='org-org', project_id='dev-project', roles=['operator'], markings=['public'])]


@pytest.mark.parametrize('error,status', [(PermissionError('secret'),403),(LookupError('secret'),404),(ValueError('secret'),503)])
def test_catalog_error_fails_closed(error, status):
    response = TestClient(app_for(Catalog(error))).get('/v1/runtime-workshop/modules')
    assert response.status_code == status
    assert 'secret' not in response.text


def test_missing_service_is_not_empty_success():
    assert TestClient(app_for()).get('/v1/runtime-workshop/modules').status_code == 503


def test_anonymous_cannot_call_catalog():
    catalog = Catalog()
    response = TestClient(app_for(catalog, authenticated=False)).get('/v1/runtime-workshop/modules')
    assert response.status_code in (401,403)
    assert catalog.calls == []


def test_control_plane_reader_wins_over_fallback():
    fallback, current = Catalog(ValueError('unused')), Catalog()
    app = app_for(fallback)
    app.state.extension_runtime_control_plane = SimpleNamespace(workshop_catalog=current)
    assert TestClient(app).get('/v1/runtime-workshop/modules').status_code == 200
    assert not fallback.calls and len(current.calls) == 1


def test_catalog_construction_is_lazy(monkeypatch):
    from aos_api.asset_registry import control_wiring
    def forbidden(*args, **kwargs):
        raise AssertionError('must not construct dependencies until read')
    monkeypatch.setattr(control_wiring, 'ManifestLoader', forbidden)
    reader = control_wiring.build_runtime_workshop_catalog_reader(view_reader=object())
    assert reader is not None
