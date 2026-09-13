import pytest
from fastapi.testclient import TestClient
from test_runtime_installations_api import _app, _control_plane, _ReadyRuntimeConnection, _InstallationReader, INSTALLATION_ID, GENERATION
from aos_api.extension_runtime.runtime_view import RuntimeViewReader


def test_http_route_uses_principal_and_one_exact_route():
    control = _control_plane()
    response = TestClient(_app(control)).get(f'/v1/bundle-runtime-installations/{INSTALLATION_ID}',
        params={'route':'/workshop/analyst','orgId':'dev-org'},headers={'Authorization':'Bearer ignored'})
    assert response.status_code == 200
    call = control.view_reader.installation_calls[0]
    assert call['requested_route'] == '/workshop/analyst'
    assert call['org_id'] == 'org-org'


@pytest.mark.parametrize('query', ['route=', 'route=/workshop/../admin', 'route=/workshop/a&route=/workshop/b', 'route='+'a'*513])
def test_invalid_or_ambiguous_route_is_rejected_before_reader(query):
    control = _control_plane()
    response = TestClient(_app(control)).get(f'/v1/bundle-runtime-installations/{INSTALLATION_ID}?{query}',
        headers={'Authorization':'Bearer ignored'})
    assert response.status_code == 422
    assert control.view_reader.installation_calls == []


@pytest.mark.parametrize('state', ['ready','disabled','fenced'])
def test_route_session_remains_current_ready_only(state):
    class Connection(_ReadyRuntimeConnection):
        def execute(self, query, params):
            result = super().execute(query,params)
            if 'FROM extension_runtime_binding' in query:
                if state == 'disabled': result._row.update(enabled=False,desired_state='disabled')
                if state == 'fenced': result._row['operation_fence']=True
            return result
    calls = []
    def resolve(**kwargs): calls.append(kwargs); return None
    reader = RuntimeViewReader(installation_reader=_InstallationReader(),connect_factory=Connection,ui_session_resolver=resolve)
    view = reader.get_installation(installation_id=INSTALLATION_ID,org_id='org-org',project_id='dev-project',
        roles=['admin'],markings=['public'],requested_route='/workshop/analyst')
    if state == 'ready':
        assert calls[0]['requested_route']=='/workshop/analyst'
        assert calls[0]['generation']==GENERATION and calls[0]['execution_epoch']==2
    else:
        assert calls==[] and view.ui is None
