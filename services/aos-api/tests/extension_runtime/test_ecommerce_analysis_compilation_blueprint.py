from copy import deepcopy
import pytest
from test_ecommerce_analysis_start_operation import _package
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.ecommerce_business_investigation_aip_authority import build_stage_template_request
from aos_api.asset_registry.canonical_json import canonical_sha256


def request():
    return dict(kind='build_analysis_compilation_blueprint',profileRef=INITIAL_STORE_PROFILE.exact_ref.model_dump(mode='json',by_alias=True,exclude_none=True))


def test_installed_blueprint_matches_compilable_stage_contract():
    body=request();original=deepcopy(body)
    result=_package().handle('ecommerce_growth_analysis_advance',body,object())
    expected=build_stage_template_request().model_dump(mode='json',by_alias=True)
    expected['profile']=INITIAL_STORE_PROFILE.responsibility_template_code
    assert result['stageTemplateRequest']==expected
    assert result['profileRef']==body['profileRef']
    assert result['compilerProfile']==expected['profile']
    assert result['schemaVersion']=='aos.ecommerce.analysis-compilation-blueprint/v2'
    assert result['startupContextPolicy']==dict(
        schemaVersion='aos.ecommerce.analysis-startup-context-policy/v1',
        purpose='analysis-start',requiredFactIds=['analysis.original-event-case-run-lineage'],
        businessFactCoverage='not-evaluated',pendingFactProfilesSource='domain-profile.requiredFactProfiles',
        evalStageId='portrait',evalPurpose='skill-publication-contract')
    assert [(s['stageId'],s['skillId']) for s in result['stageSkills']]==[
        ('portrait','ecommerce.skill.D01'),('diagnosis','ecommerce.skill.D02'),('solution-design','ecommerce.skill.D03')]
    assert result['contentHash']==canonical_sha256({k:v for k,v in result.items() if k!='contentHash'})
    assert body==original
    assert _package().handle('ecommerce_growth_analysis_advance',body,object())==result


@pytest.mark.parametrize('fault',['extra','hash','revision','id','type','receipt','boolean'])
def test_blueprint_rejects_unrecognized_profile(fault):
    body=request()
    if fault=='extra':body['tenant']='org-org'
    elif fault=='receipt':body['profileRef']['receiptId']='invented'
    else:
        key,value={'hash':('contentHash','sha256:'+'f'*64),'revision':('revision',2),'id':('resourceId','other'),
            'type':('resourceType','Other'),'boolean':('revision',True)}[fault]
        body['profileRef'][key]=value
    with pytest.raises(ValueError):_package().handle('ecommerce_growth_analysis_advance',body,object())
