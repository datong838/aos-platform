"""Audited cockpit reads retain unavailable sources and execution gates."""
import pytest

from aos_api.ecommerce_workshop_feedback_read_model import FeedbackReadUnavailable
from aos_api.routers import ecommerce_workshop as routes
from aos_api.tenant_scope import TenantScope
from test_ecommerce_workshop_read_http import client_with_catalogs

PATHS = ['/views/task-cockpit/' + name for name in
         ('feedback', 'dispatch-scenario', 'batch-scenario')]


def admit(reader):
    def get_readiness(**scope):
        reader.calls.append(scope)
    reader.get_readiness = get_readiness


@pytest.mark.parametrize('path', PATHS)
def test_cockpit_read_uses_selected_admission(path):
    client, legacy, reader = client_with_catalogs()
    assert client.get('/v1/ecommerce-workshop' + path).status_code == 404
    assert not legacy.calls
    assert reader.calls == [dict(module_id='ecommerce.task-cockpit',
        org_id='org-org', project_id='dev-project', roles=['admin'], markings=[])]


@pytest.mark.parametrize('name,code', [
    ('dispatch', 'TASK_GRAPH_EXACT_ROOT_REQUIRED'),
    ('batch', 'BATCH_EXACT_ROOTS_REQUIRED'),
])
def test_default_scenario_returns_missing_roots_and_no_execution(name, code):
    client, legacy, reader = client_with_catalogs()
    admit(reader)
    response = client.get('/v1/ecommerce-workshop/views/task-cockpit/' + name + '-scenario')
    assert response.status_code == 200
    data = response.json()
    assert data['blockers'][0]['code'] == code
    assert data['commands'] and all(value is False for value in data['commands'].values())
    assert all(stage['status'] == 'blocked' for stage in data['stages'])
    assert not legacy.calls and reader.calls


@pytest.mark.parametrize('limit', [1, 20])
def test_feedback_receives_authenticated_scope_and_keeps_source_unavailable(limit):
    client, legacy, reader = client_with_catalogs()
    admit(reader)
    class Unavailable:
        def read(self, scope, **kwargs):
            assert scope == TenantScope('org-org', 'dev-project')
            assert kwargs == {'limit': limit}
            raise FeedbackReadUnavailable('source unavailable')
    client.app.dependency_overrides[routes.get_ecommerce_workshop_feedback_read_model] = lambda: Unavailable()
    response = client.get(f'/v1/ecommerce-workshop/views/task-cockpit/feedback?limit={limit}')
    assert response.status_code == 503
    assert 'TASK_COCKPIT_FEEDBACK_UNAVAILABLE' in response.text
    assert not legacy.calls and reader.calls


@pytest.mark.parametrize('path', PATHS)
def test_cockpit_unknown_query_rejected_before_admission(path):
    client, legacy, reader = client_with_catalogs()
    assert client.get('/v1/ecommerce-workshop' + path + '?orgId=dev-org').status_code == 400
    assert not reader.calls and not legacy.calls


@pytest.mark.parametrize('limit', [0, 21])
def test_feedback_limit_rejected_before_reader(limit):
    client, legacy, reader = client_with_catalogs()
    assert client.get(f'/v1/ecommerce-workshop/views/task-cockpit/feedback?limit={limit}').status_code == 400
    assert not reader.calls and not legacy.calls
