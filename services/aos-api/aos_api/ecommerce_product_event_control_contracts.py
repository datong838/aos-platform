"""Event control intent only. Parsing never authorizes a binding mutation."""
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef


class ProductEventControlCommand(AipContractModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid',
                              revalidate_instances='always', hide_input_in_errors=True)
    schema_version: Literal['aos.ecommerce.product-event-control-command/v1']
    idempotency_key: str = Field(min_length=1, max_length=200)
    policy_ref: PipelineExactRef
    expected_binding_revision: int = Field(ge=0, le=2**63-1)
    intent: Literal['enable', 'disable']
    approval_ref: PipelineExactRef | None

    @field_validator('idempotency_key')
    @classmethod
    def canonical_key(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError('canonical event control key required')
        return value

    @model_validator(mode='after')
    def exact_purpose(self):
        if self.policy_ref.resource_type != 'SchedulePolicyRevision':
            raise ValueError('exact schedule policy required')
        if self.approval_ref is not None and self.approval_ref.resource_type != 'ActionApprovalEvent':
            raise ValueError('exact event control approval required')
        if self.intent == 'enable' and self.approval_ref is None:
            raise ValueError('enable intent requires an approval reference')
        return self
