"""Pure snapshot resume contract checks; no runtime authority or effects."""
from copy import deepcopy
import pytest

from aos_api.ecommerce_growth_runtime_adapters import _analysis_command_hash, _strict_analysis_command
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_analysis_snapshot_resume_contracts import (
    strict_snapshot_resume_command, SnapshotFulfillmentResumeResult, validate_snapshot_resume_result,
)

SCOPE=TenantScope(org_id='org-org',project_id='dev-project')


def ref(kind,identity,*,receipt=False,revision=1):
    result=dict(resourceType=kind,resourceId=identity,revision=revision,contentHash='sha256:'+'a'*64)
    if receipt:result['receiptId']=identity
    return result


def command():
    value=dict(operation='runtime.analysis.resume_snapshot',idempotencyKey='snapshot-resume-test',
        occurrenceRef=ref('AutomationOccurrence','occurrence'),caseRef=ref('BusinessInvestigationCaseRevision','case'),
        profileRef=ref('InvestigationProfileRevision','profile'),cutoffAt='2026-09-15T00:00:00+08:00',
        priorReceiptRef=ref('AnalysisRuntimeReceipt','prior',receipt=True),
        requirementRef=ref('DataRequirementRevision','requirement'),
        fulfillmentRef=ref('DataFulfillmentReceipt','fulfillment',receipt=True),
        checkpointRef=ref('CheckpointRevision','checkpoint'),priorPlanRef=ref('PlanRevision','plan'),
        sourceReadinessRef=ref('SourceReadinessEnvelope','readiness',receipt=True),
        evidenceRefs=[ref('EvidenceBundleRevision','bundle')],observedAt='2026-09-15T00:01:00+08:00',
        businessEvidenceRef=ref('Evidence','business'),
        readinessPolicyRef=ref('SnapshotReadinessPolicy','content/policies/readiness.json',revision='1.22.0'))
    return seal(value)


def seal(value):
    value['requestHash']=_analysis_command_hash({k:v for k,v in value.items() if k!='requestHash'})
    return value


def result():
    cmd=command()
    return dict(tenant=dict(orgId='org-org',projectId='dev-project'),commandId=cmd['idempotencyKey'],
        requestHash=cmd['requestHash'],dataRequirementRef=cmd['requirementRef'],
        fulfillmentReceiptRef=cmd['fulfillmentRef'],sourceReadinessRef=cmd['sourceReadinessRef'],
        evidenceBundleRef=dict(cmd['evidenceRefs'][0],contentHash='a'*64),
        businessEvidenceRef=cmd['businessEvidenceRef'],checkpointRef=cmd['checkpointRef'],
        taskRef=dict(resourceType='Task',resourceId='task',version=3),
        taskRunRef=dict(resourceType='TaskRun',resourceId='task-run',version=4))


def test_snapshot_contract_preserves_exact_original_types_without_opening_runtime():
    cmd=command();original=deepcopy(cmd)
    parsed=strict_snapshot_resume_command(cmd)
    assert cmd==original and parsed['operation']=='runtime.analysis.resume_snapshot'
    assert parsed['readinessPolicyRef'].revision=='1.22.0'
    assert parsed['evidenceRefs'][0].resource_type=='EvidenceBundleRevision'
    assert 'mappingRef' not in parsed
    with pytest.raises(ValueError):_strict_analysis_command(cmd)
    output=validate_snapshot_resume_result(cmd,result(),scope=SCOPE)
    assert validate_snapshot_resume_result(cmd,output,scope=SCOPE)==output
    assert output.task_run_status=='running' and output.task_run_transition_count==1
    assert output.external_effect_authorized is False
    assert 'hydrationReceiptRef' not in output.model_dump(by_alias=True)


