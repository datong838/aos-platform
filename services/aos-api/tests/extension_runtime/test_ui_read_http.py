from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from test_runtime_workshop_http import app_for, Catalog
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.routers.runtime_workshop import get_ui_read_service


def body():
    return dict(schemaVersion='aos.runtime-ui-read-request/v1', operationId='analyst_workspace_view_v1',
        moduleId='ecommerce.analyst', target=dict(installationId=str(uuid4()), installationRevision=1,
        generation=str(uuid4()), executionEpoch=1, bindingRevision=1,
        route='/workshop/analyst', resourceHash='sha256:' + 'a' * 64), caseLimit=20, runLimit=5)


class Service:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def enqueue(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {'state': 'requested', 'requestId': str(uuid4())}

    get = enqueue


def client(service, authenticated=True):
    app = app_for(Catalog(), authenticated=authenticated)
    app.dependency_overrides[get_ui_read_service] = lambda: service
    return TestClient(app)


def test_submit_and_query_use_only_current_principal_and_no_cache():
    service = Service()
    response = client(service).post('/v1/runtime-workshop/reads?orgId=dev-org&subject=owner',
                                   json=body(), headers={'Idempotency-Key': 'page-1'})
    assert response.status_code == 202 and response.headers['cache-control'] == 'no-store'
    call = service.calls[0]
    assert call['scope'].key == ('org-org', 'dev-project')
    assert call['subject'] == 'reader' and call['markings'] == ('public',)
    assert call['idempotency_key'] == 'page-1'
    assert 'roles' not in call
    request_id = str(uuid4())
    response = client(service).get('/v1/runtime-workshop/reads/' + request_id)
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert str(service.calls[1]['request_id']) == request_id


@pytest.mark.parametrize('defect', ['operation', 'extra', 'missing-key', 'anonymous', 'limit'])
def test_invalid_or_anonymous_request_does_not_call_service(defect):
    service = Service()
    request = body()
    headers = {'Idempotency-Key': 'page-1'}
    if defect == 'operation': request['operationId'] = 'publish'
    if defect == 'extra': request['sql'] = 'SELECT secret'
    if defect == 'limit': request['caseLimit'] = 500
    if defect == 'missing-key': headers = {}
    response = client(service, authenticated=defect != 'anonymous').post(
        '/v1/runtime-workshop/reads', json=request, headers=headers)
    assert response.status_code in (400, 401, 403, 422)
    assert service.calls == []


@pytest.mark.parametrize('error,status', [(RuntimeConflict('private-sentinel'),409),
    (LookupError('private-sentinel'),404), (PermissionError('private-sentinel'),403),
    (RuntimeError('private-sentinel'),503)])
def test_read_errors_are_safe_and_not_cached(error, status):
    response = client(Service(error)).get('/v1/runtime-workshop/reads/' + str(uuid4()))
    assert response.status_code == status
    assert 'private-sentinel' not in response.text
    assert response.headers['cache-control'] == 'no-store'


def test_unconfigured_read_is_unavailable(monkeypatch):
    monkeypatch.delenv('AOS_RUNTIME_UI_READ_CREDENTIAL_FILE', raising=False)
    response = TestClient(app_for(Catalog())).get('/v1/runtime-workshop/reads/' + str(uuid4()))
    assert response.status_code == 503
