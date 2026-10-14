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
    '/views/customer/contributions', '/views/creator-growth/workflow/drafts',
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
        '/v1/ecommerce-workshop/source-readiness',
        '/v1/ecommerce-workshop/views/operations/cases',
        '/v1/ecommerce-workshop/commands/operations/readiness',
        '/v1/ecommerce-workshop/views/task-cockpit/feedback',
        '/v1/ecommerce-workshop/views/task-cockpit/dispatch-scenario',
        '/v1/ecommerce-workshop/views/task-cockpit/batch-scenario',
        '/v1/ecommerce-workshop/views/media-studio/full-production-scenario',
        '/v1/ecommerce-workshop/views/media-studio/workflow/drafts',
        '/v1/ecommerce-workshop/views/analyst/learning-scenario',
        '/v1/ecommerce-workshop/views/content-campaign/real-inputs',
        '/v1/ecommerce-workshop/views/creator-growth/contributions',
        '/v1/ecommerce-workshop/views/creator-growth/lifecycle',
    }


def test_unknown_query_rejected_before_catalog_call():
    client, legacy, reader = client_with_catalogs()
    assert client.get('/v1/ecommerce-workshop/views/operations?orgId=dev-org').status_code == 400
    assert not legacy.calls and not reader.calls


class ReadReached(RuntimeError):
    pass


def test_creator_contribution_read_denied_before_service_access():
    client, legacy, reader = client_with_catalogs()
    class Service:
        def contribution_view(self, scope):
            pytest.fail('denied read must not access creator preparation')
    client.app.dependency_overrides[routes.get_ecommerce_workshop_creator_prepare] = lambda: Service()
    response = client.get('/v1/ecommerce-workshop/views/creator-growth/contributions')
    assert response.status_code == 404
    assert not legacy.calls
    assert reader.calls == [dict(module_id='ecommerce.creator-growth',
        org_id='org-org', project_id='dev-project', roles=['admin'], markings=[])]


def test_admitted_creator_contribution_receives_authenticated_scope():
    client, legacy, reader = client_with_catalogs()
    def admit(**scope):
        reader.calls.append(scope)
    reader.get_readiness = admit
    class Service:
        def contribution_view(self, scope):
            assert scope.key == ('org-org', 'dev-project')
            raise ReadReached('creator-contribution')
    client.app.dependency_overrides[routes.get_ecommerce_workshop_creator_prepare] = lambda: Service()
    with pytest.raises(ReadReached, match='creator-contribution'):
        client.get('/v1/ecommerce-workshop/views/creator-growth/contributions')
    assert not legacy.calls and len(reader.calls) == 1


def test_creator_contribution_query_scope_override_is_rejected():
    client, legacy, reader = client_with_catalogs()
    response = client.get('/v1/ecommerce-workshop/views/creator-growth/contributions?projectId=other')
    assert response.status_code == 400
    assert not legacy.calls and not reader.calls


def test_real_inputs_read_denied_before_business_data_access():
    client, legacy, reader = client_with_catalogs()
    def forbidden_inputs():
        class Inputs:
            def read(self, **scope):
                pytest.fail('denied installed read must not read business inputs')
        return Inputs()
    client.app.dependency_overrides[routes.get_ecommerce_workshop_content_campaign_inputs] = forbidden_inputs
    response = client.get('/v1/ecommerce-workshop/views/content-campaign/real-inputs')
    assert response.status_code == 404
    assert not legacy.calls
    assert reader.calls == [dict(module_id='ecommerce.content-campaign',
        org_id='org-org', project_id='dev-project', roles=['admin'], markings=[])]


def test_admitted_real_inputs_receives_only_authenticated_tenant():
    client, legacy, reader = client_with_catalogs()
    def admit(**scope):
        reader.calls.append(scope)
    reader.get_readiness = admit
    class Inputs:
        def read(self, **scope):
            assert scope == dict(org_id='org-org', project_id='dev-project')
            raise ReadReached('real-inputs')
    client.app.dependency_overrides[routes.get_ecommerce_workshop_content_campaign_inputs] = lambda: Inputs()
    with pytest.raises(ReadReached, match='real-inputs'):
        client.get('/v1/ecommerce-workshop/views/content-campaign/real-inputs')
    assert not legacy.calls
    assert len(reader.calls) == 1


def test_real_inputs_query_cannot_override_authenticated_scope():
    client, legacy, reader = client_with_catalogs()
    response = client.get('/v1/ecommerce-workshop/views/content-campaign/real-inputs?orgId=dev-org')
    assert response.status_code == 400
    assert not legacy.calls and not reader.calls


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


LIFECYCLE_PATH = '/v1/ecommerce-workshop/views/creator-growth/lifecycle'


def lifecycle_admission(*, readonly=True):
    from tests.test_ecommerce_workshop_read_catalog import make, ARGS
    catalog, _ = make()
    result = catalog.get_readiness(**{**ARGS, 'module_id': 'ecommerce.creator-growth'})
    if not readonly:
        result = result.model_copy(update={'item': result.item.model_copy(update={
            'blockers': [b for b in result.item.blockers if b.reason_code != 'INSTALLED_ASSET_READONLY'],
        })})
    return result


