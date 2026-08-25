"""Strict read-only contracts for the ecommerce media-studio view."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_workshop_media_studio_lifecycle_contracts import (
    MediaStudioLifecycleContribution,
)
from aos_api.ecommerce_workshop_media_publish_contracts import MediaPublishContribution


MEDIA_STUDIO_LEGACY_SCHEMA_VERSION = "aos.ecommerce-workshop.media-studio-view/v1"
MEDIA_STUDIO_PROVIDER_SCHEMA_VERSION = "aos.ecommerce-workshop.media-studio-view/v2"
MEDIA_STUDIO_SCHEMA_VERSION = "aos.ecommerce-workshop.media-studio-view/v3"
MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION = "aos.ecommerce-workshop.media-studio-view/v4"
MEDIA_STUDIO_PUBLISH_SCHEMA_VERSION = "aos.ecommerce-workshop.media-studio-view/v5"


class MediaStudioSliceId(StrEnum):
    CONTEXT = "context"
    EXECUTION = "execution"
    DELIVERY = "delivery"


class MediaReadinessAxis(StrEnum):
    MODULE = "module"
    CAPABILITY = "capability"
    ASSIGNEE = "assignee"
    PROVIDER = "provider"
    BUDGET = "budget"
    PUBLICATION = "publication"


class MediaReadinessStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    TARGET = "target"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"
    NOT_APPLICABLE = "not_applicable"


class MediaExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str = Field(min_length=1, max_length=200)


class MediaBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=160)
    required_action: str = Field(min_length=1, max_length=500)


class MediaAxisReadiness(AipContractModel):
    axis: MediaReadinessAxis
    status: MediaReadinessStatus
    exact_ref: MediaExactRef | None = None
    target_contract_ref: str | None = Field(default=None, min_length=1, max_length=240)
    gaps: list[str] = Field(default_factory=list, max_length=20)
    blockers: list[MediaBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_status(self) -> MediaAxisReadiness:
        if self.status is MediaReadinessStatus.READY:
            if self.exact_ref is None or self.target_contract_ref or self.gaps or self.blockers:
                raise ValueError("ready media axis requires one exact ref and no target gaps")
        elif self.status is MediaReadinessStatus.TARGET:
            if self.exact_ref is not None or not self.target_contract_ref or not self.gaps or not self.blockers:
                raise ValueError("target media axis requires target contract, gaps and blockers")
        elif self.status in {MediaReadinessStatus.BLOCKED, MediaReadinessStatus.UNKNOWN, MediaReadinessStatus.CONFLICT}:
            if self.exact_ref is not None or not self.blockers:
                raise ValueError("non-ready media axis requires blockers and no exact ref")
        elif self.exact_ref is not None or self.blockers:
            raise ValueError("not-applicable media axis cannot attach authority or blockers")
        return self


class MediaCountLedger(AipContractModel):
    denominator: int = Field(ge=0)
    ready: int = Field(ge=0)
    target: int = Field(ge=0)
    blocked: int = Field(ge=0)
    unknown: int = Field(ge=0)
    conflict: int = Field(ge=0)
    not_applicable: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves_denominator(self) -> MediaCountLedger:
        if self.denominator != self.ready + self.target + self.blocked + self.unknown + self.conflict + self.not_applicable:
            raise ValueError("media denominator must equal all disjoint partitions")
        return self


class MediaStudioSlice(AipContractModel):
    slice_id: MediaStudioSliceId
    status: Literal["ready", "blocked"]
    data_cutoff: datetime
    readiness_axes: list[MediaAxisReadiness] = Field(min_length=6, max_length=6)
    authority_refs: list[MediaExactRef] = Field(default_factory=list, max_length=100)
    blockers: list[MediaBlocker] = Field(default_factory=list, max_length=20)
    count_ledger: MediaCountLedger

    @field_validator("data_cutoff")
    @classmethod
    def _aware_cutoff(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("media cutoff requires timezone")
        return value

    @model_validator(mode="after")
    def _canonical_and_fail_closed(self) -> MediaStudioSlice:
        if [item.axis for item in self.readiness_axes] != list(MediaReadinessAxis):
            raise ValueError("media readiness axes require canonical order")
        identities = [(item.resource_type, item.resource_id, item.revision, item.content_hash, item.receipt_id) for item in self.authority_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("media exact refs must be unique")
        if self.status == "ready" and (self.blockers or any(item.status in {MediaReadinessStatus.BLOCKED, MediaReadinessStatus.TARGET} for item in self.readiness_axes)):
            raise ValueError("ready media slice cannot hide blocked or target axes")
        if self.status == "blocked" and not self.blockers:
            raise ValueError("blocked media slice requires blockers")
        expected = {
            "ready": sum(item.status is MediaReadinessStatus.READY for item in self.readiness_axes),
            "target": sum(item.status is MediaReadinessStatus.TARGET for item in self.readiness_axes),
            "blocked": sum(item.status is MediaReadinessStatus.BLOCKED for item in self.readiness_axes),
            "unknown": sum(item.status is MediaReadinessStatus.UNKNOWN for item in self.readiness_axes),
            "conflict": sum(item.status is MediaReadinessStatus.CONFLICT for item in self.readiness_axes),
            "not_applicable": sum(item.status is MediaReadinessStatus.NOT_APPLICABLE for item in self.readiness_axes),
        }
        if any(getattr(self.count_ledger, key) != value for key, value in expected.items()):
            raise ValueError("media ledger must equal readiness axis partitions")
        return self


class MediaPageInfo(AipContractModel):
    limit: Literal[100] = 100
    count: int = Field(ge=0, le=300)
    has_more: Literal[False] = False
    next_cursor: None = None


class MediaProviderExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class MediaProviderJobContribution(AipContractModel):
    job_id: str = Field(min_length=1, max_length=200)
    status: str = Field(pattern=r"^(prepared|submitted|running|cancel_requested|unknown|succeeded|failed|cancelled)$")
    sequence: int = Field(ge=1)
    atomic_capability_ref: MediaProviderExactRef
    logic_ref: MediaProviderExactRef
    colleague_binding_ref: MediaProviderExactRef
    model_ref: MediaProviderExactRef
    provider_ref: MediaProviderExactRef
    adapter_ref: MediaProviderExactRef
    scan_refs: list[MediaProviderExactRef] = Field(min_length=1, max_length=64)
    primary_colleague: Literal["内容官"] = "内容官"
    collaborator_colleagues: list[str] = Field(default_factory=lambda: ["活动策划师", "数据参谋", "合规协作者"], min_length=1, max_length=10)
    blocker_codes: list[str] = Field(default_factory=list, max_length=64)
    external_effects_allowed: Literal[False] = False


class MediaFinanceBucketContribution(AipContractModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    measured_minor: int = Field(ge=0)
    estimated_minor: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    adjustment_minor: int
    refund_minor: int = Field(ge=0)
    residual_minor: int | None


class MediaFinanceContribution(AipContractModel):
    finance_id: str = Field(min_length=1, max_length=200)
    job_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    attempt_binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    capacity_reservation_ref: MediaProviderExactRef
    budget_reservation_ref: MediaProviderExactRef
    projected_min_minor: int = Field(ge=0)
    projected_max_minor: int = Field(ge=0)
    projected_currency: str = Field(pattern=r"^[A-Z]{3}$")
    reservations_active: bool
    cancel_outcome: str | None = Field(default=None, pattern=r"^(requested|accepted|too_late|unknown)$")
    fee_conclusion: str = Field(pattern=r"^(no_charge|chargeable|unknown)$")
    settlement_status: str = Field(pattern=r"^(pending|settled|disputed|written_off)$")
    currency_buckets: list[MediaFinanceBucketContribution] = Field(default_factory=list, max_length=20)
    blocker_codes: list[str] = Field(default_factory=list, max_length=64)
    external_effects_allowed: Literal[False] = False


class WorkshopMediaStudioViewEnvelope(AipContractModel):
    schema_version: Literal[MEDIA_STUDIO_PROVIDER_SCHEMA_VERSION, MEDIA_STUDIO_SCHEMA_VERSION, MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION, MEDIA_STUDIO_PUBLISH_SCHEMA_VERSION] = MEDIA_STUDIO_PUBLISH_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    data_cutoff: datetime
    readiness: Literal["degraded"] = "degraded"
    slices: list[MediaStudioSlice] = Field(min_length=3, max_length=3)
    provider_jobs_status: Literal["ready", "blocked"]
    provider_jobs: list[MediaProviderJobContribution] = Field(default_factory=list, max_length=100)
    provider_job_blockers: list[MediaBlocker] = Field(default_factory=list, max_length=20)
    media_finance_status: Literal["ready", "blocked"] = "blocked"
    media_finance: list[MediaFinanceContribution] = Field(default_factory=list, max_length=100)
    media_finance_blockers: list[MediaBlocker] = Field(default_factory=lambda: [MediaBlocker(code="MEDIA_FINANCE_LEGACY_VIEW", dependency="media-studio-v3", requiredAction="refresh canonical v3 projection")], max_length=20)
    lifecycle_status: Literal["ready", "blocked"] = "blocked"
    lifecycle: MediaStudioLifecycleContribution | None = None
    lifecycle_blockers: list[MediaBlocker] = Field(default_factory=lambda: [MediaBlocker(code="MEDIA_LIFECYCLE_LEGACY_VIEW", dependency="media-studio-v4", requiredAction="refresh canonical v4 projection")], max_length=20)
    publish_status: Literal["ready", "blocked"] = "blocked"
    publish_contributions: list[MediaPublishContribution] = Field(default_factory=list, max_length=100)
    publish_blockers: list[MediaBlocker] = Field(default_factory=lambda: [MediaBlocker(code="MEDIA_PUBLISH_LEGACY_VIEW", dependency="media-studio-v5", requiredAction="refresh canonical v5 projection")], max_length=20)
    page: MediaPageInfo

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("media timestamps require timezone")
        return value

    @model_validator(mode="after")
    def _canonical_shape(self) -> WorkshopMediaStudioViewEnvelope:
        if [item.slice_id for item in self.slices] != list(MediaStudioSliceId):
            raise ValueError("media slices require canonical order")
        if any(item.data_cutoff != self.data_cutoff for item in self.slices):
            raise ValueError("media slices require one cutoff")
        if self.page.count != sum(len(item.authority_refs) for item in self.slices):
            raise ValueError("media page count must equal exact refs")
        if self.provider_jobs_status == "ready" and self.provider_job_blockers:
            raise ValueError("ready provider jobs cannot contain blockers")
        if self.provider_jobs_status == "blocked" and not self.provider_job_blockers:
            raise ValueError("blocked provider jobs require blockers")
        if self.media_finance_status == "ready" and self.media_finance_blockers:
            raise ValueError("ready media finance cannot contain blockers")
        if self.media_finance_status == "blocked" and not self.media_finance_blockers:
            raise ValueError("blocked media finance requires blockers")
        if self.schema_version == MEDIA_STUDIO_PROVIDER_SCHEMA_VERSION and self.media_finance:
            raise ValueError("v2 media view cannot carry v3 finance contributions")
        if self.lifecycle_status == "ready" and (self.lifecycle is None or self.lifecycle_blockers):
            raise ValueError("ready media lifecycle requires one contribution and no blockers")
        if self.lifecycle_status == "blocked" and (self.lifecycle is not None or not self.lifecycle_blockers):
            raise ValueError("blocked media lifecycle requires blockers and no contribution")
        if self.schema_version != MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION and self.lifecycle is not None:
            if self.schema_version != MEDIA_STUDIO_PUBLISH_SCHEMA_VERSION:
                raise ValueError("legacy media view cannot carry v4 lifecycle contribution")
        if self.publish_status == "ready" and self.publish_blockers:
            raise ValueError("ready media publish projection cannot contain blockers")
        if self.publish_status == "blocked" and not self.publish_blockers:
            raise ValueError("blocked media publish projection requires blockers")
        if self.schema_version != MEDIA_STUDIO_PUBLISH_SCHEMA_VERSION and self.publish_contributions:
            raise ValueError("legacy media view cannot carry v5 publish contributions")
        return self


__all__ = [name for name in globals() if name.startswith("MEDIA_STUDIO") or name.startswith("Media") or name.startswith("Workshop")]
