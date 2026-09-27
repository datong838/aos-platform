import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef, PipelineRuntimeControlDraft, PipelineSourceSelectionDraft
from aos_api.routers.pipeline_controls import router
from tests.test_pipeline_runtime_control_contracts import payload


@pytest.fixture
def harness():
    calls=[]
    ref=PipelineExactRef(resource_type='SourceSelectionRevision',resource_id='source-selection-55555555-5555-4555-8555-555555555555',revision=1,content_hash='sha256:'+'a'*64)
    def approve(**kw):
        calls.append(kw)
        if getattr(service,'error',None):raise service.error
        if isinstance(kw["draft"], PipelineRuntimeControlDraft):
            return ref.model_copy(update={"resource_type":"PipelineRuntimeControlRevision", "resource_id":"pipeline-control-55555555-5555-4555-8555-555555555555"})
        return ref
    def read_selection_receipt(**kw):
        calls.append(kw)
        if getattr(service,'error',None):raise service.error
        return ref
    service=SimpleNamespace(approve_selection=approve,approve_control=approve,
        read_selection_receipt=read_selection_receipt)
    scopes=[]
    def build(scope):scopes.append(scope);return service
    app=FastAPI();register_exception_handlers(app);app.include_router(router)
    app.state.extension_runtime_control_plane=SimpleNamespace(pipeline_control_factory=SimpleNamespace(build=build))
    app.dependency_overrides[require_principal]=lambda:Principal(subject='signed-user',org_id='test-org',project_id='test-project',roles=['admin'],markings=[])
    return TestClient(app),app,calls,scopes,service


def body(control=False):
    raw=payload()
    if not control:raw.pop('sourceSelectionRef')
    model=PipelineRuntimeControlDraft if control else PipelineSourceSelectionDraft
    return {'draft':json.loads(model.model_validate(raw).model_dump_json(by_alias=True))}


def post(h,body=None,headers=None,control=False,pipeline='P01-shop-qyh'):
    suffix='runtime-control-approvals' if control else 'source-selection-approvals'
    return h[0].post(f'/v1/pipelines/{pipeline}/{suffix}',json=body,headers={'Idempotency-Key':'first'} if headers is None else headers)


@pytest.mark.parametrize('control',[False,True])
def test_wire_json_uses_principal_and_only_approval_service(harness,control):
    response=post(harness,body(control),control=control)
    assert response.status_code==200,response.text
    assert response.json()['revision']==1
    assert response.json()['resourceType']==('PipelineRuntimeControlRevision' if control else 'SourceSelectionRevision')
    assert len(harness[2])==1
    args=harness[2][0]
    assert args['actor']=='signed-user' and args['idempotency_key']=='first'
    assert args['draft'].not_before.utcoffset().total_seconds()==0
    assert harness[3][0].key==('test-org','test-project')
    assert 'enabled' not in response.json()


@pytest.mark.parametrize('change',['scope','path','actor','connection','numeric','previous_kind','previous_uuid','previous_bool'])
def test_invalid_requests_never_build_or_call_service(harness,change):
    value=body();pipeline='P01-shop-qyh'
    if change=='scope':value['draft']['orgId']='dev-org'
    elif change=='path':pipeline='other'
    elif change in ('actor','connection'):value[change]='private-sentinel'
    elif change=='numeric':value['draft']['rowLimit']=True
    else:
        value['previousRef']={'resourceType':'SourceSelectionRevision','resourceId':'source-selection-55555555-5555-4555-8555-555555555555','revision':1,'contentHash':'sha256:'+'a'*64}
        if change=='previous_kind':value['previousRef']['resourceType']='Approval'
        elif change=='previous_uuid':value['previousRef']['resourceId']='source-selection-invalid'
        else:value['previousRef']['revision']=True
    response=post(harness,value,pipeline=pipeline)
    assert response.status_code in (403,422),response.text
    assert not harness[2] and not harness[3]
    assert 'private-sentinel' not in response.text


@pytest.mark.parametrize('headers',[{},[('Idempotency-Key','a'),('Idempotency-Key','b')],{'Idempotency-Key':' '}])
def test_idempotency_header_exactly_once(harness,headers):
    response=post(harness,body(),headers=headers)
    assert response.status_code==400
    assert not harness[2] and not harness[3]


@pytest.mark.parametrize('error,status',[(PermissionError('private-sentinel'),403),(LookupError('private-sentinel'),404),
    (RuntimeConflict('private-sentinel'),409),(RuntimeRevisionConflict('private-sentinel'),412),
    (ValueError('private-sentinel'),422),(OSError('private-sentinel'),503)])
def test_errors_are_safe_and_no_retry(harness,error,status):
    harness[4].error=error
    response=post(harness,body())
    assert response.status_code==status,response.text
    assert 'private-sentinel' not in response.text
    assert len(harness[2])==1


def test_missing_factory_never_falls_back(harness):
    harness[1].state.extension_runtime_control_plane.pipeline_control_factory=None
    assert post(harness,body()).status_code==503
    assert not harness[2]


def test_exact_predecessor_is_forwarded(harness):
    value=body()
    value['previousRef']={'resourceType':'SourceSelectionRevision','resourceId':'source-selection-55555555-5555-4555-8555-555555555555','revision':2,'contentHash':'sha256:'+'b'*64}
    assert post(harness,value).status_code==200
    assert harness[2][0]['previous_ref'].revision==2


