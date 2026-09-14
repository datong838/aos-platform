"""Explicit L1 intent to per-Run AIP compilation binding; not execution authority."""
from typing import Literal
from uuid import UUID
from pydantic import Field, StrictInt, model_validator
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.aip_business_investigation_compiler import CompileBusinessInvestigationRequest
from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompileSaga, BusinessInvestigationCompileConflict
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileRevision
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunView
from aos_api.tenant_scope import TenantScope


class AnalysisCompilationBinding(AipContractModel):
    schema_version: Literal['aos.ecommerce.analysis-compilation-binding/v1']='aos.ecommerce.analysis-compilation-binding/v1'
    tenant: TenantContext
    installation_id: UUID
    generation: UUID
    execution_epoch: StrictInt=Field(gt=0)
    domain_profile: EcommerceInvestigationProfileRevision
    request: CompileBusinessInvestigationRequest
    content_hash: str=Field(pattern=r'^sha256:[0-9a-f]{64}$')

    @model_validator(mode='after')
    def exact_composition(self):
        if canonical_sha256(self.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))!=self.content_hash:
            raise ValueError('analysis compilation binding hash drifted')
        domain,compiled=self.domain_profile,self.request.profile
        from aos_api.aip_business_investigation_compiler import BusinessInvestigationTaskBriefIntentSpec
        spec = self.request.task_brief_spec
        if isinstance(spec, BusinessInvestigationTaskBriefIntentSpec):
            ref = spec.domain_profile_ref
            if (ref.resource_id, ref.revision, ref.content_hash) != (
                    domain.profile_id, domain.revision, domain.content_hash.removeprefix('sha256:')):
                raise ValueError('TaskBrief domain intent differs from original profile')
        if (domain.analysis_type!=compiled.analysis_type
                or tuple(stage.stage_id for stage in domain.stages)!=tuple(stage.stage_id for stage in compiled.stages)
                or (domain.profile_id,domain.revision)==(compiled.profile_id,compiled.revision)):
            raise ValueError('domain intent and compilation profile are not distinctly bound')
        return self

    def validate_current(self,*,scope,installation_id,generation,execution_epoch,case,run):
        # Nested Pydantic values are mutable. Reparse before any authority use.
        current=type(self).model_validate(self.model_dump(mode='json',by_alias=True))
        if (type(scope) is not TenantScope or type(installation_id) is not UUID or type(generation) is not UUID
                or type(execution_epoch) is not int
                or (current.tenant.org_id,current.tenant.project_id)!=scope.key
                or (current.installation_id,current.generation,current.execution_epoch)!=(installation_id,generation,execution_epoch)):
            raise ValueError('current compilation installation or tenant differs')
        if type(case) is not BusinessInvestigationCaseRevision or type(run) is not BusinessInvestigationRunView:
            raise ValueError('exact current Case and Run required')
        case=BusinessInvestigationCaseRevision.model_validate(case.model_dump(mode='json',by_alias=True))
        run=BusinessInvestigationRunView.model_validate(run.model_dump(mode='json',by_alias=True))
        if ((case.tenant.org_id,case.tenant.project_id)!=scope.key or case.lifecycle.value!='ACTIVE'
                or case.calculated_content_hash()!=case.content_hash
                or case.investigation_profile_ref!=current.domain_profile.exact_ref
                or case.analysis_type.value!=current.domain_profile.analysis_type
                or (run.authority.case_ref.resource_id,run.authority.case_ref.revision,run.authority.case_ref.content_hash)
                   !=(case.case_id,case.revision,case.content_hash)):
            raise ValueError('current Case does not authorize this analysis intent')
        try:
            BusinessInvestigationCompileSaga._validate_inputs(scope,run,current.request)
        except BusinessInvestigationCompileConflict as exc:
            raise ValueError('current compilation Run lineage differs') from exc
        return current.request


