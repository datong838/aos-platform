import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_action_models import (
    ActionDraftBundle,
    ActionExecutionView,
    ActionProposalSnapshot,
    ActionReceiptSnapshot,
)
from aos_api.aip_contracts import (
    ActionProposalStatus,
    ActionReceiptStatus,
    ActionRiskLevel,
    ApprovalDecision,
    ApprovalEvent,
    DraftSnapshot,
    ExecutionLease,
)
from aos_api.auth import Principal
from aos_api.ecommerce_operation_case_contracts import OperationAuthorityReceipt
from aos_api.ecommerce_operation_command_execution_contracts import (
    ClassifyOperationCommandRequest,
    CreateOperationCaseCommandRequest,
    OperationCommandGovernanceRef,
)
from aos_api.ecommerce_operation_command_service import (
    CanonicalOperationActionControl,
    EcommerceOperationCommandService,
    OperationCommandConflict,
)


NOW = datetime(2026, 8, 24, tzinfo=UTC)
HASH = "a" * 64
PROPOSAL_HASH = "b" * 64
SCOPE = {"orgId": "org-org", "projectId": "dev-project"}


def principal(*, org_id: str = "org-org") -> Principal:
    return Principal(
        subject="user:executor",
        org_id=org_id,
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )


def governance() -> OperationCommandGovernanceRef:
    return OperationCommandGovernanceRef.model_validate(
        {
            "proposalId": "proposal-1",
            "proposalVersion": 2,
            "proposalHash": PROPOSAL_HASH,
            "approvalEventIds": ["approval-1"],
            "leaseId": "lease-1",
        }
    )


def classification_request(*, original_org: str = "org-org") -> ClassifyOperationCommandRequest:
    return ClassifyOperationCommandRequest.model_validate(
        {
            "governance": governance().model_dump(mode="json", by_alias=True),
            "expectedVersion": 0,
            "revision": {
                "tenant": {"orgId": "org-org", "projectId": "dev-project"},
                "decisionId": "classification-1",
                "revision": 1,
                "originalRef": {
                    "tenant": {"orgId": original_org, "projectId": "dev-project"},
                    "resourceType": "Order",
                    "resourceId": "order-1",
                    "contentHash": HASH,
                    "sourceUpdatedAt": NOW,
                },
                "classifierRef": {"resourceId": "classifier-1", "revision": 1, "contentHash": HASH},
                "aggregationPolicyRef": {"resourceId": "policy-1", "revision": 1, "contentHash": HASH},
                "classification": "fulfillment-risk",
                "confidence": 0.9,
                "reason": "exact source evidence",
                "contentHash": HASH,
                "actor": "user:executor",
                "createdAt": NOW,
            },
        }
    )


def create_case_request() -> CreateOperationCaseCommandRequest:
    return CreateOperationCaseCommandRequest.model_validate(
        {
            "governance": governance().model_dump(mode="json", by_alias=True),
            "expectedVersion": 0,
            "revision": {
                "tenant": SCOPE,
                "caseId": "case-1",
                "revision": 1,
                "version": 1,
                "status": "open",
                "aggregationPolicyRef": {"resourceId": "policy-1", "revision": 1, "contentHash": HASH},
                "memberRefs": [],
                "contentHash": HASH,
                "actor": "user:executor",
                "createdAt": NOW,
            },
        }
    )


class FakeActionControl:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, str]] = []
        self.command_payload: dict | None = None
        self.action_type_id = ""
        self.approval_ids = ["approval-1"]
        self.lease_owner = "user:executor"
        self.lease_status = "active"
        self.lease_expires_at = NOW + timedelta(minutes=10)

    def execute_exact_chain(self, **kwargs):
        if kwargs["approval_event_ids"] != self.approval_ids:
            raise OperationCommandConflict("approval refs drifted")
        if kwargs["principal"].subject != self.lease_owner:
            raise OperationCommandConflict("lease owner drifted")
        if self.lease_status != "active" or self.lease_expires_at <= NOW:
            raise OperationCommandConflict("lease is not active")
        if kwargs["canonical_payload"] != self.command_payload:
            raise OperationCommandConflict("proposal payload drifted")
        if kwargs["action_type_id"] != self.action_type_id:
            raise OperationCommandConflict("action type drifted")
        self.execute_calls.append((kwargs["lease_id"], kwargs["proposal_hash"]))
        return {
            "status": "applied",
            "operationReceipt": {
                "tenant": SCOPE,
                "receiptId": "op-receipt-1",
                "operation": "operation-command.execute",
                "idempotencyKey": "command-key",
                "requestHash": HASH,
                "resultRef": {
                    "resourceId": "result-1",
                    "revision": 1,
                    "contentHash": HASH,
                },
                "createdBy": "user:executor",
                "createdAt": NOW,
            },
        }


