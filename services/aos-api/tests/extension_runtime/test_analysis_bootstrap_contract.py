"""Bootstrap intent contracts only; no live authorization implied."""
from copy import deepcopy
import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompileSaga
from tests.test_aip_business_investigation_compile_saga import FixedCompiler,MemoryReceipts
from test_analysis_compilation_preparation import inputs,build


def payload():
    args=inputs();binding=build(args)
    receipt=BusinessInvestigationCompileSaga(FixedCompiler(),MemoryReceipts()).execute(
        args['scope'],'fixture',args['run'].authority.trigger_key,args['run'],binding.request).authority
    body=dict(schemaVersion='aos.ecommerce.analysis-bootstrap-intent/v1',operation='ecommerce_analysis_bootstrap',
        mode='paused-before-first-step',businessExecutionAuthorized=False,externalEffectAuthorized=False,
        tenant=dict(orgId='org-org',projectId='dev-project'),
        occurrenceRef=dict(resourceType='AutomationOccurrence',resourceId='fixture-occurrence',revision=1,contentHash='sha256:'+'a'*64,receiptId=None),
        sourceControlReceiptRef=dict(resourceType='EventPolicyControlReceipt',resourceId='fixture-control',revision=1,contentHash='sha256:'+'b'*64,receiptId=None),
        compilationBinding=binding.model_dump(mode='json',by_alias=True),
        compilationReceipt=receipt.model_dump(mode='json',by_alias=True))
    return dict(body,contentHash=canonical_sha256(body))


def parse(body):
    from aos_api.ecommerce_analysis_bootstrap_contract import AnalysisBootstrapIntent
    return AnalysisBootstrapIntent.model_validate(body)


def test_bootstrap_binds_compilation_without_business_authorization():
    intent=parse(payload())
    assert intent.mode=='paused-before-first-step'
    assert intent.business_execution_authorized is False and intent.external_effect_authorized is False
    assert intent.checked()==intent
    intent.compilation_receipt.task_id='substituted'
    with pytest.raises(ValueError):intent.checked()


@pytest.mark.parametrize('fault',['mode','business','external','false-coercion','tenant','occurrence','control','task',
    'profile','receipt-request','binding-hash','content-hash','extra'])
def test_bootstrap_rejects_expanded_or_cross_composed_intent(fault):
    body=payload()
    if fault=='mode':body['mode']='run-now'
    elif fault=='business':body['businessExecutionAuthorized']=True
    elif fault=='external':body['externalEffectAuthorized']=True
    elif fault=='false-coercion':body['businessExecutionAuthorized']=0
    elif fault=='tenant':body['tenant']['orgId']='dev-org'
    elif fault=='occurrence':body['occurrenceRef']['resourceType']='ActionApprovalEvent'
    elif fault=='control':body['sourceControlReceiptRef']['resourceType']='ActionApprovalEvent'
    elif fault=='task':body['compilationReceipt']['taskId']='other'
    elif fault=='profile':body['compilationReceipt']['profileRef']['resourceId']='other'
    elif fault=='receipt-request':body['compilationReceipt']['requestHash']='sha256:'+'f'*64
    elif fault=='binding-hash':body['compilationBinding']['contentHash']='sha256:'+'f'*64
    elif fault=='extra':body['skipApproval']=True
    body['contentHash']=canonical_sha256({k:v for k,v in body.items() if k!='contentHash'})
    if fault=='content-hash':body['contentHash']='sha256:'+'f'*64
    with pytest.raises(ValueError):parse(body)
