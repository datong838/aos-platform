"""Pristine registration withdrawal contract; no write or execution authority."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef, verify_registration_origin
from aos_api.ecommerce_growth_registration_receipt import decode_registration_receipt
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.tenant_scope import TenantScope


class RegistrationWithdrawalRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True,
                              hide_input_in_errors=True, revalidate_instances='always')
    schemaVersion: Literal['aos.ecommerce.first-dispatch-withdrawal/v1'] = 'aos.ecommerce.first-dispatch-withdrawal/v1'
    registrationReceiptRef: RegistrationReceiptRef
    expectedInstallationEtag: StrictInt = Field(ge=1, le=9223372036854775807)
    idempotencyKey: str = Field(min_length=1, max_length=160)

    @field_validator('idempotencyKey')
    @classmethod
    def canonical_key(cls, value):
        if value.strip() != value or not value.isprintable():
            raise ValueError('canonical withdrawal key required')
        return validate_idempotency_key(value)

    def request_hash(self):
        return canonical_sha256(self.model_dump(mode='json'))


def require_pristine_withdrawal(*, row, scope: TenantScope,
        request: RegistrationWithdrawalRequest, dispatch_snapshot: list[dict],
        cutover_count: int, dependency_count: int) -> FirstDispatchRegistrationRequest:
    """Validate trusted locked history, not caller-provided authority.

    The future control Owner must load these rows in one scoped transaction,
    check current actor permission and installation CAS, and commit a withdrawal
    Receipt atomically with removing only unused current occupancy. No current
    runtime readiness or budget is inferred from this historical request.
    """
    if type(request) is not RegistrationWithdrawalRequest:
        raise TypeError('strict registration withdrawal request required')
    request = RegistrationWithdrawalRequest.model_validate(request.model_dump())
    if (type(cutover_count) is not int or cutover_count != 0
            or type(dependency_count) is not int or dependency_count != 0):
        raise ValueError('REGISTRATION_WITHDRAWAL_REQUIRES_UNUSED_ORIGIN')
    body = decode_registration_receipt(row, scope=scope)
    origin = body['request']
    return verify_registration_origin(row=row, scope=scope,
        receipt_ref=request.registrationReceiptRef, dispatch_snapshot=dispatch_snapshot,
        installation_id=body['installationId'], generation=body['generation'],
        execution_epoch=origin['executionEpoch'], binding_revision=origin['bindingRevision'])
