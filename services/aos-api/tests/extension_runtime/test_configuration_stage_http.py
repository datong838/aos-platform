from contextlib import contextmanager
from uuid import uuid4
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import psycopg
import pytest

from aos_api.auth import Principal, require_principal
from aos_api.routers.bundle_runtime_installations import router
from aos_api.routers.runtime_configuration_staging import get_stage_service
from aos_api.extension_runtime.configuration_stage_connection import CREDENTIAL_FILE
from aos_api.extension_runtime.configuration_stage_http_service import ConfigurationStageHttpService
from aos_api.extension_runtime.configuration_stage_contracts import ConfigurationStageRequest
from aos_api.tenant_scope import TenantScope
from test_configuration_stage_contracts import request

URL='/v1/bundle-runtime-installations/configuration-requests'


class Service:
    def __init__(self,error=None): self.calls=[];self.error=error
    def enqueue(self,**kwargs):
        self.calls.append(kwargs)
        if self.error: raise self.error
        return dict(requestId=str(uuid4()),state='requested')
    get=enqueue
    find=enqueue


def client(service=None,role='admin'):
    app=FastAPI();app.include_router(router)
    if role is not None:
        app.dependency_overrides[require_principal]=lambda:Principal(subject='actor',org_id='org-org',project_id='dev-project',roles=[role],markings=['public'])
    if service is not None: app.dependency_overrides[get_stage_service]=lambda:service
    return TestClient(app)


def test_http_uses_only_current_principal_and_exact_request():
    service=Service();browser=client(service)
    response=browser.post(URL+'?subject=other&orgId=dev-org',json=request(),headers={'Idempotency-Key':'one'})
    assert response.status_code==202 and response.headers['cache-control']=='no-store'
    assert service.calls[0]['scope'].key==('org-org','dev-project') and service.calls[0]['subject']=='actor'
    assert 'roles' not in service.calls[0] and 'markings' not in service.calls[0]
    response=browser.get(URL+'/'+str(uuid4()))
    assert response.status_code==200 and response.headers['cache-control']=='no-store'


@pytest.mark.parametrize('case',('anonymous','viewer','extra','key','action'))
def test_invalid_request_does_not_reach_transport(case):
    service=Service();body=request();headers={'Idempotency-Key':'one'}
    if case=='extra': body['subject']='other'
    if case=='key': headers={}
    if case=='action': body['action']='enable'
    response=client(service,role=None if case=='anonymous' else 'viewer' if case=='viewer' else 'admin').post(URL,json=body,headers=headers)
    assert response.status_code in (400,401,403) and response.headers['cache-control']=='no-store'
    assert not service.calls


@pytest.mark.parametrize('error,status',((psycopg.errors.InsufficientPrivilege('private-sentinel'),403),
    (psycopg.errors.CheckViolation('private-sentinel'),409),(LookupError('private-sentinel'),404),
    (RuntimeError('private-sentinel'),503),(psycopg.OperationalError('private-sentinel'),503)))
def test_errors_are_fixed_and_never_cache_or_expose_internal_details(error,status):
    response=client(Service(error)).post(URL,json=request(),headers={'Idempotency-Key':'one'})
    assert response.status_code==status and response.headers['cache-control']=='no-store'
    assert 'private-sentinel' not in response.text


def test_missing_identity_does_not_fall_back(monkeypatch):
    monkeypatch.delenv(CREDENTIAL_FILE,raising=False)
    response=client().post(URL,json=request(),headers={'Idempotency-Key':'one'})
    assert response.status_code==503 and response.headers['cache-control']=='no-store'


def test_success_is_not_returned_when_transaction_commit_is_unknown():
    calls=[]
    @contextmanager
    def connection(**kwargs):
        class Conn:
            def execute(self,*args):calls.append(args);return self
            def fetchone(self):return (dict(requestId=str(uuid4()),requestHash='sha256:'+'a'*64,
                state='requested',revision=1,deadline='2026-09-14T00:00:00+00:00'),)
        yield Conn()
        raise RuntimeError('simulated commit outcome unknown')
    service=ConfigurationStageHttpService(connect=connection)
    with pytest.raises(RuntimeError,match='commit outcome unknown'):
        service.enqueue(scope=TenantScope('org-org','dev-project'),subject='actor',idempotency_key='same',
                        request=ConfigurationStageRequest.model_validate_json(json.dumps(request())))
    assert len(calls)==1


def test_lookup_static_route_uses_header_and_never_calls_submit():
    class ReadService:
        def __init__(self): self.calls=[]
        def enqueue(self, **kwargs): raise AssertionError('lookup must not submit')
        def get(self, **kwargs): raise AssertionError('lookup must not parse as UUID')
        def find(self, **kwargs): self.calls.append(kwargs); return dict(state='requested')
    service=ReadService()
    response=client(service).get(URL+'/lookup?subject=other',headers={'Idempotency-Key':'lost-key'})
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert service.calls[0]['subject']=='actor' and service.calls[0]['idempotency_key']=='lost-key'
    assert service.calls[0]['scope'].key==('org-org','dev-project')