def test_bad_json_and_oversized_input_are_rejected_without_service(harness):
    for raw,status in [(b'{"draft":',422),(b'x'*65537,413)]:
        result=harness[0].post('/v1/pipelines/P01-shop-qyh/source-selection-approvals',content=raw,headers={'Idempotency-Key':'first'})
        assert result.status_code==status
    assert not harness[2] and not harness[3]


def test_real_app_registers_both_approval_routes_once():
    from aos_api.main import app
    paths=app.openapi()['paths']
    for suffix in ('source-selection-approvals','runtime-control-approvals'):
        assert 'post' in paths[f'/v1/pipelines/{{pipeline_id}}/{suffix}']
    assert 'get' in paths['/v1/pipelines/{pipeline_id}/source-selection-approvals/receipt']


def receipt(harness, *, installation='44444444-4444-4444-8444-444444444444',
            generation='33333333-3333-4333-8333-333333333333', key='first'):
    return harness[0].get('/v1/pipelines/P01-shop-qyh/source-selection-approvals/receipt',
        params={'installationId':installation,'generation':generation},
        headers={'Idempotency-Key':key} if key is not None else {})


def test_read_selection_receipt_uses_signed_scope_and_original_key(harness):
    response=receipt(harness)
    assert response.status_code==200,response.text
    assert response.json()['resourceType']=='SourceSelectionRevision'
    assert harness[2]==[dict(installation_id='44444444-4444-4444-8444-444444444444',
        generation='33333333-3333-4333-8333-333333333333',pipeline_id='P01-shop-qyh',
        actor='signed-user',idempotency_key='first')]
    assert harness[3][0].key==('test-org','test-project')


@pytest.mark.parametrize('installation,generation,key,status',[
    ('bad','33333333-3333-4333-8333-333333333333','first',400),
    ('44444444-4444-4444-8444-444444444444','bad','first',400),
    ('44444444-4444-4444-8444-444444444444','33333333-3333-4333-8333-333333333333',None,400),
])
def test_invalid_receipt_query_never_reaches_service(harness,installation,generation,key,status):
    assert receipt(harness,installation=installation,generation=generation,key=key).status_code==status
    assert not harness[2]


@pytest.mark.parametrize('error,status',[(LookupError('private-sentinel'),404),
    (PermissionError('private-sentinel'),403),(OSError('private-sentinel'),503)])
def test_receipt_read_failure_stays_frozen_and_safe(harness,error,status):
    harness[4].error=error
    response=receipt(harness)
    assert response.status_code==status and 'private-sentinel' not in response.text
    assert len(harness[2])==1


def binding_body():
    return {'scheduleId':'schedule-one','controlRef':{
        'resourceType':'PipelineRuntimeControlRevision','resourceId':'pipeline-control-55555555-5555-4555-8555-555555555555',
        'revision':1,'contentHash':'sha256:'+'a'*64}}


def test_binding_route_uses_authenticated_actor_and_exact_control(harness):
    def bind(**kw):
        harness[2].append(kw)
        return PipelineExactRef(resource_type='PipelineScheduleControlBinding',resource_id='schedule-control-55555555-5555-4555-8555-555555555555',revision=1,content_hash='sha256:'+'b'*64)
    harness[4].bind_schedule=bind
    response=harness[0].post('/v1/pipelines/P01-shop-qyh/schedule-control-bindings',json=binding_body(),headers={'Idempotency-Key':'binding-first'})
    assert response.status_code==200,response.text
    assert response.json()['resourceType']=='PipelineScheduleControlBinding'
    assert harness[2][0]['actor']=='signed-user'
    assert harness[2][0]['pipeline_id']=='P01-shop-qyh' and harness[2][0]['schedule_id']=='schedule-one'
    assert harness[2][0]['idempotency_key']=='binding-first'
    assert harness[3][0].key==('test-org','test-project')


@pytest.mark.parametrize('mode',['actor','tenant','kind','previous','numeric','schedule'])
def test_invalid_binding_does_not_reach_service(harness,mode):
    value=binding_body()
    if mode in ('actor','tenant'):value[mode]='forged'
    elif mode=='kind':value['controlRef']['resourceType']='SourceSelectionRevision'
    elif mode=='previous':value['previousRef']=value['controlRef']
    elif mode=='numeric':value['controlRef']['revision']=True
    else:value['scheduleId']=' '
    response=harness[0].post('/v1/pipelines/P01-shop-qyh/schedule-control-bindings',json=value,headers={'Idempotency-Key':'binding-first'})
    assert response.status_code==422,response.text
    assert not harness[2] and not harness[3]


def test_binding_route_failure_is_safe_and_never_retried(harness):
    def uncertain(**kw):
        harness[2].append(kw)
        raise OSError('private-sentinel')
    harness[4].bind_schedule=uncertain
    response=harness[0].post('/v1/pipelines/P01-shop-qyh/schedule-control-bindings',json=binding_body(),headers={'Idempotency-Key':'binding-first'})
    assert response.status_code==503 and 'private-sentinel' not in response.text
    assert len(harness[2])==1
