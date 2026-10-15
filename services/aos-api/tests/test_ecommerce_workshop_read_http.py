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
    '/views/customer/contributions', '/views/creator-growth/workflow/drafts/fixture/history',
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
        '/v1/ecommerce-workshop/views/creator-growth/workflow/drafts',
        '/v1/ecommerce-workshop/views/{module}/closure-contributions',
        '/v1/ecommerce-workshop/views/price-governance/contributions',
        '/v1/ecommerce-workshop/views/price-governance/dispositions',
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


WORKFLOW_PATH = '/v1/ecommerce-workshop/views/creator-growth/workflow/drafts'


def workflow_probes(client, *, failure=None):
    calls = []
    class Legacy:
        def list(self, scope):
            calls.append(('legacy', scope.key))
            raise ReadReached('legacy-workflow')
    class Readonly:
        def list(self, scope):
            calls.append(('readonly', scope.key))
            if failure:
                from aos_api.ecommerce_creator_internal_workflow_readonly import CreatorWorkflowReadonlyError
                raise CreatorWorkflowReadonlyError(failure)
            raise ReadReached('readonly-workflow')
    client.app.dependency_overrides[routes.get_ecommerce_creator_internal_workflow] = lambda: Legacy()
    client.app.dependency_overrides[routes.get_creator_workflow_readonly] = lambda: Readonly()
    return calls


@pytest.mark.parametrize('readonly', [True, False])
def test_workflow_list_selects_exact_installed_or_legacy_reader(readonly):
    client, legacy, reader = client_with_catalogs()
    calls = workflow_probes(client)
    def admit(**scope):
        reader.calls.append(scope)
        return lifecycle_admission(readonly=readonly)
    reader.get_readiness = admit
    kind = 'readonly' if readonly else 'legacy'
    with pytest.raises(ReadReached, match=kind + '-workflow'):
        client.get(WORKFLOW_PATH)
    assert calls == [(kind, ('org-org', 'dev-project'))]
    assert not legacy.calls and reader.calls == [dict(module_id='ecommerce.creator-growth',
        org_id='org-org', project_id='dev-project', roles=['admin'], markings=[])]


def test_workflow_list_denied_catalog_precedes_every_reader():
    client, legacy, reader = client_with_catalogs()
    calls = workflow_probes(client)
    assert client.get(WORKFLOW_PATH).status_code == 404
    assert not calls and not legacy.calls and len(reader.calls) == 1


@pytest.mark.parametrize('query', ['orgId=dev-org', 'projectId=other', 'limit=1', 'mode=legacy'])
def test_workflow_list_query_never_selects_scope_limits_or_reader(query):
    client, legacy, reader = client_with_catalogs()
    calls = workflow_probes(client)
    assert client.get(WORKFLOW_PATH + '?' + query).status_code == 400
    assert not calls and not legacy.calls and not reader.calls


@pytest.mark.parametrize('admission', [None, object()])
def test_workflow_list_unknown_admission_is_503_not_empty(admission):
    client, legacy, reader = client_with_catalogs()
    calls = workflow_probes(client)
    reader.get_readiness = lambda **scope: admission
    response = client.get(WORKFLOW_PATH)
    assert response.status_code == 503 and 'CREATOR_WORKFLOW_READ_ADMISSION_UNAVAILABLE' in response.text
    assert 'items' not in response.text and not calls and not legacy.calls


@pytest.mark.parametrize('code', ['CREATOR_WORKFLOW_READ_UNAVAILABLE',
    'CREATOR_WORKFLOW_READ_AUTHORITY_DRIFT', 'CREATOR_WORKFLOW_READ_PRIVACY_UNAVAILABLE',
    'CREATOR_WORKFLOW_READ_CONTENT_UNSUPPORTED', 'CREATOR_WORKFLOW_READ_LIMIT_EXCEEDED'])
def test_workflow_read_failure_is_explicit_and_not_empty_success(code):
    client, legacy, reader = client_with_catalogs()
    calls = workflow_probes(client, failure=code)
    reader.get_readiness = lambda **scope: lifecycle_admission()
    response = client.get(WORKFLOW_PATH)
    assert response.status_code == 503 and code in response.text
    assert 'items' not in response.text and calls == [('readonly', ('org-org', 'dev-project'))]
    assert not legacy.calls


