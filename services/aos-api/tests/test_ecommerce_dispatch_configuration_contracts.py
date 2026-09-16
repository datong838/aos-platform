"""Configuration continuation is an exact request, never caller-supplied authority."""
from copy import deepcopy
import json
import pytest
from aos_api.ecommerce_dispatch_configuration_contracts import DispatchConfigurationRefreshRequest
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS


def request():
    uid=lambda n:f'00000000-0000-4000-8000-{n:012d}'
    ref=lambda kind,n:dict(resourceType=kind,resourceId=uid(n),revision=1,contentHash='sha256:'+'a'*64)
    return dict(schemaVersion='aos.ecommerce.dispatch-configuration-refresh/v1',orgId='org-org',projectId='dev-project',
        installationRef=dict(installationId=uid(1),revision=5,lockHash='sha256:'+'b'*64,overlayRevision='tenant-overlay'),
        generation=uid(2),cutoverGroupId=uid(3),expectedGroupRevision=30,
        sourceAuthorityRef=ref('CutoverResumeReceipt',4),sourceRuntimeRevision=6,sourceExecutionEpoch=3,
        sourceConfigurationRef=dict(configurationId=uid(5),revision=1,hash='sha256:'+'c'*64),
        targetRuntimeRevision=9,targetExecutionEpoch=5,
        targetConfigurationRef=dict(configurationId=uid(5),revision=2,hash='sha256:'+'d'*64),
        configureOperationId=uid(6),configureOperationRevision=8,enableOperationId=uid(7),enableOperationRevision=5,
        operationIds=sorted(ECOMMERCE_GROWTH_OPERATIONS),approvalRef=ref('ActionApprovalEvent',8),
        idempotencyKey='fixture-configuration-refresh',externalEffectsAllowed=False,resumeBusinessRuns=False)


def parse(body):return DispatchConfigurationRefreshRequest.model_validate_json(json.dumps(body))


def test_exact_request_roundtrip_hash_and_approval_scope():
    body=request();value=parse(body)
    assert value.wire()==body
    assert parse(json.loads(value.model_dump_json(by_alias=True))).request_hash()==value.request_hash()
    intent=value.approval_intent()
    assert 'approvalRef' not in intent and intent['sourceConfigurationRef']!=intent['targetConfigurationRef']
    changed=deepcopy(body);changed['projectId']='other-project'
    assert parse(changed).request_hash()!=value.request_hash()
    with pytest.raises(ValueError):value.target_execution_epoch=6


@pytest.mark.parametrize('field,value',[
    ('targetExecutionEpoch',3),('targetRuntimeRevision',6),('expectedGroupRevision',True),
    ('configureOperationRevision','8'),('generation','not-a-uuid'),('orgId',' org-org'),
    ('externalEffectsAllowed',True),('externalEffectsAllowed',0),('resumeBusinessRuns',True),
    ('idempotencyKey',' key'),('drained',True),('authorized',True),
])
def test_noncanonical_or_unsafe_requests_rejected(field,value):
    body=request();body[field]=value
    with pytest.raises(ValueError):parse(body)


@pytest.mark.parametrize('fault',['subset','duplicate','reversed','foreign-config','same-config-revision','wrong-source-kind','wrong-approval-kind','same-operation'])
def test_incomplete_or_mixed_authority_rejected(fault):
    body=request()
    if fault=='subset':body['operationIds'].pop()
    elif fault=='duplicate':body['operationIds'][-1]=body['operationIds'][0]
    elif fault=='reversed':body['operationIds'].reverse()
    elif fault=='foreign-config':body['targetConfigurationRef']['configurationId']=body['generation']
    elif fault=='same-config-revision':body['targetConfigurationRef']['revision']=1
    elif fault=='wrong-source-kind':body['sourceAuthorityRef']['resourceType']='CutoverPrepareReceipt'
    elif fault=='wrong-approval-kind':body['approvalRef']['resourceType']='SourceSelectionRevision'
    else:body['enableOperationId']=body['configureOperationId']
    with pytest.raises(ValueError):parse(body)