def lifecycle_probes(client, *, failure=None):
    calls = []
    class Legacy:
        def view(self, scope):
            calls.append(('legacy', scope.key))
            raise ReadReached('legacy-lifecycle')
    class Readonly:
        def read(self, scope):
            calls.append(('readonly', scope.key))
            if failure:
                from aos_api.ecommerce_workshop_creator_lifecycle_readonly import CreatorLifecycleReadonlyError
                raise CreatorLifecycleReadonlyError(failure)
            raise ReadReached('readonly-lifecycle')
    client.app.dependency_overrides[routes.get_ecommerce_workshop_creator_lifecycle] = lambda: Legacy()
    client.app.dependency_overrides[routes.get_creator_lifecycle_readonly] = lambda: Readonly()
    return calls


@pytest.mark.parametrize('readonly', [True, False])
def test_lifecycle_admission_selects_only_correct_reader(readonly):
    client, legacy, reader = client_with_catalogs()
    calls = lifecycle_probes(client)
    def admit(**scope):
        reader.calls.append(scope)
        return lifecycle_admission(readonly=readonly)
    reader.get_readiness = admit
    kind = 'readonly' if readonly else 'legacy'
    with pytest.raises(ReadReached, match=kind + '-lifecycle'):
        client.get(LIFECYCLE_PATH)
    assert calls == [(kind, ('org-org', 'dev-project'))]
    assert not legacy.calls
    assert reader.calls == [dict(module_id='ecommerce.creator-growth', org_id='org-org',
        project_id='dev-project', roles=['admin'], markings=[])]


def test_lifecycle_catalog_denial_precedes_both_readers():
    client, legacy, reader = client_with_catalogs()
    calls = lifecycle_probes(client)
    response = client.get(LIFECYCLE_PATH)
    assert response.status_code == 404
    assert calls == [] and not legacy.calls and len(reader.calls) == 1


@pytest.mark.parametrize('query', ['orgId=dev-org', 'projectId=other', 'limit=1', 'mode=legacy'])
def test_lifecycle_query_cannot_select_scope_reader_or_limit(query):
    client, legacy, reader = client_with_catalogs()
    calls = lifecycle_probes(client)
    response = client.get(LIFECYCLE_PATH + '?' + query)
    assert response.status_code == 400
    assert calls == [] and not legacy.calls and not reader.calls


@pytest.mark.parametrize('admission', [None, object()])
def test_unknown_lifecycle_admission_is_unavailable_not_empty(admission):
    client, legacy, reader = client_with_catalogs()
    calls = lifecycle_probes(client)
    reader.get_readiness = lambda **scope: admission
    response = client.get(LIFECYCLE_PATH)
    assert response.status_code == 503
    assert 'CREATOR_LIFECYCLE_READ_ADMISSION_UNAVAILABLE' in response.text
    assert 'latestStart' not in response.text
    assert calls == [] and not legacy.calls


@pytest.mark.parametrize('code', ['CREATOR_LIFECYCLE_READ_UNAVAILABLE',
    'CREATOR_LIFECYCLE_READ_AUTHORITY_DRIFT', 'CREATOR_LIFECYCLE_READ_LIMIT_EXCEEDED'])
def test_lifecycle_bounded_failure_stays_explicit_503(code):
    client, legacy, reader = client_with_catalogs()
    calls = lifecycle_probes(client, failure=code)
    reader.get_readiness = lambda **scope: lifecycle_admission()
    response = client.get(LIFECYCLE_PATH)
    assert response.status_code == 503 and code in response.text
    assert 'latestStart' not in response.text
    assert calls == [('readonly', ('org-org', 'dev-project'))] and not legacy.calls


def test_lifecycle_readonly_serializes_genuine_empty_without_commands():
    from datetime import datetime, timezone
    from aos_api.ecommerce_workshop_creator_lifecycle import CreatorLifecycleView, _ledger
    client, legacy, reader = client_with_catalogs()
    reader.get_readiness = lambda **scope: lifecycle_admission()
    class Readonly:
        def read(self, scope):
            return CreatorLifecycleView(
                tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
                evaluatedAt=datetime(2026, 10, 14, tzinfo=timezone.utc),
                latestStart=None, ledger=_ledger([], 0), contracts=[], deliveries=[],
                relationships=[], blockers=['CREATOR_BATCH_START_NOT_AVAILABLE'],
                allowedCommands=[], externalEffectsAllowed=False,
            )
    class Legacy:
        def view(self, scope):
            pytest.fail('installed readonly must never invoke legacy view')
    client.app.dependency_overrides[routes.get_creator_lifecycle_readonly] = lambda: Readonly()
    client.app.dependency_overrides[routes.get_ecommerce_workshop_creator_lifecycle] = lambda: Legacy()
    response = client.get(LIFECYCLE_PATH)
    assert response.status_code == 200
    data = response.json()
    assert data['tenant'] == dict(orgId='org-org', projectId='dev-project')
    assert data['latestStart'] is None and data['contracts'] == []
    assert data['allowedCommands'] == [] and data['externalEffectsAllowed'] is False
    assert not legacy.calls