def test_workflow_successful_empty_has_current_authenticated_scope():
    from aos_api.ecommerce_creator_internal_workflow_contracts import CreatorInternalWorkflowListResponse
    client, legacy, reader = client_with_catalogs()
    reader.get_readiness = lambda **scope: lifecycle_admission()
    class Readonly:
        def list(self, scope):
            assert scope.key == ('org-org', 'dev-project')
            return CreatorInternalWorkflowListResponse(tenant=dict(orgId=scope.org_id, projectId=scope.project_id), items=[], count=0)
    class Legacy:
        def list(self, scope):
            pytest.fail('installed readonly cannot invoke legacy workflow list')
    client.app.dependency_overrides[routes.get_creator_workflow_readonly] = lambda: Readonly()
    client.app.dependency_overrides[routes.get_ecommerce_creator_internal_workflow] = lambda: Legacy()
    response = client.get(WORKFLOW_PATH)
    assert response.status_code == 200
    assert response.json() == dict(tenant=dict(orgId='org-org', projectId='dev-project'), items=[], count=0)
    assert not legacy.calls


CLOSURE_PATH = '/v1/ecommerce-workshop/views/creator/closure-contributions'


def closure_probes(client, *, failure=None):
    calls = []
    class Legacy:
        def contribution_view(self, scope, module):
            calls.append(('legacy', scope.key, module.value))
            raise ReadReached('legacy-closure')
    class Readonly:
        def read(self, scope):
            calls.append(('readonly', scope.key, 'creator'))
            if failure:
                from aos_api.ecommerce_three_module_closure_readonly import CreatorClosureReadonlyError
                raise CreatorClosureReadonlyError(failure)
            raise ReadReached('readonly-closure')
    client.app.dependency_overrides[routes.get_ecommerce_workshop_three_module_closure] = lambda: Legacy()
    client.app.dependency_overrides[routes.get_creator_closure_readonly] = lambda: Readonly()
    return calls


@pytest.mark.parametrize('readonly', [True, False])
def test_creator_closure_selects_only_the_admitted_reader(readonly):
    client, legacy, catalog = client_with_catalogs()
    calls = closure_probes(client)
    catalog.get_readiness = lambda **scope: lifecycle_admission(readonly=readonly)
    kind = 'readonly' if readonly else 'legacy'
    with pytest.raises(ReadReached, match=kind + '-closure'):
        client.get(CLOSURE_PATH)
    assert calls == [(kind, ('org-org', 'dev-project'), 'creator')]
    assert not legacy.calls


def test_creator_closure_denied_before_both_readers():
    client, legacy, catalog = client_with_catalogs()
    calls = closure_probes(client)
    assert client.get(CLOSURE_PATH).status_code == 404
    assert not calls and not legacy.calls and len(catalog.calls) == 1


@pytest.mark.parametrize('module', ['price', 'customer'])
def test_other_closure_modules_keep_legacy_catalog(module):
    client, legacy, catalog = client_with_catalogs()
    calls = closure_probes(client)
    catalog.get_readiness = lambda **scope: lifecycle_admission()
    assert client.get('/v1/ecommerce-workshop/views/' + module + '/closure-contributions').status_code == 404
    assert not calls and legacy.calls and not catalog.calls


@pytest.mark.parametrize('query', ['orgId=foreign', 'projectId=foreign', 'limit=1', 'mode=legacy'])
def test_creator_closure_query_cannot_change_scope_or_reader(query):
    client, legacy, catalog = client_with_catalogs()
    calls = closure_probes(client)
    assert client.get(CLOSURE_PATH + '?' + query).status_code == 400
    assert not calls and not legacy.calls and not catalog.calls


@pytest.mark.parametrize('admission', [None, object()])
def test_creator_closure_unknown_admission_is_unavailable(admission):
    client, legacy, catalog = client_with_catalogs()
    calls = closure_probes(client)
    catalog.get_readiness = lambda **scope: admission
    response = client.get(CLOSURE_PATH)
    assert response.status_code == 503 and 'CREATOR_CLOSURE_READ_ADMISSION_UNAVAILABLE' in response.text
    assert not calls and not legacy.calls


@pytest.mark.parametrize('code', ['CREATOR_CLOSURE_READ_AUTHORITY_DRIFT',
    'CREATOR_CLOSURE_READ_PRIVACY_UNAVAILABLE', 'CREATOR_CLOSURE_READ_LIMIT_EXCEEDED',
    'CREATOR_CLOSURE_READ_UNAVAILABLE'])
