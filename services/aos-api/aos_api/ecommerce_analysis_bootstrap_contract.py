"""Fixed paused-runtime bootstrap intent; parsing never grants authorization."""
from typing import Literal
from pydantic import Field, field_validator, model_validator
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompilationReceipt
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analysis_compilation_binding import AnalysisCompilationBinding


class AnalysisBootstrapIntent(AipContractModel):
    schema_version: Literal['aos.ecommerce.analysis-bootstrap-intent/v1']
    operation: Literal['ecommerce_analysis_bootstrap']
    mode: Literal['paused-before-first-step']
    business_execution_authorized: Literal[False]
    external_effect_authorized: Literal[False]
    tenant: TenantContext
    occurrence_ref: InvestigationExactRef
    source_control_receipt_ref: InvestigationExactRef
    compilation_binding: AnalysisCompilationBinding
    compilation_receipt: BusinessInvestigationCompilationReceipt
    content_hash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')

    @field_validator('business_execution_authorized', 'external_effect_authorized', mode='before')
    @classmethod
    def strictly_false(cls, value):
        if value is not False:
            raise ValueError('bootstrap cannot authorize business or external execution')
        return value

    @model_validator(mode='after')
    def exact_compilation(self):
        if canonical_sha256(self.model_dump(mode='json', by_alias=True, exclude={'content_hash'})) != self.content_hash:
            raise ValueError('bootstrap intent hash differs')
        binding = AnalysisCompilationBinding.model_validate(self.compilation_binding.model_dump(mode='json', by_alias=True))
        receipt, request = self.compilation_receipt, binding.request
        if (self.tenant != binding.tenant or self.tenant != receipt.tenant
                or self.occurrence_ref.resource_type != 'AutomationOccurrence'
                or self.source_control_receipt_ref.resource_type != 'EventPolicyControlReceipt'):
            raise ValueError('bootstrap tenant or source reference kind differs')
        run = receipt.run_ref
        if (run.resource_type, run.resource_id, run.revision, run.content_hash.removeprefix('sha256:')) != (
                request.run_ref.resource_type, request.run_ref.resource_id, request.run_ref.revision, request.run_ref.content_hash):
            raise ValueError('bootstrap compilation Run differs')
        if (receipt.task_id != request.task_id or receipt.profile_ref != request.profile.exact_ref
                or receipt.logic_ref != request.profile.logic_ref
                or receipt.skill_binding_set_ref != request.profile.skill_binding_set_ref
                or receipt.responsibility_plan_ref != request.profile.responsibility_plan_ref):
            raise ValueError('bootstrap compilation inputs differ')
        material = dict(commandId=receipt.command_id, runRef=run.model_dump(mode='json', by_alias=True),
                        compileRequest=request.model_dump(mode='json', by_alias=True))
        if canonical_sha256(material) != receipt.request_hash:
            raise ValueError('bootstrap compilation Receipt request hash differs')
        return self

    def checked(self):
        """Reparse nested mutable models before using the intent as an input."""
        return type(self).model_validate(self.model_dump(mode='json', by_alias=True))
