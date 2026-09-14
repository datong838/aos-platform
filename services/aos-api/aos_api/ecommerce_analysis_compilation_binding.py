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
