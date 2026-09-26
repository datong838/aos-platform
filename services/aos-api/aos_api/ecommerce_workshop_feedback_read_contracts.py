"""Read-only business feedback contract; technical refs stay in auditDetails."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


SCHEMA_VERSION = "aos.ecommerce-workshop.feedback-read/v1"
SegmentKind = Literal["daily_review", "improvement_observation", "memory_candidate"]
SegmentState = Literal["pending", "acknowledged", "unknown"]


class FeedbackExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=240)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str | None = None


class FeedbackSegmentView(AipContractModel):
    sequence: int = Field(ge=1, le=3)
    kind: SegmentKind
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=1000)
    state: SegmentState
    status_label: str = Field(min_length=1, max_length=120)


class FeedbackAuditDetails(AipContractModel):
    command_id: str
    review_receipt_ref: FeedbackExactRef
    artifact_ref: FeedbackExactRef
    task_ref: FeedbackExactRef
    target_receipt_refs: list[FeedbackExactRef | None] = Field(min_length=3, max_length=3)
    effect_review_ref: FeedbackExactRef | None = None


class FeedbackBusinessItem(AipContractModel):
    title: str = Field(min_length=1, max_length=300)
    created_at: datetime
    decision_label: Literal["评审通过"] = "评审通过"
    segments: list[FeedbackSegmentView] = Field(min_length=3, max_length=3)
    effect_status: Literal["待观察", "证据不足", "状态待核对"]
    candidate_status: Literal["尚未形成", "待治理", "已驳回", "已隔离", "已批准待入库", "已入库"]
    execution_authorized: Literal[False] = False
    audit_details: FeedbackAuditDetails

    @field_validator("created_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("feedback creation time must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _canonical_order(self) -> FeedbackBusinessItem:
        if [(segment.sequence, segment.kind) for segment in self.segments] != [
            (1, "daily_review"), (2, "improvement_observation"), (3, "memory_candidate")
        ]:
            raise ValueError("feedback segments must retain the accepted three-stage order")
        if self.candidate_status != "尚未形成" and self.segments[2].state != "acknowledged":
            raise ValueError("candidate status requires the third Receipt")
        return self


class FeedbackReadEnvelope(AipContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    data_cutoff: datetime
    items: list[FeedbackBusinessItem] = Field(max_length=20)
    has_more: bool

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("feedback cutoff must be timezone-aware")
        return value


__all__ = [
    "SCHEMA_VERSION", "FeedbackAuditDetails", "FeedbackBusinessItem",
    "FeedbackExactRef", "FeedbackReadEnvelope", "FeedbackSegmentView",
]
