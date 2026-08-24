"""Strict read-only contracts for the ecommerce creator-growth view."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


CREATOR_GROWTH_SCHEMA_VERSION = "aos.ecommerce-workshop.creator-growth-view/v1"


class CreatorWorkflowPhase(StrEnum):
    DISCOVERY = "discovery"
    EVIDENCE = "evidence"
    MATCHING = "matching"
    BATCH_PREPARE = "batch_prepare"
    START = "start"


class CreatorBusinessStage(StrEnum):
    CANDIDATE = "candidate"
    OUTREACH = "outreach"
    CONTRACT = "contract"
    DELIVERY = "delivery"
    RELATIONSHIP = "relationship"


class CreatorGrowthSliceStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class CreatorGrowthAuthorityRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str = Field(min_length=1, max_length=200)
    workflow_phase: CreatorWorkflowPhase
    business_stage: CreatorBusinessStage
    pii_refs: list[str] = Field(default_factory=list, max_length=20)


class CreatorGrowthBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=160)
    required_action: str = Field(min_length=1, max_length=500)


class CreatorGrowthCountLedger(AipContractModel):
    input: int = Field(ge=0)
    eligible: int = Field(ge=0)
    excluded: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    unknown: int = Field(ge=0)
    deduplicated: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves_population(self) -> CreatorGrowthCountLedger:
        total = (
            self.eligible
            + self.excluded
            + self.needs_review
            + self.unknown
            + self.deduplicated
        )
        if self.input != total:
            raise ValueError("input must equal creator-growth population partitions")
        return self


class CreatorGrowthSlice(AipContractModel):
    business_stage: CreatorBusinessStage
    workflow_phases: list[CreatorWorkflowPhase] = Field(min_length=1, max_length=5)
    status: CreatorGrowthSliceStatus
    data_cutoff: datetime
    authority_refs: list[CreatorGrowthAuthorityRef] = Field(max_length=100)
    blockers: list[CreatorGrowthBlocker] = Field(max_length=20)
    count_ledger: CreatorGrowthCountLedger

    @field_validator("data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("creator-growth timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _fails_closed(self) -> CreatorGrowthSlice:
        if len(set(self.workflow_phases)) != len(self.workflow_phases):
            raise ValueError("workflow phases must be unique")
        identities = [
            (
                item.resource_type,
                item.resource_id,
                item.revision,
                item.content_hash,
                item.receipt_id,
            )
            for item in self.authority_refs
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("creator-growth authority identities must be unique")
        if len({item.code for item in self.blockers}) != len(self.blockers):
            raise ValueError("creator-growth blocker codes must be unique")
        if any(item.business_stage is not self.business_stage for item in self.authority_refs):
            raise ValueError("authority businessStage must match its slice")
        if self.status is CreatorGrowthSliceStatus.READY:
            if self.blockers:
                raise ValueError("ready creator-growth slices cannot have blockers")
            if self.count_ledger.eligible != len(self.authority_refs):
                raise ValueError("eligible must equal attached authority refs")
        elif not self.blockers or self.authority_refs:
            raise ValueError("blocked creator-growth slices require blockers and no refs")
        return self


class CreatorGrowthPageInfo(AipContractModel):
    limit: Literal[100] = 100
    count: int = Field(ge=0, le=500)
    has_more: Literal[False] = False
    next_cursor: None = None


class WorkshopCreatorGrowthViewEnvelope(AipContractModel):
    schema_version: Literal[CREATOR_GROWTH_SCHEMA_VERSION] = CREATOR_GROWTH_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    data_cutoff: datetime
    readiness: Literal["degraded"] = "degraded"
    slices: list[CreatorGrowthSlice] = Field(min_length=5, max_length=5)
    page: CreatorGrowthPageInfo

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("creator-growth timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _canonical_shape(self) -> WorkshopCreatorGrowthViewEnvelope:
        if [item.business_stage for item in self.slices] != list(CreatorBusinessStage):
            raise ValueError("creator-growth slices require canonical business-stage order")
        if any(item.data_cutoff != self.data_cutoff for item in self.slices):
            raise ValueError("creator-growth slices require one data cutoff")
        if self.page.count != sum(len(item.authority_refs) for item in self.slices):
            raise ValueError("page count must equal attached authority refs")
        return self


__all__ = [
    "CREATOR_GROWTH_SCHEMA_VERSION",
    "CreatorBusinessStage",
    "CreatorGrowthAuthorityRef",
    "CreatorGrowthBlocker",
    "CreatorGrowthCountLedger",
    "CreatorGrowthPageInfo",
    "CreatorGrowthSlice",
    "CreatorGrowthSliceStatus",
    "CreatorWorkflowPhase",
    "WorkshopCreatorGrowthViewEnvelope",
]
