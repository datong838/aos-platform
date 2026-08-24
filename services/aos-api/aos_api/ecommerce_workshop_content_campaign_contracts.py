"""Strict read-only contracts for the ecommerce content-campaign view."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


CONTENT_CAMPAIGN_SCHEMA_VERSION = "aos.ecommerce-workshop.content-campaign-view/v1"


class ContentCampaignReadiness(StrEnum):
    DEGRADED = "degraded"


class ContentCampaignSliceId(StrEnum):
    PLAN = "plan"
    CALENDAR = "calendar"
    CONTENT = "content"


class ContentCampaignSliceStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class ContentCampaignAuthorityRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str = Field(min_length=1, max_length=200)


class ContentCampaignBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=160)
    required_action: str = Field(min_length=1, max_length=500)


class ContentCampaignCountLedger(AipContractModel):
    eligible: int = Field(ge=0)
    attached: int = Field(ge=0)
    unmatched: int = Field(ge=0)
    conflicted: int = Field(ge=0)

    @model_validator(mode="after")
    def _counts_reconcile(self) -> ContentCampaignCountLedger:
        if self.eligible != self.attached + self.unmatched + self.conflicted:
            raise ValueError("eligible must equal attached + unmatched + conflicted")
        return self


class ContentCampaignSlice(AipContractModel):
    slice_id: ContentCampaignSliceId
    status: ContentCampaignSliceStatus
    data_cutoff: datetime
    authority_refs: list[ContentCampaignAuthorityRef] = Field(max_length=20)
    items: list[ContentCampaignAuthorityRef] = Field(max_length=100)
    blockers: list[ContentCampaignBlocker] = Field(max_length=20)
    count_ledger: ContentCampaignCountLedger

    @field_validator("data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("content-campaign timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _evidence_matches_status(self) -> ContentCampaignSlice:
        if self.count_ledger.attached != len(self.items):
            raise ValueError("attached must equal item count")
        if self.status is ContentCampaignSliceStatus.READY:
            if not self.authority_refs or self.blockers:
                raise ValueError("ready slices require authorityRefs and no blockers")
        else:
            if not self.blockers:
                raise ValueError("blocked slices require at least one blocker")
            if self.items:
                raise ValueError("blocked slices cannot expose unverified items")
        return self


class ContentCampaignPageInfo(AipContractModel):
    limit: int = Field(ge=1, le=100)
    count: int = Field(ge=0, le=300)
    has_more: bool
    next_cursor: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def _cursor_matches_more(self) -> ContentCampaignPageInfo:
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("hasMore and nextCursor must agree")
        return self


class WorkshopContentCampaignViewEnvelope(AipContractModel):
    schema_version: Literal[CONTENT_CAMPAIGN_SCHEMA_VERSION] = (
        CONTENT_CAMPAIGN_SCHEMA_VERSION
    )
    tenant: TenantContext
    evaluated_at: datetime
    data_cutoff: datetime
    readiness: Literal[ContentCampaignReadiness.DEGRADED] = (
        ContentCampaignReadiness.DEGRADED
    )
    slices: list[ContentCampaignSlice] = Field(min_length=3, max_length=3)
    page: ContentCampaignPageInfo

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("content-campaign timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _canonical_shape(self) -> WorkshopContentCampaignViewEnvelope:
        if [item.slice_id for item in self.slices] != list(ContentCampaignSliceId):
            raise ValueError("content-campaign slices require canonical order")
        attached = sum(item.count_ledger.attached for item in self.slices)
        if self.page.count != attached:
            raise ValueError("page count must equal attached slice items")
        if self.page.has_more or self.page.next_cursor is not None:
            raise ValueError("W2-03A shell cannot expose a synthetic cursor")
        return self


__all__ = [
    "CONTENT_CAMPAIGN_SCHEMA_VERSION",
    "ContentCampaignAuthorityRef",
    "ContentCampaignBlocker",
    "ContentCampaignCountLedger",
    "ContentCampaignPageInfo",
    "ContentCampaignReadiness",
    "ContentCampaignSlice",
    "ContentCampaignSliceId",
    "ContentCampaignSliceStatus",
    "WorkshopContentCampaignViewEnvelope",
]
