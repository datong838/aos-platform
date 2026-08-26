"""Strict BI-W2 DataRequirement authority records.

These DTOs freeze the tenant-bound revision, head and fulfillment shapes.  They
do not register routes, open a store, run a migration or authorize real data
access.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import (
    DataRequirementStatus,
    FulfillmentStatus,
    InvestigationBlocker,
    InvestigationExactRef,
)


DATA_REQUIREMENT_AUTHORITY_SCHEMA_VERSION = "aos.data-requirement-authority/v1"
DATA_REQUIREMENT_HEAD_SCHEMA_VERSION = "aos.data-requirement-head/v1"
DATA_FULFILLMENT_AUTHORITY_RECEIPT_SCHEMA_VERSION = (
    "aos.data-fulfillment-authority-receipt/v1"
)

_OUTPUT_TYPES = {
    "DatasetRevision",
    "DataProductRevision",
    "OntologyHydrationRevision",
    "EvidenceBundleRevision",
}
_ARTIFACT_TYPES = {
    "DatasetRevision",
    "DataProductRevision",
    "OntologyHydrationRevision",
    "EvidenceBundleRevision",
}


def _aware(value: datetime, name: str) -> datetime:
    if value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return value


def _require_type(
    ref: InvestigationExactRef | None,
    expected: set[str],
    name: str,
) -> None:
    if ref is not None and ref.resource_type not in expected:
        raise ValueError(f"{name} must reference {sorted(expected)}")


def _unique(values: list[str], name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")


class DataRequirementTimeWindow(AipContractModel):
    start_at: datetime
    end_at: datetime

    @field_validator("start_at", "end_at")
    @classmethod
    def _aware_time(cls, value: datetime, info) -> datetime:
        return _aware(value, info.field_name)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_at <= self.start_at:
            raise ValueError("timeWindow endAt must be after startAt")
        return self


class DataRequirementRevisionRecord(AipContractModel):
    schema_version: str = DATA_REQUIREMENT_AUTHORITY_SCHEMA_VERSION
    tenant: TenantContext
    requirement_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    prior_ref: InvestigationExactRef | None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: DataRequirementStatus
    case_ref: InvestigationExactRef
    run_ref: InvestigationExactRef
    checkpoint_ref: InvestigationExactRef
    purpose_code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,119}$")
    channel_ref: InvestigationExactRef
    entity_ref: InvestigationExactRef
    required_facts: list[str] = Field(min_length=1, max_length=100)
    time_window: DataRequirementTimeWindow
    grain: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    cutoff_at: datetime
    freshness_max_age_seconds: int = Field(ge=1, le=31_536_000)
    quality_threshold: float = Field(ge=0, le=1)
    markings: list[str] = Field(default_factory=list, max_length=50)
    pii_allowed: bool = False
    min_population: int = Field(ge=1)
    acceptable_degradation: list[str] = Field(default_factory=list, max_length=50)
    requested_outputs: list[str] = Field(min_length=1, max_length=20)
    budget_minor: int = Field(ge=0)
    expires_at: datetime
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)

    @field_validator("cutoff_at", "expires_at", "created_at")
    @classmethod
    def _aware_times(cls, value: datetime, info) -> datetime:
        return _aware(value, info.field_name)

    @field_validator(
        "required_facts",
        "markings",
        "acceptable_degradation",
        "requested_outputs",
    )
    @classmethod
    def _unique_lists(cls, value: list[str], info) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError(f"{info.field_name} entries must not be empty")
        _unique(cleaned, info.field_name)
        return cleaned

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != DATA_REQUIREMENT_AUTHORITY_SCHEMA_VERSION:
            raise ValueError("unsupported DataRequirement authority schemaVersion")
        _require_type(self.case_ref, {"BusinessInvestigationCaseRevision"}, "caseRef")
        _require_type(self.run_ref, {"BusinessInvestigationRun"}, "runRef")
        _require_type(self.checkpoint_ref, {"CheckpointRevision"}, "checkpointRef")
        _require_type(self.channel_ref, {"ChannelRevision"}, "channelRef")
        _require_type(self.entity_ref, {"BusinessEntityRevision"}, "entityRef")
        if (self.revision == 1) != (self.prior_ref is None):
            raise ValueError("priorRef is absent only for revision 1")
        if self.prior_ref is not None:
            _require_type(self.prior_ref, {"DataRequirementRevision"}, "priorRef")
            if self.prior_ref.resource_id != self.requirement_id:
                raise ValueError("priorRef must retain requirementId")
            if self.prior_ref.revision != self.revision - 1:
                raise ValueError("priorRef must target the preceding revision")
        if self.time_window.end_at > self.cutoff_at:
            raise ValueError("timeWindow must not extend beyond cutoffAt")
        if self.cutoff_at > self.created_at:
            raise ValueError("cutoffAt must not be after createdAt")
        if self.expires_at <= self.created_at:
            raise ValueError("expiresAt must be after createdAt")
        if any(item not in _OUTPUT_TYPES for item in self.requested_outputs):
            raise ValueError("requestedOutputs contains a non-canonical output type")
        if self.status in {
            DataRequirementStatus.REJECTED,
            DataRequirementStatus.UNKNOWN,
        } and not self.blockers:
            raise ValueError("rejected or unknown requirement requires a blocker")
        return self


class DataRequirementHeadRecord(AipContractModel):
    schema_version: str = DATA_REQUIREMENT_HEAD_SCHEMA_VERSION
    tenant: TenantContext
    requirement_id: str = Field(min_length=1, max_length=200)
    current_revision: int = Field(ge=1)
    current_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: DataRequirementStatus
    version: int = Field(ge=1)
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def _aware_updated_at(cls, value: datetime) -> datetime:
        return _aware(value, "updatedAt")

    @model_validator(mode="after")
    def _schema(self) -> Self:
        if self.schema_version != DATA_REQUIREMENT_HEAD_SCHEMA_VERSION:
            raise ValueError("unsupported DataRequirement head schemaVersion")
        return self


class DataFulfillmentReceiptRecord(AipContractModel):
    schema_version: str = DATA_FULFILLMENT_AUTHORITY_RECEIPT_SCHEMA_VERSION
    tenant: TenantContext
    fulfillment_id: str = Field(min_length=1, max_length=200)
    receipt_id: str = Field(min_length=1, max_length=200)
    requirement_ref: InvestigationExactRef
    status: FulfillmentStatus
    artifact_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=200)
    source_readiness_ref: InvestigationExactRef
    cutoff_at: datetime
    fulfilled_at: datetime
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)

    @field_validator("cutoff_at", "fulfilled_at")
    @classmethod
    def _aware_times(cls, value: datetime, info) -> datetime:
        return _aware(value, info.field_name)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != DATA_FULFILLMENT_AUTHORITY_RECEIPT_SCHEMA_VERSION:
            raise ValueError("unsupported fulfillment authority receipt schemaVersion")
        _require_type(self.requirement_ref, {"DataRequirementRevision"}, "requirementRef")
        _require_type(
            self.source_readiness_ref,
            {"SourceReadinessEnvelope"},
            "sourceReadinessRef",
        )
        if self.source_readiness_ref.receipt_id is None:
            raise ValueError("sourceReadinessRef requires receiptId")
        keys: list[str] = []
        for ref in self.artifact_refs:
            _require_type(ref, _ARTIFACT_TYPES, "artifactRefs")
            keys.append(
                f"{ref.resource_type}:{ref.resource_id}:{ref.revision}:{ref.content_hash}"
            )
        _unique(keys, "artifactRefs")
        if self.fulfilled_at < self.cutoff_at:
            raise ValueError("fulfilledAt must not be before cutoffAt")
        if self.status is FulfillmentStatus.FULFILLED:
            if not self.artifact_refs or self.blockers:
                raise ValueError("fulfilled receipt requires exact artifacts and no blockers")
        elif not self.blockers:
            raise ValueError("non-fulfilled receipt requires a blocker")
        return self
