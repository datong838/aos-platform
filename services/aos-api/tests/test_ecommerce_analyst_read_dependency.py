"""Analyst learning read admission never grants knowledge governance."""
import pytest
from aos_api.routers import ecommerce_workshop as routes
from aos_api.tenant_scope import TenantScope
from test_ecommerce_workshop_read_http import client_with_catalogs, ReadReached

PATH = '/v1/ecommerce-workshop/views/analyst/learning-scenario'


def test_learning_get_uses_selected_read_admission():
    client, legacy, reader = client_with_catalogs()
    assert client.get(PATH).status_code == 404
    assert not legacy.calls
    assert reader.calls == [dict(module_id='ecommerce.analyst', org_id='org-org', project_id='dev-project', roles=['admin'], markings=[])]


def test_default_learning_keeps_missing_review_and_false_commands():
    client, legacy, reader = client_with_catalogs()
    reader.get_readiness = lambda **scope: reader.calls.append(scope)
    response = client.get(PATH)
    assert response.status_code == 200
    data = response.json()
    assert data['blockers'][0]['code'] == 'EFFECT_REVIEW_EXACT_ROOT_REQUIRED'
    assert data['commands'] and all(value is False for value in data['commands'].values())
    assert all(stage['status'] == 'blocked' for stage in data['stages'])
    assert not legacy.calls


def test_learning_reader_receives_original_tenant_and_aware_cutoff():
    client, legacy, reader = client_with_catalogs()
    reader.get_readiness = lambda **scope: reader.calls.append(scope)
    class Probe:
        def read(self, *, scope, cutoff):
            assert scope == TenantScope('org-org', 'dev-project')
            assert cutoff.utcoffset() is not None
            raise ReadReached('learning-only')
    client.app.dependency_overrides[routes.get_ecommerce_workshop_learning_scenario] = lambda: Probe()
    with pytest.raises(ReadReached, match='learning-only'):
        client.get(PATH)
    assert not legacy.calls


def test_unknown_query_cannot_override_learning_tenant():
    client, legacy, reader = client_with_catalogs()
    assert client.get(PATH + '?orgId=dev-org').status_code == 400
    assert not legacy.calls and not reader.calls