@pytest.mark.parametrize('fault',[
    'old-mode','unknown-field','mapping','hydration','missing','null','boolean-revision','string-revision',
    'receipt-id','no-receipt','policy-int','policy-type','policy-receipt','policy-extra','policy-version',
    'business-type','empty-evidence','duplicate-evidence','dataset','naive-cutoff','naive-observed',
    'before-cutoff','after-window','key-whitespace','hash','noncanonical-ref',
])
def test_bad_snapshot_command_is_rejected_even_with_recomputed_hash(fault):
    cmd=command()
    if fault=='old-mode':cmd['operation']='runtime.analysis.resume_data'
    elif fault=='unknown-field':cmd['authorized']=True
    elif fault=='mapping':cmd['mappingRef']=ref('SourceMappingRevision','mapping')
    elif fault=='hydration':cmd['hydrationReceiptRef']=ref('SemanticHydrationReceipt','hydration',receipt=True)
    elif fault=='missing':del cmd['businessEvidenceRef']
    elif fault=='null':cmd['fulfillmentRef']=None
    elif fault=='boolean-revision':cmd['requirementRef']['revision']=True
    elif fault=='string-revision':cmd['requirementRef']['revision']='1'
    elif fault=='receipt-id':cmd['fulfillmentRef']['receiptId']='another'
    elif fault=='no-receipt':del cmd['sourceReadinessRef']['receiptId']
    elif fault=='policy-int':cmd['readinessPolicyRef']['revision']=1
    elif fault=='policy-type':cmd['readinessPolicyRef']['resourceType']='Mapping'
    elif fault=='policy-receipt':cmd['readinessPolicyRef']['receiptId']='other'
    elif fault=='policy-extra':cmd['readinessPolicyRef']['approved']=True
    elif fault=='policy-version':cmd['readinessPolicyRef']['revision']='latest'
    elif fault=='business-type':cmd['businessEvidenceRef']['resourceType']='DatasetRevision'
    elif fault=='empty-evidence':cmd['evidenceRefs']=[]
    elif fault=='duplicate-evidence':cmd['evidenceRefs']*=2
    elif fault=='dataset':cmd['evidenceRefs'][0]['resourceType']='DatasetRevision'
    elif fault=='naive-cutoff':cmd['cutoffAt']='2026-09-15T00:00:00'
    elif fault=='naive-observed':cmd['observedAt']='2026-09-15T00:01:00'
    elif fault=='before-cutoff':cmd['observedAt']='2026-09-14T23:59:59+08:00'
    elif fault=='after-window':cmd['observedAt']='2026-09-16T00:00:01+08:00'
    elif fault=='key-whitespace':cmd['idempotencyKey']=' key '
    elif fault=='noncanonical-ref':cmd['checkpointRef']['receiptId']=None
    seal(cmd)
    if fault=='hash':cmd['requestHash']='sha256:'+'b'*64
    with pytest.raises(ValueError):strict_snapshot_resume_command(cmd)


@pytest.mark.parametrize('fault',['requirement','fulfillment','readiness','bundle','business','checkpoint',
    'command','hash','hydration','task','task-run','effects','provider','source','transition','copy'])
def test_snapshot_result_must_match_command_and_original_kinds(fault):
    item=result()
    if fault in {'requirement','fulfillment','readiness','bundle','business','checkpoint'}:
        key=dict(requirement='dataRequirementRef',fulfillment='fulfillmentReceiptRef',readiness='sourceReadinessRef',
            bundle='evidenceBundleRef',business='businessEvidenceRef',checkpoint='checkpointRef')[fault]
        item[key]['resourceId']='other'
    elif fault=='command':item['commandId']='other'
    elif fault=='hash':item['requestHash']='sha256:'+'c'*64
    elif fault=='hydration':item['hydrationReceiptRef']=ref('SemanticHydrationReceipt','fake',receipt=True)
    elif fault=='task':item['taskRef']['resourceType']='TaskRun'
    elif fault=='task-run':item['taskRunRef']['resourceType']='Task'
    elif fault=='effects':item['externalEffectAuthorized']=True
    elif fault=='provider':item['providerInvocationCount']=1
    elif fault=='source':item['sourceReadCount']=1
    elif fault=='transition':item['taskRunTransitionCount']=2
    elif fault=='copy':item=SnapshotFulfillmentResumeResult.model_validate(item).model_copy(update={'external_effect_authorized':True})
    with pytest.raises(ValueError):validate_snapshot_resume_result(command(),item,scope=SCOPE)


@pytest.mark.parametrize('fault',['org','project','boolean-ref','string-ref','boolean-bundle','boolean-task',
    'boolean-count','integer-effect','result-copy-ref','result-copy-task','result-copy-bundle'])
def test_result_scope_and_canonical_primitive_types_are_explicit(fault):
    item=result()
    if fault=='org':item['tenant']['orgId']='dev-org'
    elif fault=='project':item['tenant']['projectId']='other'
    elif fault=='boolean-ref':item['dataRequirementRef']['revision']=True
    elif fault=='string-ref':item['dataRequirementRef']['revision']='1'
    elif fault=='boolean-bundle':item['evidenceBundleRef']['revision']=True
    elif fault=='boolean-task':item['taskRunRef']['version']=True
    elif fault=='boolean-count':item['taskRunTransitionCount']=True
    elif fault=='integer-effect':item['externalEffectAuthorized']=0
    elif fault=='result-copy-ref':
        item=SnapshotFulfillmentResumeResult.model_validate(item)
        item=item.model_copy(update={'data_requirement_ref':item.data_requirement_ref.model_copy(update={'revision':True})})
    elif fault=='result-copy-task':
        item=SnapshotFulfillmentResumeResult.model_validate(item)
        item=item.model_copy(update={'task_ref':item.task_ref.model_copy(update={'version':0})})
    elif fault=='result-copy-bundle':
        item=SnapshotFulfillmentResumeResult.model_validate(item)
        item=item.model_copy(update={'evidence_bundle_ref':item.evidence_bundle_ref.model_copy(update={'revision':True})})
    with pytest.raises(ValueError):validate_snapshot_resume_result(command(),item,scope=SCOPE)
