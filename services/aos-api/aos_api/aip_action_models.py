"""Strict HTTP models for the canonical AIP-3 Action safety chain."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import (
    ActionReceipt,
    ActionProposal,
    ActionRiskLevel,
    ActionTypeRevisionRef,
    ActorRef,
    AipContractModel,
    ApprovalDecision,
    ApprovalEvent,
    DraftSnapshot,
    ExecutionLease,
    ResourceRef,
)
from aos_api.aip_production_contracts import ExactRevisionRef


class CreateActionProposalRequest(AipContractModel):
    action_type_id: str
    task_id: str | None = None
    run_id: str | None = None
    object_ref: ResourceRef | None = None
    purpose: str
    risk_hint: ActionRiskLevel | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    diff: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[ResourceRef] = Field(default_factory=list)
    impact_preview_ref: ExactRevisionRef | None = None
    expires_at: datetime | None = None

    @field_validator("action_type_id", "purpose")
    @classmethod
    def _required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field must not be empty")
        return cleaned

    @model_validator(mode="after")
    def _run_requires_task(self) -> "CreateActionProposalRequest":
        if self.run_id and not self.task_id:
            raise ValueError("runId requires taskId")
        if (
            self.impact_preview_ref is not None
            and self.impact_preview_ref.resource_type != "ImpactPreviewRevision"
        ):
            raise ValueError("impactPreviewRef must reference ImpactPreviewRevision")
        return self

    def effective_expiry(self) -> datetime:
        return self.expires_at or datetime.now(timezone.utc) + timedelta(hours=24)


class CreateActionDraftRequest(CreateActionProposalRequest):
    """Editable input for the explicit W5 Draft -> Proposal submit path."""


class ReviseActionDraftRequest(CreateActionDraftRequest):
    expected_revision: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class SubmitActionDraftRequest(AipContractModel):
    expected_revision: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ActionDraftRevisionSnapshot(AipContractModel):
    draft_id: str
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    lifecycle: str
    request: CreateActionDraftRequest
    action_type_revision_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    risk_level: ActionRiskLevel
    approval_policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    submitted_proposal_id: str | None = None
    created_by: ActorRef
    created_at: datetime


class ActionProposalSnapshot(ActionProposal):
    client_risk_hint: ActionRiskLevel | None = None
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    diff: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[ResourceRef] = Field(default_factory=list)
    impact_preview_ref: ExactRevisionRef | None = None
    action_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    approval_policy_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_draft_ref: ExactRevisionRef | None = None
    compensation_original_proposal_id: str | None = None
    compensation_original_receipt_id: str | None = None
    compensation_policy_ref: ExactRevisionRef | None = None
    compensation_effect: dict[str, Any] | None = None
    compensation_residual_effect: dict[str, Any] | None = None


class ActionDraftBundle(AipContractModel):
    proposal: ActionProposalSnapshot
    draft: DraftSnapshot
    approvals: list["ActionApprovalEventSnapshot"] = Field(default_factory=list)


class ActionApprovalEventSnapshot(ApprovalEvent):
    action_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    approval_policy_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    slot_id: str | None = None
    eligibility_snapshot_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )


class ActionProposalListResponse(AipContractModel):
    items: list[ActionDraftBundle] = Field(default_factory=list)
    count: int


class DecideActionProposalRequest(AipContractModel):
    expected_proposal_version: int = Field(ge=1)
    expected_proposal_hash: str
    decision: ApprovalDecision
    reason: str = ""
    approval_expires_at: datetime | None = None

    @field_validator("expected_proposal_hash")
    @classmethod
    def _hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("expectedProposalHash must be a sha256 digest")
        return normalized


class ActionProposalTimeline(AipContractModel):
    bundle: ActionDraftBundle
    events: list[dict[str, Any]] = Field(default_factory=list)


class AcquireExecutionLeaseRequest(AipContractModel):
    expected_proposal_version: int = Field(ge=1)
    expected_proposal_hash: str
    lease_seconds: int = Field(default=120, ge=10, le=600)

    @field_validator("expected_proposal_hash")
    @classmethod
    def _lease_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("expectedProposalHash must be a sha256 digest")
        return normalized


class ExecuteActionLeaseRequest(AipContractModel):
    expected_proposal_hash: str

    @field_validator("expected_proposal_hash")
    @classmethod
    def _execute_hash(cls, value: str) -> str:
        return AcquireExecutionLeaseRequest._lease_hash(value)


class ReconcileActionReceiptRequest(AipContractModel):
    reason: str = "authorized provider reread"


class CreateManualReconcileCaseRequest(AipContractModel):
    reason: str = "automatic reconciliation unavailable"
    required_facts: list[str] = Field(default_factory=list)
    evidence_refs: list[ResourceRef] = Field(default_factory=list)
    expires_at: datetime | None = None


class DecideManualReconcileCaseRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    decision: Literal[
        "confirmed_applied",
        "confirmed_failed",
        "confirmed_partial",
        "unresolved",
    ]
    evidence_refs: list[ResourceRef] = Field(default_factory=list)
    applied_effect: dict[str, Any] | None = None
    compensated_effect: dict[str, Any] | None = None
    residual_effect: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _effect_is_required_for_partial(self) -> "DecideManualReconcileCaseRequest":
        if self.decision == "confirmed_partial" and (
            self.applied_effect is None or self.residual_effect is None
        ):
            raise ValueError("confirmed_partial requires appliedEffect and residualEffect")
        return self


class CreateCompensationRequest(AipContractModel):
    action_type_id: str | None = None
    receipt_id: str
    purpose: str
    payload: dict[str, Any] = Field(default_factory=dict)
    policy_revision_ref: ExactRevisionRef | None = None
    effect_delta: dict[str, Any] | None = None
    impact_preview_ref: ExactRevisionRef | None = None

    @model_validator(mode="after")
    def _exact_refs(self) -> "CreateCompensationRequest":
        if self.policy_revision_ref is not None and (
            self.policy_revision_ref.resource_type != "CompensationPolicyRevision"
        ):
            raise ValueError("policyRevisionRef must reference CompensationPolicyRevision")
        if self.impact_preview_ref is not None and (
            self.impact_preview_ref.resource_type != "ImpactPreviewRevision"
        ):
            raise ValueError("impactPreviewRef must reference ImpactPreviewRevision")
        return self


class ActionReceiptSnapshot(ActionReceipt):
    receipt_kind: str = "initial"
    supersedes_receipt_id: str | None = None
    request_fingerprint: str
    payload: dict[str, Any] = Field(default_factory=dict)
    attempt_id: str | None = None
    action_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    approval_set_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    adapter_revision_ref: dict[str, Any] | None = None
    account_binding_ref: dict[str, Any] | None = None
    capability_binding_ref: dict[str, Any] | None = None
    reservation_ref: dict[str, Any] | None = None
    response_artifact_ref: ResourceRef | None = None
    response_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_schema_ref: dict[str, Any] | None = None
    receipt_schema_ref: dict[str, Any] | None = None
    usage_schema_ref: dict[str, Any] | None = None
    redaction_policy_ref: dict[str, Any] | None = None
    usage_receipt_refs: list[ResourceRef] = Field(default_factory=list)
    lineage_source_ref: ResourceRef | None = None
    receipt_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_outcome: Literal["accepted", "applied", "failed", "partial", "unknown"] | None = None
    reconciliation_status: Literal[
        "not_required", "pending", "automatic", "manual", "unresolved"
    ] = "not_required"
    resolution_quality: Literal["confirmed", "insufficient", "conflicted"] | None = None
    resolution_source: Literal["provider_query", "manual_evidence"] | None = None
    resolution_cutoff: datetime | None = None
    reconcile_attempt_id: str | None = None
    manual_reconcile_case_id: str | None = None
    manual_decision_receipt_id: str | None = None
    applied_effect: dict[str, Any] | None = None
    compensated_effect: dict[str, Any] | None = None
    residual_effect: dict[str, Any] | None = None


class ActionReconcileAttemptSnapshot(AipContractModel):
    id: str
    original_receipt_id: str
    status: Literal["pending", "claimed", "resolved", "manual_required"]
    provider_request_id: str | None = None
    expires_at: datetime
    created_at: datetime
    claimed_at: datetime | None = None
    completed_at: datetime | None = None


class ManualReconcileCaseSnapshot(AipContractModel):
    id: str
    original_receipt_id: str
    status: Literal["open", "unresolved", "resolved"]
    version: int = Field(ge=1)
    required_facts: list[str] = Field(default_factory=list)
    evidence_refs: list[ResourceRef] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    conflict_facts: list[str] = Field(default_factory=list)
    maker_id: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class ActionExecutionLeaseSnapshot(ExecutionLease):
    action_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    approval_set_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reservation_ref: ResourceRef | None = None


class ActionExecutionAttemptSnapshot(AipContractModel):
    id: str
    lease_id: str
    proposal_id: str
    status: str
    action_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    approval_set_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    adapter_revision_ref: dict[str, Any] | None = None
    idempotency_envelope: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_id: str | None = None
    provider_outcome: str | None = None
    usage_settlement_status: str = "pending"
    lineage_projection_status: str = "pending"
    created_at: datetime
    claimed_at: datetime | None = None
    finished_at: datetime | None = None


class ActionExecutionView(AipContractModel):
    proposal: ActionProposalSnapshot
    lease: ActionExecutionLeaseSnapshot | None = None
    attempt: ActionExecutionAttemptSnapshot | None = None
    receipts: list[ActionReceiptSnapshot] = Field(default_factory=list)
    reconcile_attempt: ActionReconcileAttemptSnapshot | None = None
    manual_reconcile_case: ManualReconcileCaseSnapshot | None = None


def actor(actor_id: str) -> ActorRef:
    return ActorRef(actor_type="user", actor_id=actor_id)


__all__ = [
    "ActionDraftBundle",
    "ActionDraftRevisionSnapshot",
    "ActionApprovalEventSnapshot",
    "ActionExecutionLeaseSnapshot",
    "ActionExecutionAttemptSnapshot",
    "ActionProposalListResponse",
    "ActionProposalSnapshot",
    "ActionProposalTimeline",
    "ActionReceiptSnapshot",
    "ActionReconcileAttemptSnapshot",
    "ManualReconcileCaseSnapshot",
    "ActionExecutionView",
    "AcquireExecutionLeaseRequest",
    "CreateCompensationRequest",
    "CreateManualReconcileCaseRequest",
    "DecideManualReconcileCaseRequest",
    "CreateActionDraftRequest",
    "ActionTypeRevisionRef",
    "CreateActionProposalRequest",
    "DecideActionProposalRequest",
    "ExecuteActionLeaseRequest",
    "ReconcileActionReceiptRequest",
    "ReviseActionDraftRequest",
    "SubmitActionDraftRequest",
    "actor",
]
