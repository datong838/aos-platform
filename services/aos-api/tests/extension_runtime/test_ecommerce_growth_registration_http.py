from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import errors

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers.bundle_runtime_installations import router
from test_ecommerce_growth_registration_contracts import payload


@pytest.fixture
def harness():
    calls=[]
    service=SimpleNamespace(error=None,replayed=False)
    def register(**kw):
        calls.append(('register',kw))
        if service.error: raise service.error
        return dict(receiptId='fixture-receipt',executable=False,replayed=service.replayed)
    def read(**kw):
        calls.append(('read',kw))
        if service.error: raise service.error
        return dict(receiptId='fixture-receipt',executable=False,historical=True)
    service.register=register;service.read_receipt=read
    app=FastAPI();register_exception_handlers(app);app.include_router(router)
    app.state.extension_runtime_control_plane=SimpleNamespace(first_dispatch_registration_service=service)
    app.dependency_overrides[require_principal]=lambda:Principal(subject='signed-user',org_id='org-org',project_id='dev-project',roles=['admin'],markings=[])
    return SimpleNamespace(client=TestClient(app),app=app,calls=calls,service=service)


def url(installation=None):
    return '/v1/bundle-runtime-installations/'+(installation or payload()['installationRef']['installationId'])+'/ecommerce-growth-registrations'


def headers():
    return {'Idempotency-Key':payload()['idempotencyKey'],'If-Match':'"'+str(payload()['installationRef']['revision'])+'"'}


@pytest.mark.parametrize('replayed',[False,True])
def test_exact_request_principal_and_response(harness,replayed):
    harness.service.replayed=replayed
    response=harness.client.post(url(),json=payload(),headers=headers())
    assert response.status_code==(200 if replayed else 201),response.text
    assert response.json()['executable'] is False
    assert len(harness.calls)==1
    kwargs=harness.calls[0][1]
    assert kwargs['actor']=='signed-user' and kwargs['scope'].key==('org-org','dev-project')


@pytest.mark.parametrize('defect',['path','key','version','actor','scope','connection','missing-key','missing-version','duplicate-key','duplicate-version'])
def test_mismatched_or_injected_request_never_calls(harness,defect):
    body=payload();head=headers();path=url()
    if defect=='path':path=url('99999999-9999-4999-8999-999999999999')
    elif defect=='key':head['Idempotency-Key']='different'
    elif defect=='version':head['If-Match']='"999"'
    elif defect in ('actor','scope','connection'):body[defect]='private-sentinel'
    elif defect=='missing-key':head.pop('Idempotency-Key')
    elif defect=='missing-version':head.pop('If-Match')
    elif defect=='duplicate-key':head=list(head.items())+[('Idempotency-Key','other')]
    else:head=list(head.items())+[('If-Match','"999"')]
    response=harness.client.post(path,json=body,headers=head)
    assert response.status_code in (400,409,412,422,428),response.text
    assert harness.calls==[] and 'private-sentinel' not in response.text


def test_history_passes_installation_and_only_reads(harness):
    response=harness.client.get(url()+'/receipt',headers=headers())
    assert response.status_code==200,response.text
    method,kw=harness.calls[0]
    assert method=='read' and kw['installation_id']==payload()['installationRef']['installationId']
    assert kw['idempotency_key']==payload()['idempotencyKey'] and kw['scope'].key==('org-org','dev-project')
    assert response.json()['historical'] is True


def test_unconfigured_registration_is_unavailable(harness):
    harness.app.state.extension_runtime_control_plane.first_dispatch_registration_service=None
    response=harness.client.post(url(),json=payload(),headers=headers())
    assert response.status_code==503 and not harness.calls


@pytest.mark.parametrize('error,expected',[(PermissionError('private-sentinel'),403),(LookupError('private-sentinel'),404),
    (ValueError('private-sentinel'),409),(RuntimeError('private-sentinel'),503),
    (errors.SerializationFailure('private-sentinel'),409),(errors.InsufficientPrivilege('private-sentinel'),403),
    (errors.InvalidParameterValue('private-sentinel'),422),(errors.OperationalError('private-sentinel'),503)])
def test_errors_are_sanitized_and_never_retried(harness,error,expected):
    harness.service.error=error
    response=harness.client.post(url(),json=payload(),headers=headers())
    assert response.status_code==expected,response.text
    assert 'private-sentinel' not in response.text and len(harness.calls)==1


def test_real_app_exposes_registration_and_receipt_once():
    from aos_api.main import app
    paths=app.openapi()['paths']
    path='/v1/bundle-runtime-installations/{installation_id}/ecommerce-growth-registrations'
    assert paths[path]['post']['operationId']=='create_ecommerce_growth_registration'
    assert paths[path+'/receipt']['get']['operationId']=='get_ecommerce_growth_registration_receipt'
    for operation in ('create_ecommerce_growth_registration','get_ecommerce_growth_registration_receipt'):
        assert sum(item.get('operationId')==operation for methods in paths.values() for item in methods.values() if isinstance(item,dict))==1


def test_malformed_json_does_not_echo_input(harness):
    response=harness.client.post(url(),content='{"private-sentinel":',headers={**headers(),'Content-Type':'application/json'})
    assert response.status_code==422 and 'private-sentinel' not in response.text and not harness.calls
