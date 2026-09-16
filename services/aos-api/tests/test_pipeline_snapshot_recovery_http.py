"""HTTP contracts use signed principal; named service is not real business proof."""
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as NS
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from aos_api.auth import Principal,require_principal
from aos_api.errors import register_exception_handlers
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.routers.pipeline_controls import router


@pytest.fixture
def api():
    calls=[];modes=[]
    def invoke(**kw):
        calls.append(kw)
        if getattr(service,'error',None):raise service.error
        return {'status':'approval_recorded','executionStarted':False}
    service=NS(renew_saved_group=invoke,read_recovery_context=invoke,read_recovery_receipt=invoke)
    def build(scope,*,source_controls):modes.append((scope.key,source_controls));return service
    app=FastAPI();register_exception_handlers(app);app.include_router(router)
    app.state.extension_runtime_control_plane=NS(pipeline_control_factory=NS(build_snapshot_schedule=build))
    app.dependency_overrides[require_principal]=lambda:Principal(subject='signed-user',org_id='org-org',project_id='dev-project',roles=['admin'],markings=[])
    group=str(uuid4());now=datetime.now(timezone.utc)
    body=dict(expectedDefinitionRef=dict(resourceType='SnapshotScheduleDefinitionRevision',resourceId='snapshot-schedule-'+str(uuid4()),revision=2,contentHash='sha256:'+'a'*64),
        expectedRecoveryRef=None,inputManifestHash='sha256:'+'b'*64,notBefore=now.isoformat(),expiresAt=(now+timedelta(hours=1)).isoformat())
    return TestClient(app),calls,modes,service,group,body


def test_signed_identity_and_original_key_are_used(api):
    client,calls,modes,_,group,body=api
    response=client.post('/v1/pipelines/snapshot-recoveries/'+group+'/renew',json=body,headers={'Idempotency-Key':'original-key'})
    assert response.status_code==200,response.text
    assert calls[0]['actor']=='signed-user' and calls[0]['group_id']==group and calls[0]['idempotency_key']=='original-key'
    assert modes==[(('org-org','dev-project'),True)]
    assert response.json()['executionStarted'] is False


@pytest.mark.parametrize('fault',['actor','executor','scope','source','bad-group','bad-ref','bad-recovery','missing-key','naive','long-window','bad-hash'])
def test_invalid_request_never_constructs_service(api,fault):
    client,calls,modes,_,group,body=api;headers={'Idempotency-Key':'original-key'}
    if fault in {'actor','executor','scope','source'}:body[fault]='secret-sentinel'
    elif fault=='bad-group':group='not-uuid'
    elif fault=='bad-ref':body['expectedDefinitionRef']['resourceType']='Approval'
    elif fault=='bad-recovery':body['expectedRecoveryRef']=dict(body['expectedDefinitionRef'])
    elif fault=='missing-key':headers={}
    elif fault=='naive':body['notBefore']='2026-09-16T00:00:00'
    elif fault=='long-window':body['expiresAt']=(datetime.fromisoformat(body['notBefore'])+timedelta(days=2)).isoformat()
    elif fault=='bad-hash':body['inputManifestHash']='bad'
    response=client.post('/v1/pipelines/snapshot-recoveries/'+group+'/renew',json=body,headers=headers)
    assert response.status_code in {400,422},response.text
    assert 'secret-sentinel' not in response.text and not calls and not modes


@pytest.mark.parametrize('error,status',[(PermissionError('secret-sentinel'),403),(LookupError('secret-sentinel'),404),
    (ValueError('secret-sentinel'),422),(IngressJournalConflict('secret-sentinel'),409),(OSError('secret-sentinel'),503)])
def test_errors_are_safe_and_never_automatically_retried(api,error,status):
    client,calls,_,service,group,body=api;service.error=error
    response=client.post('/v1/pipelines/snapshot-recoveries/'+group+'/renew',json=body,headers={'Idempotency-Key':'original-key'})
    assert response.status_code==status and 'secret-sentinel' not in response.text
    assert len(calls)==1


def test_receipt_read_does_not_build_source_controls(api):
    client,calls,modes,_,group,_=api
    response=client.get('/v1/pipelines/snapshot-recoveries/'+group+'/receipts/original-key')
    assert response.status_code==200,response.text
    assert calls==[dict(group_id=group,actor='signed-user',idempotency_key='original-key')]
    assert modes==[(('org-org','dev-project'),False)]


def test_real_app_routes_recovery_context_to_protected_service(monkeypatch):
    from aos_api.main import app
    group=str(uuid4());calls=[]
    def read(**kw):calls.append(kw);return {'status':'saved_input_verified'}
    monkeypatch.setattr(app.state,'extension_runtime_control_plane',NS(pipeline_control_factory=NS(build_snapshot_schedule=lambda *a,**kw:NS(read_recovery_context=read))),raising=False)
    monkeypatch.setitem(app.dependency_overrides,require_principal,lambda:Principal(subject='route-reader',org_id='org-org',project_id='dev-project',roles=['admin'],markings=[]))
    response=TestClient(app).get('/v1/pipelines/snapshot-recoveries/'+group)
    assert response.status_code==200,response.text
    assert calls==[dict(group_id=group,actor='route-reader')]
