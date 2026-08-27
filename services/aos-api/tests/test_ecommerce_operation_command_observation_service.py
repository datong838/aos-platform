from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_action_models import (
    ActionExecutionLeaseSnapshot,
    ActionExecutionView,
    ActionProposalSnapshot,
    ActionReceiptSnapshot,
)
from aos_api.aip_contracts import ActionProposalStatus, ActionReceiptStatus, ActionRiskLevel
from aos_api.auth import Principal
from aos_api.ecommerce_operation_command_observation import (
    EcommerceOperationCommandObservationService,
    OperationCommandObservationConflict,
)


NOW = datetime(2026, 8, 24, tzinfo=UTC)
HASH = "a" * 64


def principal(org_id: str = "org-org") -> Principal:
    return Principal(subject="user:viewer", org_id=org_id, project_id="dev-project", roles=["operator"], markings=["public"])


def view(*, status: ActionReceiptStatus | None) -> ActionExecutionView:
    proposal = ActionProposalSnapshot(
        id="proposal-1",
        action_type={"actionTypeId": "ecommerce.operation.classify", "revisionHash": HASH, "objectType": "OperationEventClassificationDecision"},
        purpose="observe exact command",
        risk_level=ActionRiskLevel.R2,
        payload={"commandId": "classify"},
        proposal_hash=HASH,
        status=ActionProposalStatus.LEASED,
        expires_at=NOW + timedelta(hours=1),
        version=1,
        created_by={"actorType": "user", "actorId": "user:maker"},
        created_at=NOW,
        updated_at=NOW,
    )
    lease = ActionExecutionLeaseSnapshot(id="lease-1", proposal_id="proposal-1", proposal_hash=HASH, attempt=1, expires_at=NOW + timedelta(minutes=10), created_at=NOW)
    receipts = [] if status is None else [ActionReceiptSnapshot(id="receipt-1", proposal_id="proposal-1", lease_id="lease-1", status=status, request_fingerprint=HASH, payload={"commandId": "classify", "operationReceipt": {"receiptId": "op-receipt-1"}}, created_at=NOW)]
    return ActionExecutionView(proposal=proposal, lease=lease, receipts=receipts)


class FakeObservationControl:
    def __init__(self, result: ActionExecutionView) -> None:
        self.result = result
        self.calls = []

    def get_execution_view(self, principal, proposal_id):
        self.calls.append((principal.org_id, principal.project_id, proposal_id))
        return self.result


@pytest.mark.parametrize(
    ("receipt_status", "expected"),
    [(None, "notStarted"), (ActionReceiptStatus.APPLIED, "applied"), (ActionReceiptStatus.FAILED, "failed"), (ActionReceiptStatus.UNKNOWN, "unknown")],
)
def test_observation_maps_exact_lease_without_replay(receipt_status, expected) -> None:
    control = FakeObservationControl(view(status=receipt_status))
    service = EcommerceOperationCommandObservationService(action_control=control)

    result = service.read(principal(), "proposal-1", "lease-1")

    assert result.status == expected
    assert result.tenant.org_id == "org-org"
    assert result.command_id == "classify"
    assert control.calls == [("org-org", "dev-project", "proposal-1")]


def test_observation_rejects_lease_drift() -> None:
    service = EcommerceOperationCommandObservationService(action_control=FakeObservationControl(view(status=None)))
    with pytest.raises(OperationCommandObservationConflict, match="lease"):
        service.read(principal(), "proposal-1", "lease-other")
