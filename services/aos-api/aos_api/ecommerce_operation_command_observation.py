"""Read-only, principal-scoped observation of governed Operations commands."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import Field

from aos_api.aip_action_adapters import ActionAdapterRegistry
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_models import ActionExecutionView
from aos_api.aip_action_store import AipActionNotFound, AipActionStore, AipActionStoreError
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.auth import Principal


class OperationCommandObservationError(RuntimeError):
    code = "ECOMMERCE_OPERATION_COMMAND_OBSERVATION_ERROR"


class OperationCommandObservationConflict(OperationCommandObservationError):
    code = "ECOMMERCE_OPERATION_COMMAND_OBSERVATION_CONFLICT"


class OperationCommandObservationUnavailable(OperationCommandObservationError):
    code = "ECOMMERCE_OPERATION_COMMAND_OBSERVATION_UNAVAILABLE"


class OperationCommandObservationEnvelope(AipContractModel):
    schema_version: Literal[
        "aos.ecommerce-workshop.operation-command-observation/v1"
    ] = "aos.ecommerce-workshop.operation-command-observation/v1"
    tenant: TenantContext
    proposal_id: str = Field(min_length=1, max_length=300)
    lease_id: str = Field(min_length=1, max_length=300)
    command_id: Literal[
        "classify", "createCase", "changeMembership", "manageSla", "automationKill"
    ]
    status: Literal["notStarted", "accepted", "applied", "failed", "unknown", "reconciled"]
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_id: str | None = None
    request_fingerprint: str | None = None
    operation_receipt_id: str | None = None
    replay_allowed: Literal[False] = False


class OperationObservationControl(Protocol):
    def get_execution_view(
        self, principal: Principal, proposal_id: str
    ) -> ActionExecutionView: ...


def build_operation_observation_control() -> AipActionExecutionService:
    return AipActionExecutionService(AipActionStore(), ActionAdapterRegistry())


class EcommerceOperationCommandObservationService:
    def __init__(self, *, action_control: OperationObservationControl) -> None:
        self._action_control = action_control

    def read(
        self, principal: Principal, proposal_id: str, lease_id: str
    ) -> OperationCommandObservationEnvelope:
        try:
            view = self._action_control.get_execution_view(principal, proposal_id)
        except AipActionNotFound as exc:
            raise OperationCommandObservationConflict(
                "exact command proposal is unavailable"
            ) from exc
        except AipActionStoreError as exc:
            raise OperationCommandObservationUnavailable(
                "canonical command observation failed closed"
            ) from exc
        if view.lease is None or view.lease.id != lease_id:
            raise OperationCommandObservationConflict(
                "exact command lease is unavailable"
            )
        command_id = view.proposal.payload.get("commandId")
        if command_id not in {
            "classify",
            "createCase",
            "changeMembership",
            "manageSla",
            "automationKill",
        }:
            raise OperationCommandObservationConflict(
                "proposal is not an observable Operations command"
            )
        receipts = [item for item in view.receipts if item.lease_id == lease_id]
        latest = receipts[-1] if receipts else None
        operation_receipt = latest.payload.get("operationReceipt") if latest else None
        return OperationCommandObservationEnvelope(
            tenant=TenantContext(org_id=principal.org_id, project_id=principal.project_id),
            proposal_id=proposal_id,
            lease_id=lease_id,
            command_id=command_id,
            status=(latest.status.value if latest else "notStarted"),
            proposal_hash=view.proposal.proposal_hash,
            receipt_id=(latest.id if latest else None),
            request_fingerprint=(latest.request_fingerprint if latest else None),
            operation_receipt_id=(
                operation_receipt.get("receiptId")
                if isinstance(operation_receipt, dict)
                else None
            ),
        )


__all__ = [
    "EcommerceOperationCommandObservationService",
    "OperationCommandObservationConflict",
    "OperationCommandObservationEnvelope",
    "OperationCommandObservationError",
    "OperationCommandObservationUnavailable",
    "build_operation_observation_control",
]