def build_analysis_compilation_binding(*, scope, case, run, domain_profile, blueprint, prepared):
    """Assemble checked snapshots inside the current Context callback, not authority.

    The caller must keep the Context/selection owner transaction open through Saga
    execution. Every reference still requires the canonical compiler's resolver.
    """
    from copy import deepcopy
    from aos_api.aip_business_investigation_compiler import BusinessInvestigationProfileRevision
    from aos_api.aip_production_contracts import ExactRevisionRef
    from aos_api.ecommerce_analysis_skill_set import AnalysisSkillBindingSet
    from aos_api.ecommerce_product_event_analysis_port import validate_analysis_compilation_blueprint

    if type(scope) is not TenantScope or type(prepared) is not dict:
        raise ValueError('scoped current compilation preparation required')
    blueprint = validate_analysis_compilation_blueprint(domain_profile, blueprint)
    p = deepcopy(prepared)
    if p['compilationBlueprint'] != blueprint:
        raise ValueError('prepared compilation blueprint differs')
    tenant = dict(orgId=scope.org_id, projectId=scope.project_id)
    compiler_profile = blueprint['compilerProfile']

    def exact(kind, identity, revision, digest):
        return ExactRevisionRef(resourceType=kind, resourceId=identity, revision=revision,
                                contentHash=digest.removeprefix('sha256:'))

    def document_ref(kind, document, identity):
        if (document['tenant'] != tenant or document['lifecycle'] != 'frozen'
                or document['readiness'] != 'ready' or document.get('blockers')
                or document['profile'] != compiler_profile):
            raise ValueError('prepared compilation document unavailable or out of scope')
        return exact(kind, document[identity], document['revision'], document['contentHash'])

    stage, role, context = p['stageTemplate'], p['responsibilityPlan'], p['productionContext']
    stage_ref = document_ref('StageTemplateRevision', stage, 'templateId')
    role_ref = document_ref('ResponsibilityPlanRevision', role, 'planId')
    context_ref = document_ref('ProductionContextRevision', context, 'contextId')
    if (role['coverage'] != 'complete'
            or {key: stage[key] for key in ('profile', 'sourceBundleRef', 'stages')} != blueprint['stageTemplateRequest']
            or stage_ref.content_hash != canonical_sha256(blueprint['stageTemplateRequest']).removeprefix('sha256:')):
        raise ValueError('prepared stage or responsibilities differ from blueprint')
    brief_ref = ExactRevisionRef.model_validate(p['taskBriefRef'])
    task, spec = p['task'], p['taskBriefSpec']
    if (task['status'] != 'pending' or task.get('currentPlanRevisionId') is not None or task['goal'] != spec
            or context['taskId'] != task['id'] or context['briefRef'] != brief_ref.model_dump(mode='json', by_alias=True)
            or ExactRevisionRef.model_validate(context['responsibilityPlanRef']) != role_ref
            or ExactRevisionRef.model_validate(p['productionContextRef']) != context_ref):
        raise ValueError('prepared Task Brief Context lineage differs')
    selected = AnalysisSkillBindingSet.model_validate(p['skillBindingSet'])
    installation = p['currentInstallation']
    if (selected.tenant.model_dump(mode='json', by_alias=True) != tenant
            or (str(selected.installation_id), str(selected.generation), selected.execution_epoch)
               != (installation['installationId'], installation['generation'], installation['executionEpoch'])
            or type(installation['executionEpoch']) is not int
            or selected.responsibility_plan_ref != role_ref
            or selected.exact_ref != ExactRevisionRef.model_validate(p['skillBindingSetRef'])):
        raise ValueError('prepared skill set installation or reference differs')
    skills = {item['skillId']: item for item in p['skills']}
    expected = {item['skillId'] for item in blueprint['stageSkills']}
    bindings = {item.skill.asset_id: item for item in selected.bindings}
    if len(skills) != len(p['skills']) or set(skills) != expected or set(bindings) != expected:
        raise ValueError('prepared stage skill selection is incomplete or ambiguous')
    stages, ordered, entry_logic = [], [], None
    for entry in blueprint['stageSkills']:
        skill, binding = skills[entry['skillId']], bindings[entry['skillId']]
        logic = skill.get('logicRevisionRef') or {}
        if (skill['lifecycle'] != 'published' or skill['publicationTenant'] != tenant
                or (skill['skillId'], skill['revision'], skill['contentHash'])
                   != (binding.skill.asset_id, binding.skill.revision, binding.skill.content_hash)
                or logic.get('assetType') != 'LogicRevision' or logic.get('assetId') != entry['canonicalLogicId']):
            raise ValueError('prepared Skill or Logic exact lineage differs')
        skill_ref = exact('SkillTemplateRevision', skill['skillId'], skill['revision'], skill['contentHash'])
        logic_ref = exact('LogicRevision', logic['assetId'], logic['revision'], logic['contentHash'])
        if entry_logic is None:
            entry_logic = logic_ref
        if skill_ref not in ordered:
            ordered.append(skill_ref)
        stages.append(dict(stageId=entry['stageId'], skillRefs=[skill_ref.model_dump(mode='json', by_alias=True)]))
    profile_body = dict(schemaVersion='aos.aip.business-investigation-profile/v1', revision=1,
        analysisType=domain_profile.analysis_type, compilerProfile=compiler_profile,
        logicRef=entry_logic.model_dump(mode='json', by_alias=True),
        stageTemplateRef=stage_ref.model_dump(mode='json', by_alias=True),
        orderedSkillRefs=[item.model_dump(mode='json', by_alias=True) for item in ordered],
        skillBindingSetRef=selected.exact_ref.model_dump(mode='json', by_alias=True),
        responsibilityPlanRef=role_ref.model_dump(mode='json', by_alias=True),
        productionContextRef=context_ref.model_dump(mode='json', by_alias=True), stages=stages)
    # Per-Run composition identity includes the configured installation via setRef.
    identity = canonical_sha256(dict(tenant=tenant, runRef=spec['runRef'], profile=profile_body)).removeprefix('sha256:')
    profile_body['profileId'] = 'analysis-compilation-profile-' + identity
    profile = BusinessInvestigationProfileRevision.model_validate(dict(profile_body,
        contentHash=canonical_sha256(profile_body).removeprefix('sha256:')))
    request = CompileBusinessInvestigationRequest(taskId=task['id'], expectedTaskVersion=task['version'],
        caseRef=spec['caseRef'], runRef=spec['runRef'], taskBriefRef=brief_ref, taskBriefSpec=spec, profile=profile)
    payload = dict(schemaVersion='aos.ecommerce.analysis-compilation-binding/v1', tenant=tenant,
        **installation, domainProfile=domain_profile.model_dump(mode='json', by_alias=True),
        request=request.model_dump(mode='json', by_alias=True))
    result = AnalysisCompilationBinding.model_validate(dict(payload, contentHash=canonical_sha256(payload)))
    result.validate_current(scope=scope, installation_id=UUID(installation['installationId']),
        generation=UUID(installation['generation']), execution_epoch=installation['executionEpoch'], case=case, run=run)
    return result
