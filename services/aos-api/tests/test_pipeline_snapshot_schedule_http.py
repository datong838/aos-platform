"""HTTP identity/contract tests; the named service is not business acceptance."""
from types import SimpleNamespace as NS
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from aos_api.auth import Principal,require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers.pipeline_controls import router
from aos_api.routers.pipeline_snapshot_schedules import SnapshotScheduleConfigureRequest


def ref(kind,prefix):
    return dict(resourceType=kind,resourceId=prefix+str(uuid4()),revision=1,contentHash='sha256:'+'a'*64)


@pytest.fixture
def api():
    calls=[]
    def invoke(**kw):
        calls.append(kw)
        if getattr(service,'error',None):raise service.error
        return {'ref':ref('SnapshotScheduleDefinitionRevision','snapshot-schedule-'),'body':{'state':'disabled'}}
    service=NS(configure=invoke,transition=invoke,read=invoke)
    scopes=[]
    def build(scope,*,source_controls):scopes.append(scope);return service
    app=FastAPI();register_exception_handlers(app);app.include_router(router)
    app.state.extension_runtime_control_plane=NS(pipeline_control_factory=NS(build_snapshot_schedule=build))
    app.dependency_overrides[require_principal]=lambda:Principal(subject='signed-user',org_id='org-org',project_id='dev-project',roles=['admin'],markings=[])
    definition=str(uuid4())
    body=dict(cron='0 8 * * *',policyRef=dict(resourceType='SnapshotRelationshipPolicy',resourceId='content/policies/native.json',revision='1.0.0',contentHash='sha256:'+'a'*64),
        members=[dict(scheduleId='schedule-'+str(i),bindingRef=ref('PipelineScheduleControlBinding','schedule-control-')) for i in range(12)],expectedRef=None)
    return TestClient(app),calls,scopes,service,definition,body


def test_configure_uses_principal_and_exact_key(api):
    client,calls,scopes,_,definition,body=api
    result=client.put('/v1/pipelines/snapshot-schedules/'+definition,json=body,headers={'Idempotency-Key':'one'})
    assert result.status_code==200,result.text
    assert calls[0]['actor']=='signed-user' and calls[0]['idempotency_key']=='one'
    assert calls[0]['definition_id']==definition
    assert scopes[0].key==('org-org','dev-project')


@pytest.mark.parametrize('fault',['actor','scope','connection','few','duplicate','bad-ref','bad-cron','bad-id','missing-key'])
def test_invalid_contract_never_constructs_service(api,fault):
    client,calls,scopes,_,definition,body=api
    headers={'Idempotency-Key':'one'}
    if fault in {'actor','scope','connection'}:body[fault]='secret-sentinel'
    elif fault=='few':body['members'].pop()
    elif fault=='duplicate':body['members'][-1]=body['members'][0]
    elif fault=='bad-ref':body['members'][0]['bindingRef']['resourceType']='Approval'
    elif fault=='bad-cron':body['cron']='0-999999999 8 * * *'
    elif fault=='bad-id':definition='not-uuid'
    elif fault=='missing-key':headers={}
    result=client.put('/v1/pipelines/snapshot-schedules/'+definition,json=body,headers=headers)
    assert result.status_code in {400,422},result.text
    assert 'secret-sentinel' not in result.text
    assert not calls and not scopes


@pytest.mark.parametrize('intent',['enable','disable','retire'])
def test_transition_requires_exact_predecessor(api,intent):
    client,calls,_,_,definition,_=api
    previous=ref('SnapshotScheduleDefinitionRevision','snapshot-schedule-');previous['resourceId']='snapshot-schedule-'+definition
    result=client.post('/v1/pipelines/snapshot-schedules/'+definition+'/'+intent,json={'expectedRef':previous},headers={'Idempotency-Key':intent})
    assert result.status_code==200,result.text
    assert calls[0]['intent']==intent and calls[0]['actor']=='signed-user'


@pytest.mark.parametrize('error,status',[(PermissionError('secret-sentinel'),403),(LookupError('secret-sentinel'),404),
    (ValueError('secret-sentinel'),422),(OSError('secret-sentinel'),503)])
def test_errors_are_safe_and_not_retried(api,error,status):
    client,calls,_,service,definition,body=api
    service.error=error
    result=client.put('/v1/pipelines/snapshot-schedules/'+definition,json=body,headers={'Idempotency-Key':'one'})
    assert result.status_code==status and 'secret-sentinel' not in result.text
    assert len(calls)==1


def test_read_does_not_require_new_idempotency_key(api):
    client,calls,_,_,definition,_=api
    result=client.get('/v1/pipelines/snapshot-schedules/'+definition)
    assert result.status_code==200,result.text
    assert calls==[dict(definition_id=definition,actor='signed-user')]
