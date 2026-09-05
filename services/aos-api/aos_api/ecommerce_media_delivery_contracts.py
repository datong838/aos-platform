"""Strict contracts for the internal-only media delivery preparation workspace."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_media_internal_workflow_contracts import MediaInternalWorkflowDraft


class MediaDeliveryExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class MediaDeliverySelection(AipContractModel):
    family_id: str = Field(min_length=1, max_length=200)
    family_version: int = Field(ge=1)
    variant_ref: MediaDeliveryExactRef
    gate_set_ref: MediaDeliveryExactRef
    impact_preview_ref: MediaDeliveryExactRef

    @model_validator(mode="after")
    def _ref_types(self) -> "MediaDeliverySelection":
        expected = (
            (self.variant_ref, "ArtifactRevision", "variantRef"),
            (self.gate_set_ref, "MediaGateSetDecision", "gateSetRef"),
            (self.impact_preview_ref, "ImpactPreviewRevision", "impactPreviewRef"),
        )
        for ref, resource_type, label in expected:
            if ref.resource_type != resource_type:
                raise ValueError(f"{label} must reference {resource_type}")
        return self


class MediaDeliveryReviewIssue(AipContractModel):
    issue_id: str
    version: int = Field(ge=1)
    status: Literal["open", "resolved", "returned", "superseded"]
    severity: Literal["info", "warning", "error", "critical"]
    return_stage: str


class MediaDeliveryCandidate(AipContractModel):
    family_id: str
    family_version: int = Field(ge=1)
    variant_ref: MediaDeliveryExactRef
    gate_set_ref: MediaDeliveryExactRef | None = None
    gate_readiness: Literal["ready", "blocked", "stale", "conflict", "unknown"] | None = None
    impact_preview_refs: list[MediaDeliveryExactRef] = Field(default_factory=list)
    review_issues: list[MediaDeliveryReviewIssue] = Field(default_factory=list)
    return_decision_count: int = Field(ge=0)
    publish_ready: bool
    blocker_codes: list[str] = Field(default_factory=list)


class MediaDeliveryWorkspaceResponse(AipContractModel):
    tenant: TenantContext
    current_draft: MediaInternalWorkflowDraft
    history: list[MediaInternalWorkflowDraft]
    history_count: int = Field(ge=1)
    candidates: list[MediaDeliveryCandidate] = Field(default_factory=list)
    blocker_codes: list[str] = Field(default_factory=list)
    external_effects_allowed: Literal[False] = False


class MediaDeliveryExportRequest(AipContractModel):
    draft_ref: MediaDeliveryExactRef
    expected_version: int = Field(ge=1)
    selection: MediaDeliverySelection | None = None

    @model_validator(mode="after")
    def _draft_type(self) -> "MediaDeliveryExportRequest":
        if self.draft_ref.resource_type != "TaskBriefRevision":
            raise ValueError("draftRef must reference TaskBriefRevision")
        return self


class MediaDeliverySideEffects(AipContractModel):
    provider_invocation_count: Literal[0] = 0
    external_generation_count: Literal[0] = 0
    fee_charge_count: Literal[0] = 0
    publication_count: Literal[0] = 0
    business_mutation_count: Literal[0] = 0


class MediaDeliveryExportResponse(AipContractModel):
    tenant: TenantContext
    file_name: str
    content_type: Literal["application/json"] = "application/json"
    content: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    side_effects: MediaDeliverySideEffects


class MediaDeliveryPublishProposalRequest(AipContractModel):
    draft_ref: MediaDeliveryExactRef
    expected_version: int = Field(ge=1)
    selection: MediaDeliverySelection
    purpose: str = Field(min_length=2, max_length=500)

    @model_validator(mode="after")
    def _draft_type(self) -> "MediaDeliveryPublishProposalRequest":
        if self.draft_ref.resource_type != "TaskBriefRevision":
            raise ValueError("draftRef must reference TaskBriefRevision")
        return self


class MediaDeliveryProposalRef(AipContractModel):
    proposal_id: str
    version: int = Field(ge=1)
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: str


class MediaDeliveryPublishProposalResponse(AipContractModel):
    tenant: TenantContext
    proposal: MediaDeliveryProposalRef
    side_effects: MediaDeliverySideEffects
    message: str


__all__ = [name for name in globals() if name.startswith("MediaDelivery")]
