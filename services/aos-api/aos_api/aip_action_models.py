"""Strict HTTP models for the canonical AIP-3 Action safety chain."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

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
        return self

    def effective_expiry(self) -> datetime:
        return self.expires_at or datetime.now(timezone.utc) + timedelta(hours=24)


class ActionProposalSnapshot(ActionProposal):
    client_risk_hint: ActionRiskLevel | None = None
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    diff: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[ResourceRef] = Field(default_factory=list)


class ActionDraftBundle(AipContractModel):
    proposal: ActionProposalSnapshot
    draft: DraftSnapshot
    approvals: list[ApprovalEvent] = Field(default_factory=list)


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


class CreateCompensationRequest(AipContractModel):
    action_type_id: str
    receipt_id: str
    purpose: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionReceiptSnapshot(ActionReceipt):
    receipt_kind: str = "initial"
    supersedes_receipt_id: str | None = None
    request_fingerprint: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionExecutionView(AipContractModel):
    proposal: ActionProposalSnapshot
    lease: ExecutionLease | None = None
    receipts: list[ActionReceiptSnapshot] = Field(default_factory=list)


def actor(actor_id: str) -> ActorRef:
    return ActorRef(actor_type="user", actor_id=actor_id)


__all__ = [
    "ActionDraftBundle",
    "ActionProposalListResponse",
    "ActionProposalSnapshot",
    "ActionProposalTimeline",
    "ActionReceiptSnapshot",
    "ActionExecutionView",
    "AcquireExecutionLeaseRequest",
    "CreateCompensationRequest",
    "ActionTypeRevisionRef",
    "CreateActionProposalRequest",
    "DecideActionProposalRequest",
    "ExecuteActionLeaseRequest",
    "ReconcileActionReceiptRequest",
    "actor",
]
