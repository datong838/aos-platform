"""Governed execution facade for internal Operations authority commands."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from aos_api.aip_action_adapters import ActionAdapterRegistry, AdapterOutcome
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_store import (
    AipActionStore,
    AipActionConflict,
    AipActionIdempotencyConflict,
    AipActionNotFound,
    AipActionStoreError,
    AipActionTransitionBlocked,
)
from aos_api.aip_contracts import ApprovalDecision, TenantContext
from aos_api.auth import Principal
from aos_api.ecommerce_operation_case_contracts import (
    AutomationKillDecisionRevision,
    CaseMembershipDecisionRevision,
    OperationAuthorityReceipt,
    OperationCaseRevision,
    OperationEventClassificationDecisionRevision,
    SlaClockDecision,
)
from aos_api.ecommerce_operation_case_store import (
    OperationAuthorityStore,
    OperationAuthorityStoreError,
)
from aos_api.ecommerce_operation_command_execution_contracts import (
    ChangeOperationMembershipCommandRequest,
    ClassifyOperationCommandRequest,
    CreateOperationCaseCommandRequest,
    KillOperationAutomationCommandRequest,
    ManageOperationSlaCommandRequest,
    OperationCommandExecutionEnvelope,
)
from aos_api.tenant_scope import TenantScope


class OperationCommandError(RuntimeError):
    code = "ECOMMERCE_OPERATION_COMMAND_ERROR"


class OperationCommandConflict(OperationCommandError):
    code = "ECOMMERCE_OPERATION_COMMAND_CONFLICT"


class OperationCommandDependencyUnavailable(OperationCommandError):
    code = "ECOMMERCE_OPERATION_COMMAND_DEPENDENCY_UNAVAILABLE"


class OperationActionControl(Protocol):
    def execute_exact_chain(self, **kwargs: Any) -> dict[str, Any]: ...


class _InternalOperationAdapter:
    def __init__(
        self,
        *,
        scope: Any,
        actor: str,
        command_id: str,
        command_idempotency_key: str,
        expected_payload: dict[str, Any],
        authority_store: OperationAuthorityStore,
    ) -> None:
        self._scope = scope
        self._actor = actor
        self._command_id = command_id
        self._key = command_idempotency_key
        self._expected_payload = expected_payload
        self._authority_store = authority_store

    def execute(self, *, payload: dict[str, Any], idempotency_key: str) -> AdapterOutcome:
        del idempotency_key
        if payload != self._expected_payload:
            return AdapterOutcome(
                "failed",
                payload={
                    "errorCode": "ECOMMERCE_OPERATION_COMMAND_PAYLOAD_DRIFT",
                    "commandIdempotencyKeyHash": _key_hash(self._key),
                },
            )
        try:
            revision_payload = payload["revision"]
            if self._command_id == "classify":
                revision = OperationEventClassificationDecisionRevision.model_validate(
                    revision_payload
                )
                self._authority_store.append_classification(
                    self._scope, self._actor, self._key, revision
                )
                operation = "operation_classification.append"
            elif self._command_id == "createCase":
                revision = OperationCaseRevision.model_validate(revision_payload)
                self._authority_store.create_case(
                    self._scope, self._actor, self._key, revision
                )
                operation = "operation_case.create"
            elif self._command_id == "changeMembership":
                revision = CaseMembershipDecisionRevision.model_validate(
                    revision_payload
                )
                self._authority_store.append_membership(
                    self._scope, self._actor, self._key, revision
                )
                operation = "operation_membership.append"
            elif self._command_id == "manageSla":
                revision = SlaClockDecision.model_validate(revision_payload)
                self._authority_store.append_sla_clock(
                    self._scope, self._actor, self._key, revision
                )
                operation = "operation_sla_clock.append"
            elif self._command_id == "automationKill":
                revision = AutomationKillDecisionRevision.model_validate(
                    revision_payload
                )
                self._authority_store.append_kill(
                    self._scope, self._actor, self._key, revision
                )
                operation = "operation_kill.append"
            else:
                return AdapterOutcome(
                    "failed", payload={"errorCode": "ECOMMERCE_OPERATION_COMMAND_UNKNOWN"}
                )
            receipt = self._authority_store.get_receipt(
                self._scope,
                operation=operation,
                idempotency_key=self._key,
            )
            return AdapterOutcome(
                "applied",
                payload={
                    "commandId": self._command_id,
                    "commandIdempotencyKeyHash": _key_hash(self._key),
                    "operationReceipt": receipt.model_dump(
                        mode="json", by_alias=True
                    ),
                },
            )
        except OperationAuthorityStoreError as exc:
            return AdapterOutcome(
                "failed",
                payload={
                    "errorCode": exc.code,
                    "commandIdempotencyKeyHash": _key_hash(self._key),
                },
            )
        except Exception as exc:
            return AdapterOutcome(
                "unknown",
                payload={
                    "errorType": type(exc).__name__,
                    "commandIdempotencyKeyHash": _key_hash(self._key),
                },
            )

    def reconcile(self, *, provider_request_id: str, request_fingerprint: str) -> AdapterOutcome:
        del provider_request_id, request_fingerprint
        return AdapterOutcome(
            "failed",
            payload={"errorCode": "ECOMMERCE_OPERATION_COMMAND_RECONCILE_NOT_ALLOWED"},
        )


def _key_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class CanonicalOperationActionControl:
    """Bind internal authority mutation to the existing canonical AIP Action chain."""

    def __init__(
        self,
        *,
        action_store: AipActionStore | None = None,
        authority_store: OperationAuthorityStore | None = None,
        execution_factory: Callable[[AipActionStore, ActionAdapterRegistry], AipActionExecutionService]
        | None = None,
    ) -> None:
        self._action_store = action_store or AipActionStore()
        self._authority_store = authority_store or OperationAuthorityStore()
        self._execution_factory = execution_factory or AipActionExecutionService

    def execute_exact_chain(self, **kwargs: Any) -> dict[str, Any]:
        principal: Principal = kwargs["principal"]
        scope = TenantScope(principal.org_id, principal.project_id)
        proposal_id = kwargs["proposal_id"]
        proposal_hash = kwargs["proposal_hash"]
        lease_id = kwargs["lease_id"]
        expected_payload = kwargs["canonical_payload"]
        expected_action_type = kwargs["action_type_id"]
        expected_approvals = set(kwargs["approval_event_ids"])
        evaluated_at: datetime = kwargs["evaluated_at"]

        try:
            bundle = self._action_store.get_proposal(scope, proposal_id)
        except AipActionNotFound as exc:
            raise OperationCommandConflict("exact Action Proposal is unavailable") from exc
        except AipActionStoreError as exc:
            raise OperationCommandDependencyUnavailable(
                "canonical Action Proposal read failed closed"
            ) from exc
        if bundle.proposal.proposal_hash != proposal_hash:
            raise OperationCommandConflict("proposal hash drifted")
        if bundle.proposal.payload != expected_payload:
            raise OperationCommandConflict("proposal payload drifted")
        if bundle.proposal.action_type.action_type_id != expected_action_type:
            raise OperationCommandConflict("proposal Action Type drifted")

        registry = ActionAdapterRegistry()
        registry.register(
            expected_action_type,
            _InternalOperationAdapter(
                scope=scope,
                actor=principal.subject,
                command_id=kwargs["command_id"],
                command_idempotency_key=kwargs["command_idempotency_key"],
                expected_payload=expected_payload,
                authority_store=self._authority_store,
            ),
        )
        execution = self._execution_factory(self._action_store, registry)
        try:
            view = execution.get_execution_view(principal, proposal_id)
        except AipActionNotFound as exc:
            raise OperationCommandConflict(
                "exact ExecutionLease is unavailable"
            ) from exc
        except AipActionStoreError as exc:
            raise OperationCommandDependencyUnavailable(
                "canonical ExecutionLease read failed closed"
            ) from exc
        if view.lease is None or view.lease.id != lease_id:
            raise OperationCommandConflict("exact ExecutionLease is unavailable")
        if view.lease.proposal_hash != proposal_hash:
            raise OperationCommandConflict("ExecutionLease proposal hash drifted")
        prior = [item for item in view.receipts if item.lease_id == lease_id]
        if prior:
            receipt = prior[-1]
            if receipt.payload.get("commandIdempotencyKeyHash") != _key_hash(
                kwargs["command_idempotency_key"]
            ):
                raise OperationCommandConflict("command idempotency key drifted")
            return {"status": receipt.status.value, **receipt.payload}

        if bundle.proposal.version != kwargs["proposal_version"]:
            raise OperationCommandConflict("proposal version drifted")
        if bundle.proposal.expires_at <= evaluated_at:
            raise OperationCommandConflict("proposal expired before command execution")
        if view.lease.expires_at <= evaluated_at:
            raise OperationCommandConflict("ExecutionLease expired before command execution")
        actual_approvals = {
            item.id
            for item in bundle.approvals
            if item.decision is ApprovalDecision.APPROVED
            and (item.expires_at is None or item.expires_at > evaluated_at)
        }
        if actual_approvals != expected_approvals:
            raise OperationCommandConflict("approval refs drifted")

        try:
            executed = execution.execute(principal, lease_id, proposal_hash)
        except (
            AipActionConflict,
            AipActionIdempotencyConflict,
            AipActionNotFound,
            AipActionTransitionBlocked,
        ) as exc:
            raise OperationCommandConflict(str(exc)) from exc
        except AipActionStoreError as exc:
            raise OperationCommandDependencyUnavailable(
                "canonical Action execution failed closed"
            ) from exc
        receipts = [item for item in executed.receipts if item.lease_id == lease_id]
        if not receipts:
            raise OperationCommandDependencyUnavailable(
                "canonical Action Receipt is unavailable"
            )
        receipt = receipts[-1]
        return {"status": receipt.status.value, **receipt.payload}


class EcommerceOperationCommandService:
    def __init__(
        self,
        *,
        action_control: OperationActionControl,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._action_control = action_control
        self._now = now or (lambda: datetime.now(UTC))

    def classify(
        self,
        principal: Principal,
        idempotency_key: str,
        request: ClassifyOperationCommandRequest,
    ) -> OperationCommandExecutionEnvelope:
        self._require_idempotency_key(idempotency_key)
        self._require_revision_scope(principal, request.revision)
        original = request.revision.original_ref.tenant
        self._require_scope(principal, original.org_id, original.project_id)
        return self._execute(
            principal=principal,
            idempotency_key=idempotency_key,
            request=request,
            command_id="classify",
            action_type_id="ecommerce.operation.classify",
        )

    def create_case(
        self,
        principal: Principal,
        idempotency_key: str,
        request: CreateOperationCaseCommandRequest,
    ) -> OperationCommandExecutionEnvelope:
        self._require_idempotency_key(idempotency_key)
        self._require_revision_scope(principal, request.revision)
        for member in request.revision.member_refs:
            self._require_scope(
                principal, member.tenant.org_id, member.tenant.project_id
            )
        return self._execute(
            principal=principal,
            idempotency_key=idempotency_key,
            request=request,
            command_id="createCase",
            action_type_id="ecommerce.operation.create-case",
        )

    def change_membership(
        self,
        principal: Principal,
        idempotency_key: str,
        request: ChangeOperationMembershipCommandRequest,
    ) -> OperationCommandExecutionEnvelope:
        self._require_idempotency_key(idempotency_key)
        self._require_revision_scope(principal, request.revision)
        for original in request.revision.moved_originals:
            self._require_scope(
                principal, original.tenant.org_id, original.tenant.project_id
            )
        return self._execute(
            principal=principal,
            idempotency_key=idempotency_key,
            request=request,
            command_id="changeMembership",
            action_type_id="ecommerce.operation.change-membership",
        )

    def manage_sla(
        self,
        principal: Principal,
        idempotency_key: str,
        request: ManageOperationSlaCommandRequest,
    ) -> OperationCommandExecutionEnvelope:
        self._require_idempotency_key(idempotency_key)
        self._require_revision_scope(principal, request.revision)
        return self._execute(
            principal=principal,
            idempotency_key=idempotency_key,
            request=request,
            command_id="manageSla",
            action_type_id="ecommerce.operation.manage-sla",
        )

    def automation_kill(
        self,
        principal: Principal,
        idempotency_key: str,
        request: KillOperationAutomationCommandRequest,
    ) -> OperationCommandExecutionEnvelope:
        self._require_idempotency_key(idempotency_key)
        self._require_revision_scope(principal, request.revision)
        return self._execute(
            principal=principal,
            idempotency_key=idempotency_key,
            request=request,
            command_id="automationKill",
            action_type_id="ecommerce.operation.automation-kill",
        )

    def _execute(
        self,
        *,
        principal: Principal,
        idempotency_key: str,
        request: Any,
        command_id: str,
        action_type_id: str,
    ) -> OperationCommandExecutionEnvelope:
        governance = request.governance
        canonical_payload = request.canonical_action_payload()
        result = self._action_control.execute_exact_chain(
            principal=principal,
            proposal_id=governance.proposal_id,
            proposal_version=governance.proposal_version,
            proposal_hash=governance.proposal_hash,
            approval_event_ids=list(governance.approval_event_ids),
            lease_id=governance.lease_id,
            action_type_id=action_type_id,
            canonical_payload=canonical_payload,
            command_idempotency_key=idempotency_key,
            evaluated_at=self._now(),
            command_id=command_id,
        )
        receipt = result.get("operationReceipt")
        if result.get("status") != "applied" or not isinstance(receipt, dict):
            raise OperationCommandDependencyUnavailable(
                "canonical action execution did not return an applied operation Receipt"
            )
        return OperationCommandExecutionEnvelope(
            tenant=TenantContext(
                org_id=principal.org_id, project_id=principal.project_id
            ),
            command_id=command_id,
            status="applied",
            proposal_id=governance.proposal_id,
            lease_id=governance.lease_id,
            operation_receipt=OperationAuthorityReceipt.model_validate(receipt),
        )

    @staticmethod
    def _require_idempotency_key(value: str) -> None:
        if not value.strip() or len(value) > 200:
            raise OperationCommandConflict(
                "Idempotency-Key must be 1..200 characters"
            )

    @staticmethod
    def _require_scope(principal: Principal, org_id: str, project_id: str) -> None:
        if (org_id, project_id) != (principal.org_id, principal.project_id):
            raise OperationCommandConflict(
                "command revision tenant does not match principal tenant"
            )

    @classmethod
    def _require_revision_scope(cls, principal: Principal, revision: Any) -> None:
        cls._require_scope(
            principal, revision.tenant.org_id, revision.tenant.project_id
        )
        if revision.actor != principal.subject:
            raise OperationCommandConflict(
                "command revision actor does not match principal actor"
            )


__all__ = [
    "CanonicalOperationActionControl",
    "EcommerceOperationCommandService",
    "OperationActionControl",
    "OperationCommandConflict",
    "OperationCommandDependencyUnavailable",
    "OperationCommandError",
]