def service_for(command_id: str, request) -> tuple[EcommerceOperationCommandService, FakeActionControl]:
    control = FakeActionControl()
    control.action_type_id = f"ecommerce.operation.{command_id}"
    control.command_payload = request.canonical_action_payload()
    return EcommerceOperationCommandService(action_control=control, now=lambda: NOW), control


def test_classify_requires_exact_governance_then_executes_canonical_lease() -> None:
    request = classification_request()
    service, control = service_for("classify", request)

    result = service.classify(principal(), "command-key-1", request)

    assert result.command_id == "classify"
    assert result.status == "applied"
    assert result.operation_receipt.receipt_id == "op-receipt-1"
    assert control.execute_calls == [("lease-1", PROPOSAL_HASH)]


def test_create_case_uses_distinct_action_type_and_expected_zero_version() -> None:
    request = create_case_request()
    service, control = service_for("create-case", request)

    result = service.create_case(principal(), "command-key-2", request)

    assert result.command_id == "createCase"
    assert control.execute_calls == [("lease-1", PROPOSAL_HASH)]


def test_cross_tenant_original_is_rejected_before_action_control() -> None:
    request = classification_request(original_org="dev-org")
    service, control = service_for("classify", request)

    with pytest.raises(OperationCommandConflict, match="tenant"):
        service.classify(principal(), "command-key-3", request)

    assert control.execute_calls == []


def test_proposal_payload_drift_is_rejected_without_consuming_lease() -> None:
    request = classification_request()
    service, control = service_for("classify", request)
    control.command_payload = {"commandId": "classify", "revision": {}}

    with pytest.raises(OperationCommandConflict, match="payload"):
        service.classify(principal(), "command-key-4", request)

    assert control.execute_calls == []


def test_body_cannot_inject_tenant_or_actor() -> None:
    payload = classification_request().model_dump(mode="json", by_alias=True)
    payload["orgId"] = "dev-org"
    payload["actorId"] = "user:other"
    with pytest.raises(ValueError):
        ClassifyOperationCommandRequest.model_validate(payload)


class FakeCanonicalActionStore:
    def __init__(self, payload: dict) -> None:
        self.bundle = ActionDraftBundle(
            proposal=ActionProposalSnapshot(
                id="proposal-1",
                action_type={
                    "actionTypeId": "ecommerce.operation.classify",
                    "revisionHash": HASH,
                    "objectType": "OperationEventClassificationDecision",
                },
                purpose="append exact operation classification",
                risk_level=ActionRiskLevel.R2,
                payload=payload,
                proposal_hash=PROPOSAL_HASH,
                status=ActionProposalStatus.LEASED,
                expires_at=NOW + timedelta(hours=1),
                version=2,
                created_by={"actorType": "user", "actorId": "user:maker"},
                created_at=NOW,
                updated_at=NOW,
            ),
            draft=DraftSnapshot(
                id="draft-1",
                proposal_id="proposal-1",
                proposal_version=1,
                proposal_hash=PROPOSAL_HASH,
                status="approved",
                created_at=NOW,
            ),
            approvals=[
                ApprovalEvent(
                    id="approval-1",
                    proposal_id="proposal-1",
                    proposal_version=1,
                    proposal_hash=PROPOSAL_HASH,
                    decision=ApprovalDecision.APPROVED,
                    actor={"actorType": "user", "actorId": "user:checker"},
                    created_at=NOW,
                )
            ],
        )

    def get_proposal(self, scope, proposal_id):
        assert scope.key == ("org-org", "dev-project")
        assert proposal_id == "proposal-1"
        return self.bundle


class FakeCanonicalAuthorityStore:
    def __init__(self) -> None:
        self.appended = []

    def append_classification(self, scope, actor, key, revision):
        self.appended.append((scope.key, actor, key, revision.decision_id))

    def get_receipt(self, scope, *, operation, idempotency_key):
        return OperationAuthorityReceipt(
            tenant=SCOPE,
            receipt_id="op-receipt-1",
            operation=operation,
            idempotency_key=idempotency_key,
            request_hash=HASH,
            result_ref={"resourceId": "classification-1", "revision": 1, "contentHash": HASH},
            created_by="user:executor",
            created_at=NOW,
        )