def test_creator_closure_reader_failure_cannot_be_empty_success(code):
    client, legacy, catalog = client_with_catalogs()
    calls = closure_probes(client, failure=code)
    catalog.get_readiness = lambda **scope: lifecycle_admission()
    response = client.get(CLOSURE_PATH)
    assert response.status_code == 503 and code in response.text
    assert 'latestClosure' not in response.text
    assert calls == [('readonly', ('org-org', 'dev-project'), 'creator')] and not legacy.calls


PRICE_RESEARCH_PATH = '/v1/ecommerce-workshop/views/price-governance/contributions'


def price_admission(readonly=True):
    from tests.test_ecommerce_workshop_read_catalog import make, ARGS
    catalog, _ = make()
    result = catalog.get_readiness(**{**ARGS, 'module_id': 'ecommerce.price-governance'})
    if not readonly:
        result = result.model_copy(update={'item': result.item.model_copy(update={
            'blockers': [b for b in result.item.blockers if b.reason_code != 'INSTALLED_ASSET_READONLY'],
        })})
    return result


def price_research_probes(client, failure=None):
    calls = []
    class Legacy:
        def contribution_view(self, scope):
            calls.append(('legacy', scope.key))
            raise ReadReached('legacy-price-research')
    class Readonly:
        def read(self, scope):
            calls.append(('readonly', scope.key))
            if failure:
                from aos_api.ecommerce_price_research_readonly import PriceResearchReadonlyError
                raise PriceResearchReadonlyError(failure)
            raise ReadReached('readonly-price-research')
    client.app.dependency_overrides[routes.get_ecommerce_workshop_price_research] = lambda: Legacy()
    # getattr permits pre-implementation RED to exercise the old Catalog rejection.
    factory = getattr(routes, 'get_price_research_readonly', Readonly)
    client.app.dependency_overrides[factory] = lambda: Readonly()
    return calls


@pytest.mark.parametrize('readonly', [True, False])
def test_price_research_selects_admitted_reader_only(readonly):
    client, legacy, catalog = client_with_catalogs()
    calls = price_research_probes(client)
    def admit(**scope):
        assert scope == dict(module_id='ecommerce.price-governance', org_id='org-org',
                             project_id='dev-project', roles=['admin'], markings=[])
        return price_admission(readonly)
    catalog.get_readiness = admit
    kind = 'readonly' if readonly else 'legacy'
    with pytest.raises(ReadReached, match=kind + '-price-research'):
        client.get(PRICE_RESEARCH_PATH)
    assert calls == [(kind, ('org-org', 'dev-project'))] and not legacy.calls


def test_price_research_denied_before_business_read():
    client, legacy, catalog = client_with_catalogs()
    calls = price_research_probes(client)
    assert client.get(PRICE_RESEARCH_PATH).status_code == 404
    assert not calls and not legacy.calls and len(catalog.calls) == 1


@pytest.mark.parametrize('admission', [None, object()])
def test_price_research_unknown_admission_is_unavailable(admission):
    client, legacy, catalog = client_with_catalogs()
    calls = price_research_probes(client)
    catalog.get_readiness = lambda **scope: admission
    response = client.get(PRICE_RESEARCH_PATH)
    assert response.status_code == 503 and 'PRICE_RESEARCH_READ_ADMISSION_UNAVAILABLE' in response.text
    assert not calls and not legacy.calls


@pytest.mark.parametrize('code', ['PRICE_RESEARCH_READ_UNAVAILABLE', 'PRICE_RESEARCH_READ_AUTHORITY_DRIFT',
                                 'PRICE_RESEARCH_READ_LIMIT_EXCEEDED', 'PRICE_RESEARCH_READ_PRIVACY_UNAVAILABLE'])
def test_price_research_invalid_snapshot_does_not_become_empty(code):
    client, legacy, catalog = client_with_catalogs()
    calls = price_research_probes(client, code)
    catalog.get_readiness = lambda **scope: price_admission()
    response = client.get(PRICE_RESEARCH_PATH)
    assert response.status_code == 503 and code in response.text
    assert 'latestBatch' not in response.text
    assert calls == [('readonly', ('org-org', 'dev-project'))] and not legacy.calls


