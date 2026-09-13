from copy import deepcopy
from uuid import UUID
import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
from aos_api.tenant_scope import TenantScope
from tests.test_ecommerce_business_investigation_lifecycle import draft_case
from tests.test_aip_business_investigation_compile_saga import run_view,request_for


def fixture():
    case=draft_case().model_dump(mode='json',by_alias=True)
    case.update(investigationProfileRef=INITIAL_STORE_PROFILE.exact_ref.model_dump(mode='json',by_alias=True))
    value=BusinessInvestigationCaseRevision.model_validate(case)
    case['contentHash']=value.calculated_content_hash()
    prior=dict(resourceType='BusinessInvestigationCaseRevision',resourceId=case['caseId'],revision=1,contentHash=case['contentHash'])
    case.update(lifecycle='ACTIVE',revision=2,version=2,priorRef=prior)
    case['contentHash']=BusinessInvestigationCaseRevision.model_validate(case).calculated_content_hash()
    case=BusinessInvestigationCaseRevision.model_validate(case)
    run=run_view(caseRef=dict(resourceType='BusinessInvestigationCaseRevision',resourceId=case.case_id,revision=case.revision,contentHash=case.content_hash))
    payload=dict(schemaVersion='aos.ecommerce.analysis-compilation-binding/v1',tenant=dict(orgId='org-org',projectId='dev-project'),
        installationId=str(UUID(int=1)),generation=str(UUID(int=2)),executionEpoch=3,
        domainProfile=INITIAL_STORE_PROFILE.model_dump(mode='json',by_alias=True),
        request=request_for(run).model_dump(mode='json',by_alias=True))
    payload['contentHash']=canonical_sha256(payload)
    return payload,case,run


def test_exact_binding_preserves_distinct_domain_intent_and_compilation():
    from aos_api.ecommerce_analysis_compilation_binding import AnalysisCompilationBinding
    payload,case,run=fixture()
    binding=AnalysisCompilationBinding.model_validate(payload)
    result=binding.validate_current(scope=TenantScope('org-org','dev-project'),installation_id=UUID(int=1),
        generation=UUID(int=2),execution_epoch=3,case=case,run=run)
    assert result==binding.request
    assert binding.domain_profile.profile_id!=result.profile.profile_id


@pytest.mark.parametrize('fault',['tenant','installation','generation','epoch','case','run','nested'])
def test_binding_rejects_current_authority_drift(fault):
    from aos_api.ecommerce_analysis_compilation_binding import AnalysisCompilationBinding
    payload,case,run=fixture();binding=AnalysisCompilationBinding.model_validate(payload)
    args=dict(scope=TenantScope('org-org','dev-project'),installation_id=UUID(int=1),generation=UUID(int=2),execution_epoch=3,case=case,run=run)
    if fault=='tenant':args['scope']=TenantScope('dev-org','dev-project')
    elif fault=='installation':args['installation_id']=UUID(int=9)
    elif fault=='generation':args['generation']=UUID(int=9)
    elif fault=='epoch':args['execution_epoch']=4
    elif fault=='case':args['case']=draft_case('other')
    elif fault=='run':args['run']=run_view(runId='other')
    else:binding.request.task_id='tampered'
    with pytest.raises(ValueError):binding.validate_current(**args)


@pytest.mark.parametrize('fault',['hash','epoch-type','profile-identity'])
def test_rehashed_invalid_binding_is_not_authority(fault):
    from aos_api.ecommerce_analysis_compilation_binding import AnalysisCompilationBinding
    payload,_,_=fixture()
    if fault=='hash':payload['contentHash']='sha256:'+'0'*64
    elif fault=='epoch-type':
        payload['executionEpoch']=True
        payload['contentHash']=canonical_sha256({k:v for k,v in payload.items() if k!='contentHash'})
    else:
        profile=payload['request']['profile']
        profile['profileId']=payload['domainProfile']['profileId']
        profile['revision']=payload['domainProfile']['revision']
        profile['contentHash']=canonical_sha256({k:v for k,v in profile.items() if k!='contentHash'}).removeprefix('sha256:')
        payload['request']['taskBriefSpec']['investigationProfileRef'].update(resourceId=profile['profileId'],revision=profile['revision'],contentHash=profile['contentHash'])
        payload['contentHash']=canonical_sha256({k:v for k,v in payload.items() if k!='contentHash'})
    with pytest.raises(ValueError):AnalysisCompilationBinding.model_validate(payload)
