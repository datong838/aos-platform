"""Contracts for the tenant-safe creator internal workflow."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef

CreatorWorkflowCommand = Literal["create", "save", "submit_review", "approve", "reject", "restore"]
CreatorWorkflowPurpose = Literal["candidate_import", "outreach_batch", "outreach_message", "collaboration", "delivery_check", "relationship_plan"]
CreatorWorkflowStatus = Literal["draft", "in_review", "approved", "rejected"]


class CreatorInternalWorkflowCommandRequest(AipContractModel):
    command: CreatorWorkflowCommand
    purpose: CreatorWorkflowPurpose
    title: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=2, max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)
    draft_ref: ExactRevisionRef | None = None
    expected_version: int | None = Field(default=None, ge=1)
    restore_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _revision_contract(self) -> "CreatorInternalWorkflowCommandRequest":
        revising = self.command != "create"
        if revising != (self.draft_ref is not None and self.expected_version is not None):
            raise ValueError("revision commands require draftRef and expectedVersion")
        if self.draft_ref and self.draft_ref.resource_type != "TaskBriefRevision":
            raise ValueError("draftRef must reference TaskBriefRevision")
        if (self.command == "restore") != (self.restore_revision is not None):
            raise ValueError("restore requires restoreRevision and other commands forbid it")
        return self


class CreatorInternalWorkflowDraft(ExactRevisionRef):
    resource_type: Literal["TaskBriefRevision"] = "TaskBriefRevision"
    version: int = Field(ge=1)
    purpose: CreatorWorkflowPurpose
    title: str
    summary: str
    details: dict[str, Any]
    status: CreatorWorkflowStatus


class CreatorInternalWorkflowReceipt(AipContractModel):
    receipt_id: str
    operation: Literal["task_brief.create", "task_brief.revise"]
    idempotency_key: str
    replay: bool


class CreatorInternalWorkflowSideEffects(AipContractModel):
    provider_invocation_count: Literal[0] = 0
    external_outreach_count: Literal[0] = 0
    contract_signature_count: Literal[0] = 0
    business_mutation_count: Literal[0] = 0


class CreatorInternalWorkflowCommandResponse(AipContractModel):
    tenant: TenantContext
    command: CreatorWorkflowCommand
    task_id: str
    draft: CreatorInternalWorkflowDraft
    receipt: CreatorInternalWorkflowReceipt
    side_effects: CreatorInternalWorkflowSideEffects
    message: str


class CreatorInternalWorkflowHistoryResponse(AipContractModel):
    tenant: TenantContext
    items: list[CreatorInternalWorkflowDraft]
    count: int = Field(ge=0)


class CreatorInternalWorkflowListResponse(AipContractModel):
    tenant: TenantContext
    items: list[CreatorInternalWorkflowDraft]
    count: int = Field(ge=0)
