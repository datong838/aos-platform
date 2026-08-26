"""Strict BI-W1 shared contracts for Business Investigation.

This module is DTO-only.  It reuses the existing TenantContext and references
canonical SourceReadiness, Analyst and Task authorities by exact ref.  Importing
it does not register routes, allocate stores, execute migrations or enable a
feature flag.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, StrictInt, StrictStr, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


BUSINESS_INVESTIGATION_SHARED_SCHEMA_VERSION = "aos.business-investigation.shared/v1"
DATA_REQUIREMENT_SCHEMA_VERSION = "aos.data-requirement/v1"
DATA_FULFILLMENT_SCHEMA_VERSION = "aos.data-fulfillment-receipt/v1"
PLATFORM_OBSERVATION_SCHEMA_VERSION = "aos.platform-observation/v1"
SOURCE_MAPPING_SCHEMA_VERSION = "aos.source-mapping/v1"
ADAPTIVE_PROFILE_SCHEMA_VERSION = "aos.adaptive-profile/v1"
SEMANTIC_HYDRATION_SCHEMA_VERSION = "aos.semantic-hydration-receipt/v1"


def _aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value


class InvestigationExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=240)
    revision: StrictInt | StrictStr
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str | None = Field(default=None, min_length=1, max_length=240)

    @field_validator("resource_type", "resource_id")
    @classmethod
    def _trim_identity(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("exact ref identity must not be empty")
        return cleaned

    @field_validator("revision")
    @classmethod
    def _valid_revision(cls, value: StrictInt | StrictStr) -> StrictInt | StrictStr:
        if isinstance(value, int):
            if value < 1:
                raise ValueError("exact ref integer revision must be >= 1")
            return value
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 160:
            raise ValueError("exact ref string revision must be non-empty and bounded")
        return cleaned


def _require_type(ref: InvestigationExactRef, expected: set[str], name: str) -> None:
    if ref.resource_type not in expected:
        raise ValueError(f"{name} must reference {sorted(expected)}")


class InvestigationPlatform(StrEnum):
    NIUSHOP = "niushop"
    WECHAT_STORE = "wechat_store"
    DOUYIN_STORE = "douyin_store"


class InvestigationReadinessStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    STALE = "stale"
    UNKNOWN = "unknown"


class InvestigationFreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class BlockerSeverity(StrEnum):
    WARNING = "warning"
    BLOCKING = "blocking"


class InvestigationBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    severity: BlockerSeverity
    dependency: str = Field(min_length=1, max_length=160)
    required_action: str = Field(min_length=1, max_length=500)


class ChannelContract(AipContractModel):
    channel_id: str = Field(min_length=1, max_length=200)
    platform: InvestigationPlatform
    display_name: str = Field(min_length=1, max_length=240)
    channel_ref: InvestigationExactRef

    @model_validator(mode="after")
    def _canonical_ref(self) -> Self:
        _require_type(self.channel_ref, {"ChannelRevision"}, "channelRef")
        if self.channel_ref.resource_id != self.channel_id:
            raise ValueError("channelRef must retain channelId")
        return self


class BusinessEntityContract(AipContractModel):
    business_entity_id: str = Field(min_length=1, max_length=200)
    entity_type: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=240)
    channel_ref: InvestigationExactRef

    @model_validator(mode="after")
    def _channel_ref_type(self) -> Self:
        _require_type(self.channel_ref, {"ChannelRevision"}, "channelRef")
        return self


class InvestigationCoverage(AipContractModel):
    required: int = Field(ge=0)
    fulfilled: int = Field(ge=0)
    unknown: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves_count(self) -> Self:
        if self.fulfilled + self.unknown > self.required:
            raise ValueError("coverage counts exceed required")
        return self


class InvestigationFreshness(AipContractModel):
    status: InvestigationFreshnessStatus
    data_cutoff: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("data_cutoff", "expires_at")
    @classmethod
    def _aware_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware(value)

    @model_validator(mode="after")
    def _fresh_is_bounded(self) -> Self:
        if self.status is InvestigationFreshnessStatus.FRESH:
            if self.data_cutoff is None or self.expires_at is None:
                raise ValueError("fresh readiness requires dataCutoff and expiresAt")
            if self.expires_at <= self.data_cutoff:
                raise ValueError("freshness expiry must be after data cutoff")
        return self


class InvestigationReadiness(AipContractModel):
    status: InvestigationReadinessStatus
    source_readiness_ref: InvestigationExactRef | None = None
    coverage: InvestigationCoverage
    freshness: InvestigationFreshness
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _fail_closed(self) -> Self:
        if self.source_readiness_ref is not None:
            _require_type(
                self.source_readiness_ref,
                {"SourceReadinessEnvelope"},
                "sourceReadinessRef",
            )
            if self.source_readiness_ref.receipt_id is None:
                raise ValueError("sourceReadinessRef requires receiptId")
        if self.status is InvestigationReadinessStatus.READY:
            complete = (
                self.source_readiness_ref is not None
                and self.coverage.fulfilled == self.coverage.required
                and self.coverage.unknown == 0
                and self.freshness.status is InvestigationFreshnessStatus.FRESH
                and not self.blockers
            )
            if not complete:
                raise ValueError("ready readiness requires exact, complete and fresh evidence")
        elif not self.blockers:
            raise ValueError("non-ready readiness requires an explicit blocker")
        return self


_ARTIFACT_TYPES = {
    "BusinessDossierRevision",
    "ProblemMapRevision",
    "OpportunityMapRevision",
    "SolutionPortfolioRevision",
    "InsightRevision",
    "DecisionSummaryRevision",
    "GrowthPlanRevision",
    "TaskGraphRevision",
    "EcommerceEffectReviewRevision",
}


class BusinessInvestigationSharedEnvelope(AipContractModel):
    schema_version: str = BUSINESS_INVESTIGATION_SHARED_SCHEMA_VERSION
    tenant: TenantContext
    channel: ChannelContract
    business_entity: BusinessEntityContract
    case_ref: InvestigationExactRef
    run_ref: InvestigationExactRef
    readiness: InvestigationReadiness
    artifact_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def _canonical_refs(self) -> Self:
        if self.schema_version != BUSINESS_INVESTIGATION_SHARED_SCHEMA_VERSION:
            raise ValueError("unsupported shared schemaVersion")
        _require_type(self.case_ref, {"BusinessInvestigationCaseRevision"}, "caseRef")
        _require_type(self.run_ref, {"BusinessInvestigationRun"}, "runRef")
        if self.business_entity.channel_ref != self.channel.channel_ref:
            raise ValueError("businessEntity channelRef must equal channel channelRef")
        keys: set[tuple[str, str, StrictInt | StrictStr, str]] = set()
        for ref in self.artifact_refs:
            _require_type(ref, _ARTIFACT_TYPES, "artifactRefs")
            key = (ref.resource_type, ref.resource_id, ref.revision, ref.content_hash)
            if key in keys:
                raise ValueError("artifactRefs must be unique")
            keys.add(key)
        return self


class DataRequirementStatus(StrEnum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    PLANNED = "planned"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class DataRequirementContract(AipContractModel):
    schema_version: str = DATA_REQUIREMENT_SCHEMA_VERSION
    tenant: TenantContext
    requirement_id: str = Field(min_length=1, max_length=200)
    case_ref: InvestigationExactRef
    run_ref: InvestigationExactRef
    purpose: str = Field(min_length=1, max_length=1000)
    fact_types: list[str] = Field(min_length=1, max_length=100)
    status: DataRequirementStatus
    requested_at: datetime
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)

    @field_validator("requested_at")
    @classmethod
    def _requested_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != DATA_REQUIREMENT_SCHEMA_VERSION:
            raise ValueError("unsupported data requirement schemaVersion")
        _require_type(self.case_ref, {"BusinessInvestigationCaseRevision"}, "caseRef")
        _require_type(self.run_ref, {"BusinessInvestigationRun"}, "runRef")
        if len(set(self.fact_types)) != len(self.fact_types):
            raise ValueError("factTypes must be unique")
        if self.status in {DataRequirementStatus.REJECTED, DataRequirementStatus.UNKNOWN} and not self.blockers:
            raise ValueError("rejected or unknown requirement requires blockers")
        return self


class FulfillmentStatus(StrEnum):
    FULFILLED = "fulfilled"
    PARTIAL = "partial"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class DataFulfillmentReceiptContract(AipContractModel):
    schema_version: str = DATA_FULFILLMENT_SCHEMA_VERSION
    tenant: TenantContext
    fulfillment_id: str = Field(min_length=1, max_length=200)
    requirement_ref: InvestigationExactRef
    status: FulfillmentStatus
    artifact_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=200)
    fulfilled_at: datetime
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)

    @field_validator("fulfilled_at")
    @classmethod
    def _fulfilled_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != DATA_FULFILLMENT_SCHEMA_VERSION:
            raise ValueError("unsupported fulfillment schemaVersion")
        _require_type(self.requirement_ref, {"DataRequirementRevision"}, "requirementRef")
        if self.status is FulfillmentStatus.FULFILLED:
            if not self.artifact_refs or self.blockers:
                raise ValueError("fulfilled receipt requires artifacts and no blockers")
        elif not self.blockers:
            raise ValueError("non-fulfilled receipt requires blockers")
        return self


class ObservationLifecycle(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
    RECONCILING = "reconciling"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ObservationContract(AipContractModel):
    schema_version: str = PLATFORM_OBSERVATION_SCHEMA_VERSION
    tenant: TenantContext
    observation_id: str = Field(min_length=1, max_length=200)
    status: ObservationLifecycle
    observed_at: datetime
    source_ref: InvestigationExactRef
    evidence_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=200)
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)

    @field_validator("observed_at")
    @classmethod
    def _observed_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != PLATFORM_OBSERVATION_SCHEMA_VERSION:
            raise ValueError("unsupported observation schemaVersion")
        _require_type(self.source_ref, {"PlatformSourceRevision"}, "sourceRef")
        if self.status is ObservationLifecycle.COMPLETED and not self.evidence_refs:
            raise ValueError("completed observation requires evidenceRefs")
        if self.status in {ObservationLifecycle.BLOCKED, ObservationLifecycle.UNKNOWN} and not self.blockers:
            raise ValueError("blocked or unknown observation requires blockers")
        return self


class SourceMappingContract(AipContractModel):
    schema_version: str = SOURCE_MAPPING_SCHEMA_VERSION
    tenant: TenantContext
    mapping_id: str = Field(min_length=1, max_length=200)
    observation_ref: InvestigationExactRef
    source_field: str = Field(min_length=1, max_length=500)
    canonical_field: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)
    confirmed_by: str | None = Field(default=None, min_length=1, max_length=200)
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != SOURCE_MAPPING_SCHEMA_VERSION:
            raise ValueError("unsupported source mapping schemaVersion")
        _require_type(self.observation_ref, {"PlatformObservation"}, "observationRef")
        return self


class AdaptiveProfileContract(AipContractModel):
    schema_version: str = ADAPTIVE_PROFILE_SCHEMA_VERSION
    tenant: TenantContext
    profile_id: str = Field(min_length=1, max_length=200)
    source_ref: InvestigationExactRef
    hypothesis_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=100)
    coverage: InvestigationCoverage
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != ADAPTIVE_PROFILE_SCHEMA_VERSION:
            raise ValueError("unsupported adaptive profile schemaVersion")
        _require_type(self.source_ref, {"PlatformSourceRevision"}, "sourceRef")
        keys: set[tuple[str, str, StrictInt | StrictStr, str]] = set()
        for ref in self.hypothesis_refs:
            _require_type(ref, {"SemanticHypothesisRevision"}, "hypothesisRefs")
            key = (ref.resource_type, ref.resource_id, ref.revision, ref.content_hash)
            if key in keys:
                raise ValueError("hypothesisRefs must be unique")
            keys.add(key)
        return self


class HydrationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class SemanticHydrationReceiptContract(AipContractModel):
    schema_version: str = SEMANTIC_HYDRATION_SCHEMA_VERSION
    tenant: TenantContext
    hydration_id: str = Field(min_length=1, max_length=200)
    status: HydrationStatus
    observation_ref: InvestigationExactRef
    mapping_ref: InvestigationExactRef
    output_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=200)
    hydrated_at: datetime
    blockers: list[InvestigationBlocker] = Field(default_factory=list, max_length=50)

    @field_validator("hydrated_at")
    @classmethod
    def _hydrated_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != SEMANTIC_HYDRATION_SCHEMA_VERSION:
            raise ValueError("unsupported hydration schemaVersion")
        _require_type(self.observation_ref, {"PlatformObservation"}, "observationRef")
        _require_type(self.mapping_ref, {"SourceMappingRevision"}, "mappingRef")
        if self.status is HydrationStatus.SUCCEEDED:
            if not self.output_refs or self.blockers:
                raise ValueError("succeeded hydration requires outputs and no blockers")
        elif not self.blockers:
            raise ValueError("non-succeeded hydration requires blockers")
        return self
