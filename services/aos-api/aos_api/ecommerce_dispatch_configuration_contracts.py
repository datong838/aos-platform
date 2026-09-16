"""Exact configuration continuation inputs; parsing grants no runtime authority."""
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.extension_runtime.configuration_contracts import ConfigurationRef
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef, PipelineInstallationRef
from aos_api.tenant_scope import TenantScope

_MAX = 2**63-1


class DispatchConfigurationRefreshRequest(AipContractModel):
    """An Owner must independently resolve every ref and operation under locks."""
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid',
                              revalidate_instances='always', hide_input_in_errors=True)
    schema_version: Literal['aos.ecommerce.dispatch-configuration-refresh/v1'] = 'aos.ecommerce.dispatch-configuration-refresh/v1'
    org_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    installation_ref: PipelineInstallationRef
    generation: str
    cutover_group_id: str
    expected_group_revision: int = Field(ge=1, le=_MAX)
    source_authority_ref: PipelineExactRef
    source_runtime_revision: int = Field(ge=1, le=_MAX)
    source_execution_epoch: int = Field(ge=1, le=_MAX)
    source_configuration_ref: ConfigurationRef
    target_runtime_revision: int = Field(ge=1, le=_MAX)
    target_execution_epoch: int = Field(ge=1, le=_MAX)
    target_configuration_ref: ConfigurationRef
    configure_operation_id: str
    configure_operation_revision: int = Field(ge=1, le=_MAX)
    enable_operation_id: str
    enable_operation_revision: int = Field(ge=1, le=_MAX)
    operation_ids: tuple[str, ...]
    approval_ref: PipelineExactRef
    idempotency_key: str = Field(min_length=1, max_length=160)
    external_effects_allowed: Literal[False] = False
    resume_business_runs: Literal[False] = False

    @field_validator('generation', 'cutover_group_id', 'configure_operation_id', 'enable_operation_id')
    @classmethod
    def canonical_uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical identity required')
        return value

    @field_validator('org_id', 'project_id', 'idempotency_key')
    @classmethod
    def canonical_text(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError('canonical scope and key required')
        return value

    @field_validator('external_effects_allowed', 'resume_business_runs', mode='before')
    @classmethod
    def no_implicit_effect(cls, value):
        if value is not False:
            raise ValueError('configuration refresh cannot authorize business effects')
        return value

    @model_validator(mode='after')
    def exact_transition(self):
        TenantScope(self.org_id, self.project_id)
        validate_idempotency_key(self.idempotency_key)
        if self.operation_ids != tuple(sorted(ECOMMERCE_GROWTH_OPERATIONS)):
            raise ValueError('complete ordered operation set required')
        source, target = self.source_configuration_ref, self.target_configuration_ref
        if source.configurationId != target.configurationId or target.revision <= source.revision:
            raise ValueError('same configuration family successor required')
        if self.target_runtime_revision <= self.source_runtime_revision or self.target_execution_epoch <= self.source_execution_epoch:
            raise ValueError('new runtime revision and epoch required')
        if self.configure_operation_id == self.enable_operation_id:
            raise ValueError('distinct configure and enable operations required')
        if self.source_authority_ref.resource_type not in {'CutoverResumeReceipt', 'DispatchConfigurationRefreshReceipt'}:
            raise ValueError('exact previous dispatch authority required')
        if str(UUID(self.source_authority_ref.resource_id)) != self.source_authority_ref.resource_id:
            raise ValueError('canonical previous receipt identity required')
        if type(self.source_authority_ref.revision) is not int:
            raise ValueError('integer previous receipt revision required')
        if self.approval_ref.resource_type != 'ActionApprovalEvent':
            raise ValueError('exact action approval required')
        hashes = (source.hash, target.hash, self.installation_ref.lock_hash,
                  self.source_authority_ref.content_hash, self.approval_ref.content_hash)
        if any(value == 'sha256:'+'0'*64 for value in hashes):
            raise ValueError('placeholder authority hash forbidden')
        return self

    def wire(self):
        return self.model_dump(mode='json', by_alias=True, exclude_none=True)

    def request_hash(self):
        return canonical_sha256(self.wire())

    def approval_intent(self):
        return self.model_dump(mode='json', by_alias=True, exclude_none=True, exclude={'approval_ref'})
