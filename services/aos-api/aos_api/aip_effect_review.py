"""EffectReview / EffectMaturity authority (W-L19).

accepted and effect_completed are independent axes. Maturity decisions never
promote immature reviews to completed.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext


class EffectMaturityStatus(StrEnum):
    IMMATURE = "immature"
    MATURE = "mature"
    INSUFFICIENT = "insufficient"
    UNKNOWN = "unknown"


class CreateEffectReviewRequest(AipContractModel):
    subject_id: str = Field(min_length=1, max_length=240)
    subject_ref: ResourceRef
    observation_refs: list[ResourceRef] = Field(default_factory=list, max_length=32)
    metric_keys: list[str] = Field(default_factory=list, max_length=32)
    sample_count: int = Field(default=0, ge=0)
    min_sample: int = Field(default=1, ge=1)
    cutoff_at: datetime
    event_time_at: datetime
    accepted: bool = False
    expected_revision: int = Field(default=0, ge=0)
    reason_code: str = Field(default="effect_observed", min_length=1, max_length=160)

    @model_validator(mode="after")
    def _cutoff_after_event(self) -> "CreateEffectReviewRequest":
        if self.cutoff_at < self.event_time_at:
            raise ValueError("cutoffAt must be at or after eventTimeAt")
        return self


class EffectReviewRevision(AipContractModel):
    tenant: TenantContext
    review_id: str
    subject_id: str
    revision: int = Field(ge=1)
    subject_ref: ResourceRef
    observation_refs: list[ResourceRef]
    metric_keys: list[str]
    sample_count: int = Field(ge=0)
    min_sample: int = Field(ge=1)
    cutoff_at: datetime
    event_time_at: datetime
    accepted: bool
    effect_completed: bool
    maturity_status: EffectMaturityStatus
    reason_code: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str
    created_at: datetime


class EvaluateEffectMaturityRequest(AipContractModel):
    subject_id: str = Field(min_length=1, max_length=240)
    observed_at: datetime
    reason_code: str = Field(default="maturity_window_check", min_length=1, max_length=160)


class EffectMaturityDecision(AipContractModel):
    tenant: TenantContext
    decision_id: str
    subject_id: str
    review_id: str
    review_revision: int = Field(ge=1)
    maturity_status: EffectMaturityStatus
    accepted: bool
    effect_completed: bool
    sample_count: int
    min_sample: int
    cutoff_at: datetime
    observed_at: datetime
    reason_code: str
    actor: str
    created_at: datetime


class EffectAxisSnapshot(AipContractModel):
    """Five independent axes — no axis may impersonate another."""

    tenant: TenantContext
    subject_id: str
    item_outcome: str | None = None
    action_outcome: str | None = None
    usage_settlement: str | None = None
    effect_maturity: EffectMaturityStatus | None = None
    handoff_decision: str | None = None
    accepted: bool | None = None
    effect_completed: bool | None = None
    review_revision: int | None = None


__all__ = [
    "CreateEffectReviewRequest",
    "EffectAxisSnapshot",
    "EffectMaturityDecision",
    "EffectMaturityStatus",
    "EffectReviewRevision",
    "EvaluateEffectMaturityRequest",
]
