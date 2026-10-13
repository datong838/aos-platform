"""Media reads preserve missing production roots and source failures."""
import pytest
from aos_api.routers import ecommerce_workshop as routes
from aos_api.tenant_scope import TenantScope
from test_ecommerce_workshop_read_http import client_with_catalogs, ReadReached

PATHS = ['/views/media-studio/full-production-scenario', '/views/media-studio/workflow/drafts']


def admit(reader):
    reader.get_readiness = lambda **scope: reader.calls.append(scope)


@pytest.mark.parametrize('path', PATHS)
def test_media_read_uses_selected_admission(path):
    client, legacy, reader = client_with_catalogs()
    assert client.get('/v1/ecommerce-workshop' + path).status_code == 404
    assert not legacy.calls
    assert reader.calls == [dict(module_id='ecommerce.media-studio', org_id='org-org', project_id='dev-project', roles=['admin'], markings=[])]


def test_full_video_keeps_all_execution_commands_false():
    client, legacy, reader = client_with_catalogs()
    admit(reader)
    response = client.get('/v1/ecommerce-workshop' + PATHS[0])
    assert response.status_code == 200
    data = response.json()
    assert data['blockers'][0]['code'] == 'FULL_VIDEO_EXACT_ROOT_REQUIRED'
    assert len(data['commands']) == 8
    assert all(value is False for value in data['commands'].values())
    assert all(stage['status'] == 'blocked' for stage in data['stages'])
    assert not legacy.calls


def test_draft_reader_receives_original_authenticated_scope():
    client, legacy, reader = client_with_catalogs()
    admit(reader)
    class Probe:
        def list(self, scope):
            assert scope == TenantScope('org-org', 'dev-project')
            raise ReadReached('media-draft-source')
    client.app.dependency_overrides[routes.get_ecommerce_media_internal_workflow] = lambda: Probe()
    with pytest.raises(ReadReached, match='media-draft-source'):
        client.get('/v1/ecommerce-workshop' + PATHS[1])
    assert not legacy.calls


@pytest.mark.parametrize('path', PATHS)
def test_media_unknown_query_cannot_override_tenant(path):
    client, legacy, reader = client_with_catalogs()
    assert client.get('/v1/ecommerce-workshop' + path + '?orgId=dev-org').status_code == 400
    assert not reader.calls and not legacy.calls