@pytest.mark.parametrize('query', ['orgId=foreign', 'projectId=foreign', 'limit=1', 'mode=legacy'])
def test_price_research_query_does_not_change_scope(query):
    client, legacy, catalog = client_with_catalogs()
    calls = price_research_probes(client)
    assert client.get(PRICE_RESEARCH_PATH + '?' + query).status_code == 400
    assert not calls and not legacy.calls and not catalog.calls


@pytest.mark.parametrize('readonly', [True, False])
def test_price_research_full_http_dto_preserves_readonly_and_legacy_semantics(readonly):
    from datetime import UTC, datetime
    from psycopg import IsolationLevel
    from aos_api.ecommerce_price_research_readonly import PriceResearchReadonlyReader
    from aos_api.ecommerce_workshop_price_research import EcommerceWorkshopPriceResearchService
    client, legacy, catalog = client_with_catalogs()
    catalog.get_readiness = lambda **scope: price_admission(readonly)
    calls = []
    cutoff = datetime(2026, 10, 15, tzinfo=UTC)
    class EmptyStore:
        def latest_batch_or_none(self, scope):
            calls.append(('legacy', scope.key))
            return None
    class Result:
        def __init__(self, value): self.value = value
        def fetchone(self): return self.value
    class Connection:
        read_only = True
        autocommit = False
        isolation_level = IsolationLevel.REPEATABLE_READ
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, statement, params=()):
            if 'transaction_timestamp' in statement: return Result({'cutoff': cutoff})
            assert params == ('org-org', 'dev-project')
            assert 'CASE WHEN' in statement and 'LIMIT 1' in statement
            calls.append(('readonly', params))
            return Result(None)
    client.app.dependency_overrides[routes.get_price_research_readonly] = lambda: PriceResearchReadonlyReader(connect_factory=lambda scope: Connection())
    client.app.dependency_overrides[routes.get_ecommerce_workshop_price_research] = lambda: EcommerceWorkshopPriceResearchService(EmptyStore())
    response = client.get(PRICE_RESEARCH_PATH)
    assert response.status_code == 200
    body = response.json()
    assert body['tenant'] == dict(orgId='org-org', projectId='dev-project')
    assert body['latestBatch'] is None and body['blockers'] == ['PRICE_RESEARCH_BATCH_NOT_AVAILABLE']
    assert body['externalEffectsAllowed'] is False
    assert body['allowedCommands'] == ([] if readonly else ['PREPARE_PRICE_RESEARCH_BATCH', 'FREEZE_PRICE_RESEARCH_BATCH'])
    assert calls == [('readonly' if readonly else 'legacy', ('org-org', 'dev-project'))]
    assert not legacy.calls


PRICE_DISPOSITION_PATH = '/v1/ecommerce-workshop/views/price-governance/dispositions'


def disposition_probes(client, failure=None):
    calls = []
    class Legacy:
        def contribution_view(self, scope):
            calls.append(('legacy', scope.key))
            raise ReadReached('legacy-price-disposition')
    class Readonly:
        def read(self, scope):
            calls.append(('readonly', scope.key))
            if failure:
                from aos_api.ecommerce_price_disposition_readonly import PriceDispositionReadonlyError
                raise PriceDispositionReadonlyError(failure)
            raise ReadReached('readonly-price-disposition')
    client.app.dependency_overrides[routes.get_ecommerce_workshop_price_disposition] = lambda: Legacy()
    client.app.dependency_overrides[getattr(routes, 'get_price_disposition_readonly', Readonly)] = lambda: Readonly()
    return calls


@pytest.mark.parametrize('readonly', [True, False])
def test_price_disposition_selects_only_admitted_reader(readonly):
    client, legacy, catalog = client_with_catalogs()
    calls = disposition_probes(client)
    def admit(**scope):
        assert scope == dict(module_id='ecommerce.price-governance', org_id='org-org', project_id='dev-project', roles=['admin'], markings=[])
        return price_admission(readonly)
    catalog.get_readiness = admit
    kind = 'readonly' if readonly else 'legacy'
    with pytest.raises(ReadReached, match=kind + '-price-disposition'): client.get(PRICE_DISPOSITION_PATH)
    assert calls == [(kind, ('org-org', 'dev-project'))] and not legacy.calls


