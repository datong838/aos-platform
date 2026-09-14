"""Compilation assembly fixtures are contracts, not live publication authority."""
from copy import deepcopy
from uuid import UUID
import pytest
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.tenant_scope import TenantScope
from tests.test_ecommerce_analysis_compilation_binding import fixture
from tests.test_ecommerce_analysis_skill_set import data
from test_ecommerce_analysis_start_operation import _package


def inputs():
    _,case,run=fixture()
    scope=TenantScope('org-org','dev-project')
    blueprint=_package().handle('ecommerce_growth_analysis_advance',dict(kind='build_analysis_compilation_blueprint',
        profileRef=INITIAL_STORE_PROFILE.exact_ref.model_dump(mode='json',by_alias=True,exclude_none=True)),object())
    def ref(kind,identity,hash='a'*64):
        return dict(resourceType=kind,resourceId=identity,revision=1,contentHash=hash)
    def aip(value):
        value={k:v for k,v in deepcopy(value).items() if v is not None};value['contentHash']=value['contentHash'].removeprefix('sha256:');return value
    case_ref=ref('BusinessInvestigationCaseRevision',case.case_id,case.content_hash.removeprefix('sha256:'));case_ref['revision']=case.revision
    run_ref=ref('BusinessInvestigationRun',run.authority.run_id,run.authority.content_hash.removeprefix('sha256:'))
    brief=ref('TaskBriefRevision','brief')
    context=ref('ProductionContextRevision','context')
    role_ref=ref('ResponsibilityPlanRevision','roles')
    tenant=dict(orgId=scope.org_id,projectId=scope.project_id)
    installation=dict(installationId=str(UUID(int=1)),generation=str(UUID(int=2)),executionEpoch=3)
    _,binding,skillset=data()
    skills=[];bindings=[]
    for i,item in enumerate(blueprint['stageSkills']):
        skill=dict(skillId=item['skillId'],revision=2,contentHash=str(i+1)*64,lifecycle='published',publicationTenant=tenant,
            logicRevisionRef=dict(assetType='LogicRevision',assetId=item['canonicalLogicId'],revision=1,contentHash='b'*64))
        skills.append(skill)
        b=binding.model_dump(mode='json',by_alias=True)
        b.update(bindingId='binding-'+str(i),skill=dict(assetType='SkillTemplate',assetId=skill['skillId'],revision=2,contentHash=skill['contentHash']))
        bindings.append(b)
    skillset.update(schemaVersion='aos.ecommerce.analysis-skill-binding-set/v1',responsibilityPlanRef=role_ref,bindings=bindings)
    skillset['contentHash']=canonical_sha256(skillset)
    from aos_api.ecommerce_analysis_skill_set import AnalysisSkillBindingSet
    selected=AnalysisSkillBindingSet.model_validate(skillset)
    stage=dict(blueprint['stageTemplateRequest'],templateId='stages',revision=1,lifecycle='frozen',readiness='ready',
        tenant=tenant,contentHash=canonical_sha256(blueprint['stageTemplateRequest']).removeprefix('sha256:'))
    spec=dict(schemaVersion='aos.aip.business-investigation-task-brief-intent/v2',caseRef=case_ref,runRef=run_ref,
        domainProfileRef=aip(INITIAL_STORE_PROFILE.exact_ref.model_dump(mode='json',by_alias=True)),
        analysisType=INITIAL_STORE_PROFILE.analysis_type,compilerProfile=blueprint['compilerProfile'])
    prepared=dict(currentInstallation=installation,compilationBlueprint=blueprint,stageTemplate=stage,
        skills=skills,skillBindingSet=skillset,skillBindingSetRef=selected.exact_ref.model_dump(mode='json',by_alias=True),
        responsibilityPlan=dict(planId='roles',revision=1,contentHash='a'*64,lifecycle='frozen',readiness='ready',coverage='complete',
            profile=blueprint['compilerProfile'],tenant=tenant,blockers=[]),
        task=dict(id='task',version=1,goal=spec,status='pending',currentPlanRevisionId=None),taskBriefRef=brief,taskBriefSpec=spec,
        productionContextRef=context,productionContext=dict(contextId='context',revision=1,contentHash='a'*64,
            taskId='task',briefRef=brief,responsibilityPlanRef=role_ref,profile=blueprint['compilerProfile'],
            tenant=tenant,lifecycle='frozen',readiness='ready',blockers=[]))
    return dict(scope=scope,case=case,run=run,domain_profile=INITIAL_STORE_PROFILE,blueprint=blueprint,prepared=prepared)


def build(args):
    from aos_api.ecommerce_analysis_compilation_binding import build_analysis_compilation_binding
    return build_analysis_compilation_binding(**args)


def test_binding_assembles_all_stages_by_blueprint_not_reader_order():
    args=inputs();first=build(args)
    args['prepared']['skills'].reverse()
    assert build(args)==first
    request=first.request
    assert [s.stage_id for s in request.profile.stages]==['portrait','diagnosis','solution-design']
    assert [s.resource_id for s in request.profile.ordered_skill_refs]==[s['skillId'] for s in args['blueprint']['stageSkills']]
    assert request.profile.logic_ref.resource_id==args['blueprint']['stageSkills'][0]['canonicalLogicId']
    assert request.profile.profile_id!=INITIAL_STORE_PROFILE.profile_id
    assert request.task_id=='task'


@pytest.mark.parametrize('fault',['context-task','context-brief','context-role','context-hash','role-tenant','stage-body',
    'stage-profile','skill-logic','skill-hash','skill-missing','skill-duplicate','installation','binding-ref','task-goal','blueprint'])
def test_binding_rejects_cross_composed_dependencies(fault):
    args=inputs();p=args['prepared']
    if fault=='context-task':p['productionContext']['taskId']='other'
    elif fault=='context-brief':p['productionContext']['briefRef']={**p['taskBriefRef'],'resourceId':'other'}
    elif fault=='context-role':p['productionContext']['responsibilityPlanRef']['resourceId']='other'
    elif fault=='context-hash':p['productionContext']['contentHash']='f'*64
    elif fault=='role-tenant':p['responsibilityPlan']['tenant']={'orgId':'dev-org','projectId':'dev-project'}
    elif fault=='stage-body':p['stageTemplate']['stages']=[]
    elif fault=='stage-profile':p['stageTemplate']['profile']='other'
    elif fault=='skill-logic':p['skills'][0]['logicRevisionRef']['assetId']='other'
    elif fault=='skill-hash':p['skills'][0]['contentHash']='f'*64
    elif fault=='skill-missing':p['skills'].pop()
    elif fault=='skill-duplicate':p['skills'].append(deepcopy(p['skills'][0]))
    elif fault=='installation':p['currentInstallation']['generation']=str(UUID(int=9))
    elif fault=='binding-ref':p['skillBindingSetRef']['resourceId']='other'
    elif fault=='task-goal':p['task']['goal']={}
    elif fault=='blueprint':p['compilationBlueprint']=dict(p['compilationBlueprint'],compilerProfile='other')
    with pytest.raises(ValueError):build(args)
