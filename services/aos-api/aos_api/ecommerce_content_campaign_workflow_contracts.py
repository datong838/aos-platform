"""Contracts for the internal content-campaign drafting workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef


class ContentCampaignRiskDecisionInput(AipContractModel):
    category: Literal["discount_margin", "inventory_supply"]
    disposition: Literal["adopt_recommendation", "keep_current", "custom", "defer"]
    constraint: str = Field(min_length=2, max_length=500)

    @field_validator("constraint")
    @classmethod
    def _clean_constraint(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("constraint must contain at least two characters")
        return cleaned


class ContentCampaignRiskDecision(ContentCampaignRiskDecisionInput):
    applied_from_revision: int = Field(ge=1)


class ContentCampaignWorkflowCommandRequest(AipContractModel):
    command: Literal["generate", "save", "regenerate", "apply_risk_decision", "undo_risk_decision"]
    objective: str = Field(min_length=4, max_length=2000)
    channels: list[str] = Field(default_factory=lambda: ["微信小店"], min_length=1, max_length=12)
    audience: str | None = Field(default=None, max_length=500)
    time_window: str | None = Field(default=None, max_length=300)
    constraints: list[str] = Field(default_factory=list, max_length=30)
    draft_ref: ExactRevisionRef | None = None
    expected_version: int | None = Field(default=None, ge=1)
    risk_decision: ContentCampaignRiskDecisionInput | None = None

    @field_validator("objective")
    @classmethod
    def _clean_objective(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 4:
            raise ValueError("objective must contain at least four characters")
        return cleaned

    @field_validator("channels", "constraints")
    @classmethod
    def _unique_business_values(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(value.split()) for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("values must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _revision_inputs(self) -> "ContentCampaignWorkflowCommandRequest":
        revising = self.command != "generate"
        if revising != (self.draft_ref is not None and self.expected_version is not None):
            raise ValueError("revision commands require draftRef and expectedVersion")
        if self.draft_ref is not None and self.draft_ref.resource_type != "TaskBriefRevision":
            raise ValueError("draftRef must reference TaskBriefRevision")
        if (self.command == "apply_risk_decision") != (self.risk_decision is not None):
            raise ValueError("applyRiskDecision requires riskDecision and other commands forbid it")
        return self


class ContentCampaignWorkflowTask(AipContractModel):
    task_id: str
    title: str


class ContentCampaignWorkflowDraft(ExactRevisionRef):
    resource_type: Literal["TaskBriefRevision"] = "TaskBriefRevision"
    version: int = Field(ge=1)
    objective: str
    channels: list[str]
    constraints: list[str] = Field(default_factory=list)
    risk_decisions: list[ContentCampaignRiskDecision] = Field(default_factory=list)
    last_action: str | None = None


class ContentCampaignWorkflowReceipt(AipContractModel):
    receipt_id: str
    operation: Literal["task_brief.create", "task_brief.revise"]
    idempotency_key: str
    replay: bool


class ContentCampaignWorkflowSideEffects(AipContractModel):
    provider_invocation_count: Literal[0] = 0
    approval_created_count: Literal[0] = 0
    task_run_created_count: Literal[0] = 0
    external_publication_count: Literal[0] = 0
    external_business_mutation_count: Literal[0] = 0


class ContentCampaignWorkflowCommandResponse(AipContractModel):
    tenant: TenantContext
    command: Literal["generate", "save", "regenerate", "apply_risk_decision", "undo_risk_decision"]
    task: ContentCampaignWorkflowTask
    draft: ContentCampaignWorkflowDraft
    receipt: ContentCampaignWorkflowReceipt
    side_effects: ContentCampaignWorkflowSideEffects
    message: str


class ContentCampaignApprovalPreviewRequest(AipContractModel):
    draft_ref: ExactRevisionRef

    @field_validator("draft_ref")
    @classmethod
    def _draft_ref(cls, value: ExactRevisionRef) -> ExactRevisionRef:
        if value.resource_type != "TaskBriefRevision":
            raise ValueError("draftRef must reference TaskBriefRevision")
        return value


class ContentCampaignApprovalCheck(AipContractModel):
    name: str
    passed: bool
    detail: str


class ContentCampaignApprovalPreviewResponse(AipContractModel):
    tenant: TenantContext
    status: Literal["reviewable", "needs_input"]
    approval_allowed: bool
    draft: ContentCampaignWorkflowDraft
    checks: list[ContentCampaignApprovalCheck]
    next_actions: list[str]
    evaluated_at: datetime
    data_cutoff: datetime
    side_effects: ContentCampaignWorkflowSideEffects
