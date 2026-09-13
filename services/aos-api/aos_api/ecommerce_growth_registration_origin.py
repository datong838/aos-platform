"""Exact first-registration provenance; never current execution authorization."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_registration_receipt import decode_registration_receipt
from aos_api.tenant_scope import TenantScope


class RegistrationReceiptRef(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True,
                              hide_input_in_errors=True, revalidate_instances="always")
    resourceType: Literal["FirstDispatchRegistrationReceipt"]
    resourceId: str
    revision: StrictInt = Field(ge=1, le=1)
    contentHash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("resourceId")
    @classmethod
    def canonical_uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("canonical registration receipt UUID required")
        return value


def verify_registration_origin(*, row, scope: TenantScope,
    receipt_ref: RegistrationReceiptRef, dispatch_snapshot: list[dict],
    installation_id: str, generation: str, execution_epoch: int,
    binding_revision: int) -> FirstDispatchRegistrationRequest:
    """Match trusted stored history and a locked snapshot; caller checks live authority.

    The returned request retains installation/config refs for same-transaction
    current permission, configuration and release validation by the control Owner.
    This function neither reads a database nor accepts a bypass/activation flag.
    """
    try:
        if type(scope) is not TenantScope or type(receipt_ref) is not RegistrationReceiptRef:
            raise ValueError()
        ref = RegistrationReceiptRef.model_validate(receipt_ref.model_dump())
        if (type(dispatch_snapshot) is not list
                or type(installation_id) is not str or type(generation) is not str
                or type(execution_epoch) is not int or type(binding_revision) is not int
                or execution_epoch < 1 or binding_revision < 1):
            raise ValueError()
        body = decode_registration_receipt(row, scope=scope)
        request = FirstDispatchRegistrationRequest.model_validate(body["request"])
        if (body["receiptId"] != ref.resourceId or body["contentHash"] != ref.contentHash
                or body["installationId"] != installation_id or body["generation"] != generation
                or request.executionEpoch != execution_epoch or request.bindingRevision != binding_revision
                or canonical_sha256(dispatch_snapshot) != canonical_sha256(body["dispatchSnapshot"])):
            raise ValueError()
        return request
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("REGISTRATION_ORIGIN_INVALID") from None
