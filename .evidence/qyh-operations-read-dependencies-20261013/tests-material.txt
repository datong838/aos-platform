"""Only audited read dependencies recover; command execution stays unavailable."""
import pytest
from aos_api.routers import ecommerce_workshop as routes
from test_ecommerce_workshop_read_http import client_with_catalogs, ReadReached

PATHS = ['/views/operations/cases', '/commands/operations/readiness']


@pytest.mark.parametrize('path', PATHS)
def test_missing_selected_read_admission_does_not_fall_back_to_legacy(path):
    client, legacy, reader = client_with_catalogs()
    assert client.get('/v1/ecommerce-workshop' + path).status_code == 404
    assert not legacy.calls
    assert reader.calls == [dict(module_id='ecommerce.operations',org_id='org-org',project_id='dev-project',roles=['admin'],markings=[])]


def admit(reader):
    def get_readiness(**scope):
        reader.calls.append(scope)
    reader.get_readiness = get_readiness


def test_readiness_returns_original_six_blocked_commands():
    client, legacy, reader = client_with_catalogs()
    admit(reader)
    response = client.get('/v1/ecommerce-workshop/commands/operations/readiness')
    assert response.status_code == 200
    data = response.json()
    assert data['tenant'] == dict(orgId='org-org',projectId='dev-project')
    assert len(data['commands']) == 6
    assert all(c['status'] == 'blocked' and c['blockers'] for c in data['commands'])
    assert not legacy.calls and reader.calls
    assert all('EXACT_ACTION_CHAIN_REQUIRED' in {b['code'] for b in c['blockers']} for c in data['commands'] if c['commandId'] != 'refund')
    refund = next(c for c in data['commands'] if c['commandId'] == 'refund')
    assert refund['blockers'][0]['code'] == 'EXTERNAL_ACTION_GATE_NOT_BOUND'


def test_case_workspace_receives_original_authenticated_tenant():
    client, legacy, reader = client_with_catalogs()
    admit(reader)
    class Probe:
        def read(self, **scope):
            assert scope == dict(org_id='org-org',project_id='dev-project')
            raise ReadReached('case-workspace')
    client.app.dependency_overrides[routes.get_ecommerce_operation_case_workspace] = lambda: Probe()
    with pytest.raises(ReadReached, match='case-workspace'):
        client.get('/v1/ecommerce-workshop/views/operations/cases')
    assert not legacy.calls and reader.calls


@pytest.mark.parametrize('path', PATHS)
def test_unknown_query_cannot_change_tenant_or_reach_catalog(path):
    client, legacy, reader = client_with_catalogs()
    assert client.get('/v1/ecommerce-workshop' + path + '?orgId=dev-org').status_code == 400
    assert not legacy.calls and not reader.calls
