"""Strict request/response contracts for governed W3-12B internal commands."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_operation_case_contracts import (
    CaseMembershipDecisionRevision,
    OperationAuthorityReceipt,
    OperationCaseRevision,
    OperationEventClassificationDecisionRevision,
    SlaClockDecision,
)


class OperationCommandGovernanceRef(AipContractModel):
    proposal_id: str = Field(min_length=1, max_length=300)
    proposal_version: int = Field(ge=1)
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_event_ids: list[str] = Field(min_length=1, max_length=20)
    lease_id: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def _unique_approvals(self) -> "OperationCommandGovernanceRef":
        if len(self.approval_event_ids) != len(set(self.approval_event_ids)):
            raise ValueError("approvalEventIds must be unique exact refs")
        return self


class _InternalOperationCommandRequest(AipContractModel):
    governance: OperationCommandGovernanceRef
    expected_version: int = Field(ge=0)

    def canonical_action_payload(self) -> dict[str, Any]:
        raise NotImplementedError


class ClassifyOperationCommandRequest(_InternalOperationCommandRequest):
    revision: OperationEventClassificationDecisionRevision

    @model_validator(mode="after")
    def _append_once(self) -> "ClassifyOperationCommandRequest":
        if self.revision.revision != self.expected_version + 1:
            raise ValueError("classification revision must advance expectedVersion once")
        return self

    def canonical_action_payload(self) -> dict[str, Any]:
        return {
            "commandId": "classify",
            "expectedVersion": self.expected_version,
            "revision": self.revision.model_dump(mode="json", by_alias=True),
        }


class CreateOperationCaseCommandRequest(_InternalOperationCommandRequest):
    revision: OperationCaseRevision

    @model_validator(mode="after")
    def _new_case(self) -> "CreateOperationCaseCommandRequest":
        if self.expected_version != 0:
            raise ValueError("new operation case expectedVersion must be zero")
        if self.revision.revision != 1 or self.revision.version != 1:
            raise ValueError("new operation case must start at revision/version one")
        return self

    def canonical_action_payload(self) -> dict[str, Any]:
        return {
            "commandId": "createCase",
            "expectedVersion": self.expected_version,
            "revision": self.revision.model_dump(mode="json", by_alias=True),
        }


class ChangeOperationMembershipCommandRequest(_InternalOperationCommandRequest):
    revision: CaseMembershipDecisionRevision

    @model_validator(mode="after")
    def _append_once(self) -> "ChangeOperationMembershipCommandRequest":
        if self.revision.revision != self.expected_version + 1:
            raise ValueError("membership revision must advance expectedVersion once")
        return self

    def canonical_action_payload(self) -> dict[str, Any]:
        return {
            "commandId": "changeMembership",
            "expectedVersion": self.expected_version,
            "revision": self.revision.model_dump(mode="json", by_alias=True),
        }


class ManageOperationSlaCommandRequest(_InternalOperationCommandRequest):
    revision: SlaClockDecision

    @model_validator(mode="after")
    def _append_once(self) -> "ManageOperationSlaCommandRequest":
        if self.revision.revision != self.expected_version + 1:
            raise ValueError("SLA clock revision must advance expectedVersion once")
        return self

    def canonical_action_payload(self) -> dict[str, Any]:
        return {
            "commandId": "manageSla",
            "expectedVersion": self.expected_version,
            "revision": self.revision.model_dump(mode="json", by_alias=True),
        }


class OperationCommandExecutionEnvelope(AipContractModel):
    schema_version: Literal[
        "aos.ecommerce-workshop.operation-command-execution/v1"
    ] = "aos.ecommerce-workshop.operation-command-execution/v1"
    tenant: TenantContext
    command_id: Literal["classify", "createCase", "changeMembership", "manageSla"]
    status: Literal["applied"]
    proposal_id: str
    lease_id: str
    operation_receipt: OperationAuthorityReceipt


__all__ = [
    "ChangeOperationMembershipCommandRequest",
    "ClassifyOperationCommandRequest",
    "CreateOperationCaseCommandRequest",
    "ManageOperationSlaCommandRequest",
    "OperationCommandExecutionEnvelope",
    "OperationCommandGovernanceRef",
]
