"""W6-02 responsibility profile recommendation and merge authority contracts."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef


class ResponsibilityProfile(StrEnum):
    LITE = "LITE"
    STANDARD = "STANDARD"
    FULL = "FULL"


PROFILE_ORDER = {
    ResponsibilityProfile.LITE: 0,
    ResponsibilityProfile.STANDARD: 1,
    ResponsibilityProfile.FULL: 2,
}


class CreateMergePolicyRequest(AipContractModel):
    policy_id: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=1)
    minimum_profile: ResponsibilityProfile
    maximum_risk_level: int = Field(default=3, ge=0, le=3)
    allowed_merge_groups: list[list[str]] = Field(default_factory=list, max_length=128)
    protected_responsibility_types: list[str] = Field(
        default_factory=lambda: [
            "independent_review",
            "hard_compliance",
            "external_publication_approval",
            "receipt_reconciliation",
        ],
        max_length=64,
    )
    expires_at: datetime

    @model_validator(mode="after")
    def _policy_is_canonical(self) -> CreateMergePolicyRequest:
        if self.expires_at.utcoffset() is None:
            raise ValueError("merge policy expiry requires timezone")
        if len(self.protected_responsibility_types) != len(
            set(self.protected_responsibility_types)
        ):
            raise ValueError("protected responsibility types must be unique")
        canonical_groups: set[tuple[str, ...]] = set()
        for group in self.allowed_merge_groups:
            if len(group) < 2 or len(group) != len(set(group)) or any(not item.strip() for item in group):
                raise ValueError("merge groups require at least two unique slot IDs")
            canonical_groups.add(tuple(sorted(group)))
        if len(canonical_groups) != len(self.allowed_merge_groups):
            raise ValueError("merge groups must be unique")
        return self


class MergePolicyRevision(CreateMergePolicyRequest):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class RecommendResponsibilityProfileRequest(AipContractModel):
    subject_ref: ExactRevisionRef
    candidate_template_refs: dict[ResponsibilityProfile, ExactRevisionRef]
    policy_ref: ExactRevisionRef
    risk_level: int = Field(ge=0, le=3)
    channel_count: int = Field(ge=1, le=100)
    unknown_codes: list[str] = Field(default_factory=list, max_length=128)
    requested_profile: ResponsibilityProfile | None = None
    freshness_seconds: int = Field(default=600, ge=60, le=3600)

    @model_validator(mode="after")
    def _recommendation_input_is_exact(self) -> RecommendResponsibilityProfileRequest:
        if set(self.candidate_template_refs) != set(ResponsibilityProfile):
            raise ValueError("candidate templates must cover LITE/STANDARD/FULL")
        if any(
            ref.resource_type != "ResponsibilityTemplateRevision"
            for ref in self.candidate_template_refs.values()
        ):
            raise ValueError("candidate templates must be ResponsibilityTemplateRevision")
        if self.policy_ref.resource_type != "MergePolicyRevision":
            raise ValueError("policyRef must reference MergePolicyRevision")
        if len(self.unknown_codes) != len(set(self.unknown_codes)):
            raise ValueError("unknown codes must be unique")
        return self


class ProfileRecommendationRevision(AipContractModel):
    tenant: TenantContext
    recommendation_id: str
    revision: int = Field(ge=1)
    subject_ref: ExactRevisionRef
    recommended_profile: ResponsibilityProfile
    candidate_template_refs: dict[ResponsibilityProfile, ExactRevisionRef]
    selected_template_ref: ExactRevisionRef
    policy_ref: ExactRevisionRef
    risk_level: int
    channel_count: int
    reason_codes: list[str]
    unknown_codes: list[str]
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime
    created_by: str
    created_at: datetime


class ConfirmResponsibilityProfileRequest(AipContractModel):
    recommendation_id: str = Field(min_length=1, max_length=200)
    recommendation_revision: int = Field(ge=1)
    recommendation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_profile: ResponsibilityProfile
    reason: str = Field(min_length=1, max_length=1000)


class ProfileConfirmationReceipt(AipContractModel):
    tenant: TenantContext
    confirmation_id: str
    recommendation_id: str
    recommendation_revision: int
    recommendation_hash: str
    selected_profile: ResponsibilityProfile
    selected_template_ref: ExactRevisionRef
    policy_ref: ExactRevisionRef
    actor: str
    reason: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class CreateMergeDecisionRequest(AipContractModel):
    plan_ref: ExactRevisionRef
    policy_ref: ExactRevisionRef
    confirmation_id: str = Field(min_length=1, max_length=200)
    source_slot_ids: list[str] = Field(min_length=1, max_length=64)
    target_slot_id: str = Field(min_length=1, max_length=160)
    target_assignee_resolution_receipt_id: str = Field(min_length=1, max_length=240)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _merge_shape_is_canonical(self) -> CreateMergeDecisionRequest:
        if self.plan_ref.resource_type != "ResponsibilityPlanRevision":
            raise ValueError("planRef must reference ResponsibilityPlanRevision")
        if self.policy_ref.resource_type != "MergePolicyRevision":
            raise ValueError("policyRef must reference MergePolicyRevision")
        if len(self.source_slot_ids) != len(set(self.source_slot_ids)):
            raise ValueError("source slot IDs must be unique")
        if self.target_slot_id in self.source_slot_ids:
            raise ValueError("target slot cannot be merged into itself")
        return self


class MergeDecisionReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str
    plan_ref: ExactRevisionRef
    policy_ref: ExactRevisionRef
    confirmation_id: str
    source_slot_ids: list[str]
    target_slot_id: str
    merged_responsibility_types: list[str]
    capability_union: list[str]
    target_assignee_resolution_receipt_id: str
    actor: str
    reason: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


__all__ = [
    "ConfirmResponsibilityProfileRequest",
    "CreateMergeDecisionRequest",
    "CreateMergePolicyRequest",
    "MergeDecisionReceipt",
    "MergePolicyRevision",
    "PROFILE_ORDER",
    "ProfileConfirmationReceipt",
    "ProfileRecommendationRevision",
    "RecommendResponsibilityProfileRequest",
    "ResponsibilityProfile",
]
