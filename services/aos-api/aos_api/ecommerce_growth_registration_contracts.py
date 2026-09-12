"""First registration request and detached preview; no execution authority."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.asset_registry.errors import IdempotencyKeyRequiredError
from aos_api.extension_runtime.configuration_contracts import ConfigurationRef


class FirstDispatchRegistrationRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
                              hide_input_in_errors=True, revalidate_instances='always')
    schemaVersion: Literal['aos.ecommerce.first-dispatch-registration/v1']
    installationRef: CurrentInstallationRef
    generation: str
    bindingRevision: int = Field(ge=1, le=2**63-1)
    executionEpoch: int = Field(ge=1, le=2**63-1)
    configRef: ConfigurationRef
    groupId: str
    idempotencyKey: str

    @field_validator('generation', 'groupId')
    @classmethod
    def canonical_uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical registration UUID required')
        return value

    @field_validator('idempotencyKey')
    @classmethod
    def canonical_key(cls, value):
        try:
            return validate_idempotency_key(value)
        except IdempotencyKeyRequiredError:
            raise ValueError('canonical registration idempotency key required') from None

    def request_hash(self) -> str:
        validated = type(self).model_validate(self.model_dump(mode='python', by_alias=True))
        return canonical_sha256(validated.model_dump(mode='json', by_alias=True))


def preview_registration(request: FirstDispatchRegistrationRequest) -> dict:
    """Proposed metadata only; the Owner must revalidate live authority separately."""
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    if type(request) is not FirstDispatchRegistrationRequest:
        raise TypeError('validated first registration request required')
    request = FirstDispatchRegistrationRequest.model_validate(
        request.model_dump(mode='python', by_alias=True))
    return dict(
        schemaVersion='aos.ecommerce.first-dispatch-registration-preview/v1',
        executable=False, authorityValidated=False, requestHash=request.request_hash(),
        request=request.model_dump(mode='json', by_alias=True),
        proposedDispatchSnapshot=[dict(
            operationId=operation, handlerKind='legacy', installationId=None,
            generation=None, executionEpoch=None, operationFence=True, revision=1,
            cutoverGroupId=request.groupId, cutoverGroupRevision=1,
        ) for operation in sorted(ECOMMERCE_GROWTH_OPERATIONS)],
    )
