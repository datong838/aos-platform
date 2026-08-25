"""W6-02 responsibility profile recommendation and merge authority contracts."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

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


class ProjectedCostInput(AipContractModel):
    profile: ResponsibilityProfile
    stage_id: str = Field(min_length=1, max_length=160)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    usage_basis: Literal["input_tokens", "output_tokens", "cached_tokens"]
    price_snapshot_ref: ExactRevisionRef | None = None
    quantity_lower: Decimal | None = Field(default=None, ge=0)
    quantity_upper: Decimal | None = Field(default=None, ge=0)
    tax_lower: Decimal = Field(default=Decimal("0"), ge=0)
    tax_upper: Decimal = Field(default=Decimal("0"), ge=0)
    platform_fee_lower: Decimal = Field(default=Decimal("0"), ge=0)
    platform_fee_upper: Decimal = Field(default=Decimal("0"), ge=0)
    license_fee_lower: Decimal = Field(default=Decimal("0"), ge=0)
    license_fee_upper: Decimal = Field(default=Decimal("0"), ge=0)
    redundancy_lower: Decimal = Field(default=Decimal("0"), ge=0)
    redundancy_upper: Decimal = Field(default=Decimal("0"), ge=0)
    license_refs: list[ExactRevisionRef] = Field(default_factory=list, max_length=32)
    assumptions: list[str] = Field(default_factory=list, max_length=64)
    unknown_codes: list[str] = Field(default_factory=list, max_length=64)
    expires_at: datetime

    @model_validator(mode="after")
    def _projection_input_is_explicit(self) -> Self:
        if self.expires_at.utcoffset() is None:
            raise ValueError("projected cost expiry requires timezone")
        if len(self.unknown_codes) != len(set(self.unknown_codes)):
            raise ValueError("projected cost unknown codes must be unique")
        if len(self.assumptions) != len(set(self.assumptions)):
            raise ValueError("projected cost assumptions must be unique")
        if len(self.license_refs) != len(
            {(item.resource_id, item.revision, item.content_hash) for item in self.license_refs}
        ):
            raise ValueError("projected cost license refs must be unique")
        known = not self.unknown_codes
        if known and (
            self.price_snapshot_ref is None
            or self.quantity_lower is None
            or self.quantity_upper is None
        ):
            raise ValueError("known projected cost requires exact price and quantity range")
        if self.price_snapshot_ref is not None and (
            self.price_snapshot_ref.resource_type != "ModelPriceSnapshotRevision"
        ):
            raise ValueError("priceSnapshotRef must reference ModelPriceSnapshotRevision")
        if (
            self.quantity_lower is not None
            and self.quantity_upper is not None
            and self.quantity_upper < self.quantity_lower
        ):
            raise ValueError("projected quantity range is invalid")
        for lower, upper in (
            (self.tax_lower, self.tax_upper),
            (self.platform_fee_lower, self.platform_fee_upper),
            (self.license_fee_lower, self.license_fee_upper),
            (self.redundancy_lower, self.redundancy_upper),
        ):
            if upper < lower:
                raise ValueError("projected fee range is invalid")
        return self


class ProjectedCostRange(AipContractModel):
    profile: ResponsibilityProfile
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    component_count: int = Field(ge=1)
    price_snapshot_refs: list[ExactRevisionRef] = Field(default_factory=list, max_length=64)
    lower_amount: Decimal | None = Field(default=None, ge=0)
    upper_amount: Decimal | None = Field(default=None, ge=0)
    assumptions: list[str] = Field(default_factory=list, max_length=128)
    unknown_codes: list[str] = Field(default_factory=list, max_length=128)
    confidence: Literal["high", "medium", "low", "unknown"]
    expires_at: datetime

    @model_validator(mode="after")
    def _range_never_masks_unknown_as_zero(self) -> Self:
        if self.expires_at.utcoffset() is None:
            raise ValueError("projected cost range expiry requires timezone")
        if self.unknown_codes:
            if self.lower_amount is not None or self.upper_amount is not None:
                raise ValueError("unknown projected cost cannot expose numeric bounds")
            if self.confidence != "unknown":
                raise ValueError("unknown projected cost requires unknown confidence")
        elif (
            self.lower_amount is None
            or self.upper_amount is None
            or self.upper_amount < self.lower_amount
            or self.confidence == "unknown"
        ):
            raise ValueError("known projected cost requires an ordered numeric range")
        return self


class ProjectedDurationRange(AipContractModel):
    lower_seconds: int | None = Field(default=None, ge=0)
    upper_seconds: int | None = Field(default=None, ge=0)
    assumptions: list[str] = Field(default_factory=list, max_length=64)
    unknown_codes: list[str] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def _duration_never_masks_unknown(self) -> Self:
        if self.unknown_codes:
            if self.lower_seconds is not None or self.upper_seconds is not None:
                raise ValueError("unknown duration cannot expose numeric bounds")
        elif (
            self.lower_seconds is None
            or self.upper_seconds is None
            or self.upper_seconds < self.lower_seconds
        ):
            raise ValueError("known duration requires an ordered range")
        return self


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


class RecommendMediaResponsibilityProfileRequest(
    RecommendResponsibilityProfileRequest
):
    evidence_bundle_ref: ExactRevisionRef
    eval_contract_ref: ExactRevisionRef
    stage_template_refs: dict[ResponsibilityProfile, ExactRevisionRef]
    cost_inputs: list[ProjectedCostInput] = Field(min_length=3, max_length=128)
    projected_duration: ProjectedDurationRange
    assumptions: list[str] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def _media_dependencies_are_exact(self) -> Self:
        dependency_types = (
            (self.subject_ref.resource_type, "TaskBriefRevision"),
            (self.evidence_bundle_ref.resource_type, "EvidenceBundleRevision"),
            (self.eval_contract_ref.resource_type, "EvalContractRevision"),
        )
        if any(actual != expected for actual, expected in dependency_types):
            raise ValueError("media recommendation requires exact Brief/Evidence/Eval refs")
        if set(self.stage_template_refs) != set(ResponsibilityProfile) or any(
            ref.resource_type != "StageTemplateRevision"
            for ref in self.stage_template_refs.values()
        ):
            raise ValueError("media recommendation requires three exact Stage templates")
        if not set(ResponsibilityProfile).issubset(
            {item.profile for item in self.cost_inputs}
        ):
            raise ValueError("projected cost inputs must cover all three profiles")
        if len(self.assumptions) != len(set(self.assumptions)):
            raise ValueError("recommendation assumptions must be unique")
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
    dependency_refs: list[ExactRevisionRef] = Field(default_factory=list, max_length=256)
    projected_cost_ranges: list[ProjectedCostRange] = Field(
        default_factory=list, max_length=64
    )
    projected_duration: ProjectedDurationRange | None = None
    assumptions: list[str] = Field(default_factory=list, max_length=128)
    confidence: Literal["high", "medium", "low", "unknown"] = "unknown"
    readiness: Literal["ready", "blocked", "stale", "unknown"] = "unknown"
    blockers: list[str] = Field(default_factory=list, max_length=128)
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
    recommendation_etag: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    selected_projected_cost_ranges: list[ProjectedCostRange] = Field(
        default_factory=list, max_length=32
    )
    actor: str
    reason: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class ProfileRecommendationListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ProfileRecommendationRevision]
    count: int = Field(ge=0)


class ProfileConfirmationListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ProfileConfirmationReceipt]
    count: int = Field(ge=0)


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
    "ProfileConfirmationListResponse",
    "ProfileRecommendationRevision",
    "ProfileRecommendationListResponse",
    "ProjectedCostInput",
    "ProjectedCostRange",
    "ProjectedDurationRange",
    "RecommendMediaResponsibilityProfileRequest",
    "RecommendResponsibilityProfileRequest",
    "ResponsibilityProfile",
]