class FakeCanonicalExecution:
    def __init__(self, store, registry, payload, *, prior_key: str | None = None) -> None:
        self.registry = registry
        self.payload = payload
        self.prior_key = prior_key
        self.execute_count = 0

    def get_execution_view(self, principal, proposal_id):
        return ActionExecutionView(
            proposal=FakeCanonicalActionStore(self.payload).bundle.proposal,
            lease=ExecutionLease(
                id="lease-1",
                proposal_id="proposal-1",
                proposal_hash=PROPOSAL_HASH,
                attempt=1,
                expires_at=NOW + timedelta(minutes=10),
                created_at=NOW,
            ),
            receipts=(
                []
                if self.prior_key is None
                else [
                    ActionReceiptSnapshot(
                        id="action-receipt-prior",
                        proposal_id="proposal-1",
                        lease_id="lease-1",
                        status=ActionReceiptStatus.APPLIED,
                        request_fingerprint=HASH,
                        payload={
                            "commandId": "classify",
                            "commandIdempotencyKeyHash": hashlib.sha256(
                                self.prior_key.encode()
                            ).hexdigest(),
                            "operationReceipt": FakeCanonicalAuthorityStore()
                            .get_receipt(
                                None,
                                operation="operation_classification.append",
                                idempotency_key=self.prior_key,
                            )
                            .model_dump(mode="json", by_alias=True),
                        },
                        created_at=NOW,
                    )
                ]
            ),
        )

    def execute(self, principal, lease_id, expected_hash):
        self.execute_count += 1
        adapter = self.registry.get("ecommerce.operation.classify")
        outcome = adapter.execute(payload=self.payload, idempotency_key="canonical-key")
        return ActionExecutionView(
            proposal=FakeCanonicalActionStore(self.payload).bundle.proposal,
            lease=ExecutionLease(
                id=lease_id,
                proposal_id="proposal-1",
                proposal_hash=expected_hash,
                attempt=1,
                expires_at=NOW + timedelta(minutes=10),
                created_at=NOW,
            ),
            receipts=[
                ActionReceiptSnapshot(
                    id="action-receipt-1",
                    proposal_id="proposal-1",
                    lease_id=lease_id,
                    status=ActionReceiptStatus.APPLIED,
                    request_fingerprint=HASH,
                    payload=outcome.payload,
                    created_at=NOW,
                )
            ],
        )


def test_canonical_control_consumes_existing_action_chain_and_embeds_operation_receipt() -> None:
    request = classification_request()
    action_store = FakeCanonicalActionStore(request.canonical_action_payload())
    authority_store = FakeCanonicalAuthorityStore()
    control = CanonicalOperationActionControl(
        action_store=action_store,  # type: ignore[arg-type]
        authority_store=authority_store,  # type: ignore[arg-type]
        execution_factory=lambda store, registry: FakeCanonicalExecution(
            store, registry, request.canonical_action_payload()
        ),
    )
    service = EcommerceOperationCommandService(action_control=control, now=lambda: NOW)

    result = service.classify(principal(), "command-key-5", request)

    assert result.operation_receipt.receipt_id == "op-receipt-1"
    assert authority_store.appended == [
        (("org-org", "dev-project"), "user:executor", "command-key-5", "classification-1")
    ]


def test_canonical_control_replays_same_command_key_and_rejects_key_drift() -> None:
    request = classification_request()
    action_store = FakeCanonicalActionStore(request.canonical_action_payload())
    execution = None

    def execution_factory(store, registry):
        nonlocal execution
        execution = FakeCanonicalExecution(
            store,
            registry,
            request.canonical_action_payload(),
            prior_key="command-key-6",
        )
        return execution

    control = CanonicalOperationActionControl(
        action_store=action_store,  # type: ignore[arg-type]
        authority_store=FakeCanonicalAuthorityStore(),  # type: ignore[arg-type]
        execution_factory=execution_factory,
    )
    service = EcommerceOperationCommandService(action_control=control, now=lambda: NOW)

    replay = service.classify(principal(), "command-key-6", request)
    assert replay.operation_receipt.receipt_id == "op-receipt-1"
    assert execution.execute_count == 0

    with pytest.raises(OperationCommandConflict, match="idempotency"):
        service.classify(principal(), "different-key", request)
