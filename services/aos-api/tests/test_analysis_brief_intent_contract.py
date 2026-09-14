from copy import deepcopy
from uuid import UUID
import pytest
from tests.test_ecommerce_analysis_compilation_binding import fixture
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analysis_compilation_binding import AnalysisCompilationBinding
from aos_api.aip_business_investigation_compiler import BusinessInvestigationProfileCompiler, BusinessInvestigationCompilationBlocked
from aos_api.tenant_scope import TenantScope


def intent_payload():
    payload,case,run=fixture()
    request=payload['request']
    domain=payload['domainProfile']
    request['taskBriefSpec']=dict(schemaVersion='aos.aip.business-investigation-task-brief-intent/v2',
        caseRef=deepcopy(request['caseRef']),runRef=deepcopy(request['runRef']),
        domainProfileRef=dict(resourceType='InvestigationProfileRevision',resourceId=domain['profileId'],
            revision=domain['revision'],contentHash=domain['contentHash'].removeprefix('sha256:')),
        analysisType=domain['analysisType'],compilerProfile=request['profile']['compilerProfile'])
    return payload,case,run


@pytest.mark.parametrize('fault',[None,'domain','compiler','case','schema'])
def test_intent_brief_breaks_context_hash_cycle_without_weakening_binding(fault):
    payload,case,run=intent_payload()
    spec=payload['request']['taskBriefSpec']
    if fault=='domain':spec['domainProfileRef']['contentHash']='d'*64
    elif fault=='compiler':spec['compilerProfile']='other'
    elif fault=='case':spec['caseRef']['resourceId']='other'
    elif fault=='schema':spec.pop('schemaVersion')
    payload['contentHash']=canonical_sha256({k:v for k,v in payload.items() if k!='contentHash'})
    def validate():
        binding=AnalysisCompilationBinding.model_validate(payload)
        request=binding.validate_current(scope=TenantScope('org-org','dev-project'),installation_id=UUID(int=1),
            generation=UUID(int=2),execution_epoch=3,case=case,run=run)
        return request
    if fault:
        with pytest.raises(ValueError):validate()
    else:
        request=validate()
        refs=dict(BusinessInvestigationProfileCompiler._input_refs(request))
        assert refs['DOMAIN_PROFILE']==request.task_brief_spec.domain_profile_ref
        compiler=BusinessInvestigationProfileCompiler(None,lambda scope,ref:ref!=refs['DOMAIN_PROFILE'])
        with pytest.raises(BusinessInvestigationCompilationBlocked,match='DOMAIN_PROFILE_NOT_RESOLVED'):
            compiler.compile(TenantScope('org-org','dev-project'),'actor','intent-test',request)
        # Context may be created after this exact intent Brief is frozen.
        frozen_spec=deepcopy(spec)
        profile=payload['request']['profile']
        profile['productionContextRef']['contentHash']='e'*64
        profile['contentHash']=canonical_sha256({k:v for k,v in profile.items() if k!='contentHash'}).removeprefix('sha256:')
        payload['contentHash']=canonical_sha256({k:v for k,v in payload.items() if k!='contentHash'})
        validate()
        assert payload['request']['taskBriefSpec']==frozen_spec
