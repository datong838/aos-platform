import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_action_models import (
    ActionApprovalEventSnapshot,
    ActionDraftBundle,
    ActionExecutionLeaseSnapshot,
    ActionExecutionView,
    ActionProposalSnapshot,
    ActionReceiptSnapshot,
)
from aos_api.aip_contracts import (
    ActionProposalStatus,
    ActionReceiptStatus,
    ActionRiskLevel,
    ApprovalDecision,
    DraftSnapshot,
)
from aos_api.auth import Principal
from aos_api.ecommerce_operation_case_contracts import OperationAuthorityReceipt
from aos_api.ecommerce_operation_command_execution_contracts import (
    ChangeOperationMembershipCommandRequest,
    ClassifyOperationCommandRequest,
    CreateOperationCaseCommandRequest,
    KillOperationAutomationCommandRequest,
    ManageOperationSlaCommandRequest,
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


def membership_request() -> ChangeOperationMembershipCommandRequest:
    return ChangeOperationMembershipCommandRequest.model_validate(
        {
            "governance": governance().model_dump(mode="json", by_alias=True),
            "expectedVersion": 0,
            "revision": {
                "tenant": SCOPE,
                "decisionId": "membership-1",
                "revision": 1,
                "decisionType": "attach",
                "predecessorCaseRefs": [],
                "successorCaseRefs": [],
                "movedOriginals": [
                    {
                        "tenant": SCOPE,
                        "resourceType": "Order",
                        "resourceId": "order-1",
                        "contentHash": HASH,
                        "sourceUpdatedAt": NOW,
                    }
                ],
                "beforeTotal": 1,
                "afterTotal": 1,
                "unmatchedCount": 0,
                "conflictedCount": 0,
                "reason": "attach exact original",
                "contentHash": HASH,
                "actor": "user:executor",
                "createdAt": NOW,
            },
        }
    )


def sla_request() -> ManageOperationSlaCommandRequest:
    return ManageOperationSlaCommandRequest.model_validate(
        {
            "governance": governance().model_dump(mode="json", by_alias=True),
            "expectedVersion": 0,
            "revision": {
                "tenant": SCOPE,
                "decisionId": "sla-clock-1",
                "revision": 1,
                "caseRef": {"resourceId": "case-1", "revision": 1, "contentHash": HASH},
                "policyRef": {"resourceId": "sla-policy-1", "revision": 1, "contentHash": HASH},
                "operation": "start",
                "sourceEventTime": NOW,
                "reason": "start exact SLA clock",
                "contentHash": HASH,
                "actor": "user:executor",
                "createdAt": NOW,
            },
        }
    )


def kill_request() -> KillOperationAutomationCommandRequest:
    return KillOperationAutomationCommandRequest.model_validate(
        {
            "governance": governance().model_dump(mode="json", by_alias=True),
            "expectedVersion": 0,
            "revision": {
                "tenant": SCOPE,
                "decisionId": "kill-1",
                "revision": 1,
                "state": "active",
                "scopeHash": HASH,
                "checkpoints": ["proposal", "lease", "executor"],
                "reason": "bounded automation stop",
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


@pytest.mark.parametrize(
    ("command_id", "request_factory", "service_method", "expected_command"),
    [
        ("change-membership", membership_request, "change_membership", "changeMembership"),
        ("manage-sla", sla_request, "manage_sla", "manageSla"),
    ],
)
def test_membership_and_sla_reuse_exact_governance_chain(
    command_id, request_factory, service_method, expected_command
) -> None:
    request = request_factory()
    service, control = service_for(command_id, request)

    result = getattr(service, service_method)(principal(), "command-key-b2b", request)

    assert result.command_id == expected_command
    assert control.execute_calls == [("lease-1", PROPOSAL_HASH)]


def test_membership_rejects_cross_tenant_original_before_action_control() -> None:
    payload = membership_request().model_dump(mode="json", by_alias=True)
    payload["revision"]["movedOriginals"][0]["tenant"]["orgId"] = "dev-org"
    request = ChangeOperationMembershipCommandRequest.model_validate(payload)
    service, control = service_for("change-membership", request)

    with pytest.raises(OperationCommandConflict, match="tenant"):
        service.change_membership(principal(), "command-key-b2b-tenant", request)

    assert control.execute_calls == []


def test_automation_kill_reuses_exact_governance_chain() -> None:
    request = kill_request()
    service, control = service_for("automation-kill", request)

    result = service.automation_kill(principal(), "command-key-kill", request)

    assert result.command_id == "automationKill"
    assert control.execute_calls == [("lease-1", PROPOSAL_HASH)]


def test_automation_kill_requires_all_unique_checkpoints() -> None:
    payload = kill_request().model_dump(mode="json", by_alias=True)
    payload["revision"]["checkpoints"] = ["proposal", "lease"]

    with pytest.raises(ValueError, match="proposal, lease and executor"):
        KillOperationAutomationCommandRequest.model_validate(payload)


@pytest.mark.parametrize(
    ("request_factory", "request_type"),
    [
        (membership_request, ChangeOperationMembershipCommandRequest),
        (sla_request, ManageOperationSlaCommandRequest),
    ],
)
def test_membership_and_sla_require_exact_next_revision(
    request_factory, request_type
) -> None:
    payload = request_factory().model_dump(mode="json", by_alias=True)
    payload["expectedVersion"] = 1

    with pytest.raises(ValueError, match="advance expectedVersion once"):
        request_type.model_validate(payload)


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
    def __init__(
        self, payload: dict, action_type_id: str = "ecommerce.operation.classify"
    ) -> None:
        self.bundle = ActionDraftBundle(
            proposal=ActionProposalSnapshot(
                id="proposal-1",
                action_type={
                    "actionTypeId": action_type_id,
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
                ActionApprovalEventSnapshot(
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
        self.appended.append(("classify", scope.key, actor, key, revision.decision_id))

    def append_membership(self, scope, actor, key, revision):
        self.appended.append(("membership", scope.key, actor, key, revision.decision_id))

    def append_sla_clock(self, scope, actor, key, revision):
        self.appended.append(("sla", scope.key, actor, key, revision.decision_id))

    def append_kill(self, scope, actor, key, revision):
        self.appended.append(("kill", scope.key, actor, key, revision.decision_id))

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
    def __init__(
        self,
        store,
        registry,
        payload,
        *,
        action_type_id: str = "ecommerce.operation.classify",
        prior_key: str | None = None,
    ) -> None:
        self.registry = registry
        self.payload = payload
        self.prior_key = prior_key
        self.action_type_id = action_type_id
        self.execute_count = 0

    def get_execution_view(self, principal, proposal_id):
        return ActionExecutionView(
            proposal=FakeCanonicalActionStore(
                self.payload, self.action_type_id
            ).bundle.proposal,
            lease=ActionExecutionLeaseSnapshot(
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
        adapter = self.registry.get(self.action_type_id)
        outcome = adapter.execute(payload=self.payload, idempotency_key="canonical-key")
        return ActionExecutionView(
            proposal=FakeCanonicalActionStore(
                self.payload, self.action_type_id
            ).bundle.proposal,
            lease=ActionExecutionLeaseSnapshot(
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
        ("classify", ("org-org", "dev-project"), "user:executor", "command-key-5", "classification-1")
    ]


@pytest.mark.parametrize(
    ("request_factory", "action_type_id", "service_method", "append_kind"),
    [
        (
            membership_request,
            "ecommerce.operation.change-membership",
            "change_membership",
            "membership",
        ),
        (sla_request, "ecommerce.operation.manage-sla", "manage_sla", "sla"),
        (
            kill_request,
            "ecommerce.operation.automation-kill",
            "automation_kill",
            "kill",
        ),
    ],
)
def test_membership_and_sla_canonical_adapters_embed_exact_operation_receipt(
    request_factory, action_type_id, service_method, append_kind
) -> None:
    request = request_factory()
    action_store = FakeCanonicalActionStore(
        request.canonical_action_payload(), action_type_id
    )
    authority_store = FakeCanonicalAuthorityStore()
    control = CanonicalOperationActionControl(
        action_store=action_store,  # type: ignore[arg-type]
        authority_store=authority_store,  # type: ignore[arg-type]
        execution_factory=lambda store, registry: FakeCanonicalExecution(
            store,
            registry,
            request.canonical_action_payload(),
            action_type_id=action_type_id,
        ),
    )
    service = EcommerceOperationCommandService(action_control=control, now=lambda: NOW)

    result = getattr(service, service_method)(
        principal(), "command-key-b2b-canonical", request
    )

    assert result.operation_receipt.receipt_id == "op-receipt-1"
    assert authority_store.appended[0][0] == append_kind


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