def test_price_disposition_denied_before_business_read():
    client, legacy, catalog = client_with_catalogs(); calls = disposition_probes(client)
    assert client.get(PRICE_DISPOSITION_PATH).status_code == 404
    assert not calls and not legacy.calls and len(catalog.calls) == 1


@pytest.mark.parametrize('admission', [None, object()])
def test_price_disposition_unknown_admission_fails_closed(admission):
    client, legacy, catalog = client_with_catalogs(); calls = disposition_probes(client)
    catalog.get_readiness = lambda **scope: admission
    response = client.get(PRICE_DISPOSITION_PATH)
    assert response.status_code == 503 and 'PRICE_DISPOSITION_READ_ADMISSION_UNAVAILABLE' in response.text
    assert not calls and not legacy.calls


@pytest.mark.parametrize('code', ['PRICE_DISPOSITION_READ_AUTHORITY_UNAVAILABLE', 'PRICE_DISPOSITION_READ_AUTHORITY_DRIFT',
                                 'PRICE_DISPOSITION_READ_LIMIT_EXCEEDED', 'PRICE_DISPOSITION_READ_SENSITIVE_CONTENT'])
def test_price_disposition_failure_does_not_become_empty_success(code):
    client, legacy, catalog = client_with_catalogs(); calls = disposition_probes(client, code)
    catalog.get_readiness = lambda **scope: price_admission()
    response = client.get(PRICE_DISPOSITION_PATH)
    assert response.status_code == 503 and code in response.text and 'caseCount' not in response.text
    assert calls == [('readonly', ('org-org', 'dev-project'))] and not legacy.calls


@pytest.mark.parametrize('query', ['orgId=foreign', 'projectId=foreign', 'limit=1', 'mode=legacy'])
def test_price_disposition_query_cannot_change_scope(query):
    client, legacy, catalog = client_with_catalogs(); calls = disposition_probes(client)
    assert client.get(PRICE_DISPOSITION_PATH + '?' + query).status_code == 400
    assert not calls and not legacy.calls and not catalog.calls


@pytest.mark.parametrize('readonly,nonempty', [(True, True), (True, False), (False, False)])
def test_price_disposition_full_http_serialization(readonly, nonempty):
    import importlib.util
    from pathlib import Path
    from aos_api.ecommerce_workshop_price_disposition import EcommerceWorkshopPriceDispositionService
    path = Path(__file__).parent / 'aip/test_ecommerce_price_disposition_readonly.py'
    spec = importlib.util.spec_from_file_location('disposition_http_fixture', path)
    fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    f, tables = fixture.saved_rows()
    if not nonempty:
        for table in tables: tables[table] = []
    reader, conn, opened = fixture.reader_for(tables, f)
    client, legacy, catalog = client_with_catalogs()
    catalog.get_readiness = lambda **scope: price_admission(readonly)
    class EmptyStore:
        def list_cases(self, _scope): return []
        def list_dispositions(self, _scope): return []
        def list_observations(self, _scope): return []
    client.app.dependency_overrides[routes.get_price_disposition_readonly] = lambda: reader
    client.app.dependency_overrides[routes.get_ecommerce_workshop_price_disposition] = lambda: EcommerceWorkshopPriceDispositionService(EmptyStore(), None)
    response = client.get(PRICE_DISPOSITION_PATH)
    assert response.status_code == 200
    body = response.json()
    assert body['tenant'] == dict(orgId='org-org', projectId='dev-project')
    assert body['caseCount'] == int(nonempty)
    assert sum(body['dispositionCounts'].values()) == (8 if nonempty else 0)
    assert body['externalEffectsAllowed'] is body['repricingEnabled'] is False
    assert body['allowedCommands'] == ([] if readonly else ['COMPILE_PRICE_CASE', 'CREATE_PRICE_DISPOSITION_CONTRACT',
        'PREPARE_PRICE_DISPOSITION', 'FREEZE_PRICE_DISPOSITION', 'RECORD_PRICE_DISPOSITION_OBSERVATION'])
    if nonempty:
        assert body['latestDisposition']['lifecycle'] == 'frozen'
        assert body['latestObservation']['dispositionRef']['resourceId'] != body['latestDisposition']['dispositionId']
    else:
        assert body['latestDisposition'] is body['latestObservation'] is None
    assert len(opened) == int(readonly) and conn.payload_calls == (4 if readonly else 0)
    assert not legacy.calls
