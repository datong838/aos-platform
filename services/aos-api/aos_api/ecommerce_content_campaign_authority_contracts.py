"""Canonical tenant-bound authority contracts for content and campaigns."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


class ContentCampaignExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CampaignLifecycle(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"


class CalendarLifecycle(StrEnum):
    SCHEDULED = "scheduled"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"


class CalendarDecisionType(StrEnum):
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    CONFLICT_OVERRIDE = "conflictOverride"


class DstResolution(StrEnum):
    EXACT = "exact"
    EARLIER = "earlier"
    LATER = "later"


class IntentLifecycle(StrEnum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"


def _require_type(
    value: ContentCampaignExactRef | None,
    expected: set[str],
    field_name: str,
) -> None:
    if value is not None and value.resource_type not in expected:
        raise ValueError(f"{field_name} must reference {sorted(expected)}")


class CampaignRevision(AipContractModel):
    tenant: TenantContext
    campaign_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    prior_ref: ContentCampaignExactRef | None = None
    lifecycle: CampaignLifecycle
    goal_period_ref: ContentCampaignExactRef
    budget_envelope_ref: ContentCampaignExactRef
    offer_ref: ContentCampaignExactRef | None = None
    channel_ids: list[str] = Field(min_length=1, max_length=20)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("campaign createdAt must include a timezone")
        return value

    @field_validator("channel_ids")
    @classmethod
    def _unique_channels(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(not item.strip() for item in value):
            raise ValueError("channelIds must be unique and non-blank")
        return value

    @model_validator(mode="after")
    def _revision_chain(self) -> CampaignRevision:
        if self.version != self.revision:
            raise ValueError("campaign version must equal revision")
        if (self.revision == 1) != (self.prior_ref is None):
            raise ValueError("campaign revisions after r1 require priorRef")
        _require_type(self.prior_ref, {"CampaignRevision"}, "priorRef")
        if self.prior_ref is not None:
            if self.prior_ref.resource_id != self.campaign_id:
                raise ValueError("priorRef must target the same campaign")
            if self.prior_ref.revision != self.revision - 1:
                raise ValueError("priorRef must target the preceding revision")
        _require_type(self.goal_period_ref, {"GoalPeriodRevision"}, "goalPeriodRef")
        _require_type(
            self.budget_envelope_ref,
            {"BudgetEnvelopeRevision"},
            "budgetEnvelopeRef",
        )
        _require_type(self.offer_ref, {"OfferRevision"}, "offerRef")
        return self


class CalendarEntryRevision(AipContractModel):
    tenant: TenantContext
    entry_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    prior_ref: ContentCampaignExactRef | None = None
    lifecycle: CalendarLifecycle
    campaign_ref: ContentCampaignExactRef
    content_artifact_refs: list[ContentCampaignExactRef] = Field(max_length=50)
    timezone: str = Field(min_length=1, max_length=100)
    local_start: str = Field(min_length=16, max_length=40)
    local_end: str = Field(min_length=16, max_length=40)
    resolved_start: datetime
    resolved_end: datetime
    dst_resolution: DstResolution
    conflict_decision_ref: ContentCampaignExactRef | None = None
    cancellation_reason: str | None = Field(default=None, max_length=1000)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("resolved_start", "resolved_end", "created_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("calendar timestamps must include a timezone")
        return value

    @field_validator("timezone")
    @classmethod
    def _iana_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA name") from exc
        return value

    @field_validator("content_artifact_refs")
    @classmethod
    def _unique_artifacts(
        cls, value: list[ContentCampaignExactRef]
    ) -> list[ContentCampaignExactRef]:
        identities = [(item.resource_id, item.revision) for item in value]
        if len(identities) != len(set(identities)):
            raise ValueError("contentArtifactRefs must be unique")
        for item in value:
            _require_type(item, {"ArtifactRevision"}, "contentArtifactRefs")
        return value

    @model_validator(mode="after")
    def _calendar_integrity(self) -> CalendarEntryRevision:
        if self.version != self.revision:
            raise ValueError("calendar version must equal revision")
        if (self.revision == 1) != (self.prior_ref is None):
            raise ValueError("calendar revisions after r1 require priorRef")
        _require_type(self.prior_ref, {"CalendarEntryRevision"}, "priorRef")
        if self.prior_ref is not None:
            if self.prior_ref.resource_id != self.entry_id:
                raise ValueError("priorRef must target the same entry")
            if self.prior_ref.revision != self.revision - 1:
                raise ValueError("priorRef must target the preceding revision")
        _require_type(self.campaign_ref, {"CampaignRevision"}, "campaignRef")
        _require_type(
            self.conflict_decision_ref,
            {"CalendarDecisionRevision"},
            "conflictDecisionRef",
        )
        if self.resolved_start >= self.resolved_end:
            raise ValueError("resolvedStart must precede resolvedEnd")
        if self.lifecycle is CalendarLifecycle.CANCELLED:
            if not self.cancellation_reason or not self.cancellation_reason.strip():
                raise ValueError("cancelled entries require cancellationReason")
        elif self.cancellation_reason is not None:
            raise ValueError("only cancelled entries may have cancellationReason")
        return self


class CalendarDecisionRevision(AipContractModel):
    tenant: TenantContext
    decision_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    decision_type: CalendarDecisionType
    from_entry_ref: ContentCampaignExactRef
    to_entry_ref: ContentCampaignExactRef
    reason: str = Field(min_length=1, max_length=1000)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("calendar decision createdAt must include a timezone")
        return value

    @model_validator(mode="after")
    def _successor_integrity(self) -> CalendarDecisionRevision:
        _require_type(
            self.from_entry_ref, {"CalendarEntryRevision"}, "fromEntryRef"
        )
        _require_type(self.to_entry_ref, {"CalendarEntryRevision"}, "toEntryRef")
        if self.from_entry_ref.resource_id != self.to_entry_ref.resource_id:
            raise ValueError("calendar decisions must retain entry identity")
        if self.to_entry_ref.revision != self.from_entry_ref.revision + 1:
            raise ValueError("calendar decisions must reference an exact successor")
        return self


class MasterContentIntentRevision(AipContractModel):
    tenant: TenantContext
    intent_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    prior_ref: ContentCampaignExactRef | None = None
    lifecycle: IntentLifecycle
    campaign_ref: ContentCampaignExactRef
    brief_ref: ContentCampaignExactRef | None = None
    master_artifact_ref: ContentCampaignExactRef | None = None
    channel_ids: list[str] = Field(min_length=1, max_length=20)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("intent createdAt must include a timezone")
        return value

    @field_validator("channel_ids")
    @classmethod
    def _unique_channels(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(not item.strip() for item in value):
            raise ValueError("channelIds must be unique and non-blank")
        return value

    @model_validator(mode="after")
    def _intent_integrity(self) -> MasterContentIntentRevision:
        if self.version != self.revision:
            raise ValueError("intent version must equal revision")
        if (self.revision == 1) != (self.prior_ref is None):
            raise ValueError("intent revisions after r1 require priorRef")
        _require_type(self.prior_ref, {"MasterContentIntentRevision"}, "priorRef")
        if self.prior_ref is not None:
            if self.prior_ref.resource_id != self.intent_id:
                raise ValueError("priorRef must target the same intent")
            if self.prior_ref.revision != self.revision - 1:
                raise ValueError("priorRef must target the preceding revision")
        _require_type(self.campaign_ref, {"CampaignRevision"}, "campaignRef")
        _require_type(self.brief_ref, {"TaskBriefRevision"}, "briefRef")
        _require_type(
            self.master_artifact_ref, {"ArtifactRevision"}, "masterArtifactRef"
        )
        return self


class ContentCampaignAuthorityReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str = Field(min_length=1, max_length=200)
    operation: str = Field(pattern=r"^content_campaign[.][a-z_]+$")
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_ref: ContentCampaignExactRef
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("authority Receipt createdAt must include a timezone")
        return value


__all__ = [
    "CalendarDecisionRevision",
    "CalendarDecisionType",
    "CalendarEntryRevision",
    "CalendarLifecycle",
    "CampaignLifecycle",
    "CampaignRevision",
    "ContentCampaignAuthorityReceipt",
    "ContentCampaignExactRef",
    "DstResolution",
    "IntentLifecycle",
    "MasterContentIntentRevision",
]
