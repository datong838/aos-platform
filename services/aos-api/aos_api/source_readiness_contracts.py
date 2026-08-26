"""Canonical, tenant-scoped SourceReadiness public contracts.

The contract intentionally separates observed facts from policy-backed
readiness.  A successful Pipeline run never implies READY when an exact
policy, schema, mapping, capability, freshness or reconciliation reference is
missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


SOURCE_READINESS_SCHEMA_VERSION = "aos.source-readiness/v1"


@dataclass(frozen=True, slots=True)
class CanonicalSource:
    pipeline_id: str
    object_type: str
    mapping_file: str


CANONICAL_QYH_SOURCES: tuple[CanonicalSource, ...] = (
    CanonicalSource("P01-shop-qyh", "Shop", "p01-shop.yaml"),
    CanonicalSource("P02-product-qyh", "Product", "p02-product.yaml"),
    CanonicalSource("P03-product-sku-qyh", "ProductSku", "p03-product-sku.yaml"),
    CanonicalSource("P04-category-qyh", "Category", "p04-category.yaml"),
    CanonicalSource("P05-order-qyh", "Order", "p05-order.yaml"),
    CanonicalSource("P06-order-line-qyh", "OrderLine", "p06-order-line.yaml"),
    CanonicalSource("P07-shipment-qyh", "Shipment", "p07-shipment.yaml"),
    CanonicalSource("P08-customer-lite-qyh", "CustomerLite", "p08-customer-lite.yaml"),
    CanonicalSource("P09-weapp-qyh", "Weapp", "p09-weapp.yaml"),
    CanonicalSource("P10-system-config-qyh", "SystemConfig", "p10-system-config.yaml"),
    CanonicalSource("P11-product-review-qyh", "ProductReview", "p11-product-review.yaml"),
    CanonicalSource("P12-payment-qyh", "Payment", "p12-payment.yaml"),
)
CANONICAL_QYH_PIPELINE_IDS = tuple(source.pipeline_id for source in CANONICAL_QYH_SOURCES)


class SourceReadinessStatus(StrEnum):
    READY = "ready"
    EMPTY = "empty"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"
    STALE = "stale"
    FAILED = "failed"
    BLOCKED = "blocked"
    FORBIDDEN = "forbidden"


class ObservationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RUNNING = "running"
    UNKNOWN = "unknown"


class PolicyCheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


_STATUS_PRECEDENCE = {
    SourceReadinessStatus.READY: 0,
    SourceReadinessStatus.EMPTY: 1,
    SourceReadinessStatus.DEGRADED: 2,
    SourceReadinessStatus.UNKNOWN: 3,
    SourceReadinessStatus.STALE: 4,
    SourceReadinessStatus.FAILED: 5,
    SourceReadinessStatus.BLOCKED: 6,
    SourceReadinessStatus.FORBIDDEN: 7,
}


def aggregate_source_readiness_status(
    statuses: list[SourceReadinessStatus] | tuple[SourceReadinessStatus, ...],
) -> SourceReadinessStatus:
    """Return the strictest status; an empty input is UNKNOWN."""
    if not statuses:
        return SourceReadinessStatus.UNKNOWN
    return max(statuses, key=_STATUS_PRECEDENCE.__getitem__)


class ExactResourceRef(AipContractModel):
    resource_type: str
    resource_id: str
    revision: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority: str

    @field_validator("resource_type", "resource_id", "revision", "authority")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("exact resource reference fields must not be empty")
        return cleaned


class LatestRunObservation(AipContractModel):
    run_id: str | None = None
    status: ObservationStatus = ObservationStatus.UNKNOWN
    scheduled_for: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    rows_written: int | None = Field(default=None, ge=0)
    error_code: str | None = None


class SourceCounts(AipContractModel):
    source_total: int | None = Field(default=None, ge=0)
    source_active: int | None = Field(default=None, ge=0)
    source_deleted: int | None = Field(default=None, ge=0)
    projection_total: int | None = Field(default=None, ge=0)
    unexplained_delta: int | None = None


class PolicyObservation(AipContractModel):
    status: PolicyCheckStatus = PolicyCheckStatus.UNKNOWN
    rule_ref: ExactResourceRef | None = None
    summary: str | None = None


class SourceReadinessItem(AipContractModel):
    schema_version: str = SOURCE_READINESS_SCHEMA_VERSION
    tenant: TenantContext
    source_id: str
    pipeline_id: str
    object_type: str
    status: SourceReadinessStatus
    checked_at: datetime
    observed_at: datetime | None = None
    source_event_at: datetime | None = None
    projected_at: datetime | None = None
    data_cutoff: datetime | None = None
    freshness_expires_at: datetime | None = None
    source_config_ref: ExactResourceRef | None = None
    mapping_ref: ExactResourceRef | None = None
    schema_ref: ExactResourceRef | None = None
    masking_policy_ref: ExactResourceRef | None = None
    freshness_policy_ref: ExactResourceRef | None = None
    quality_policy_ref: ExactResourceRef | None = None
    reconciliation_policy_ref: ExactResourceRef | None = None
    query_capability_ref: ExactResourceRef | None = None
    latest_run: LatestRunObservation = Field(default_factory=LatestRunObservation)
    counts: SourceCounts = Field(default_factory=SourceCounts)
    quality: PolicyObservation = Field(default_factory=PolicyObservation)
    reconciliation: PolicyObservation = Field(default_factory=PolicyObservation)
    reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    @field_validator("source_id", "pipeline_id", "object_type")
    @classmethod
    def _required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("source identity fields must not be empty")
        return cleaned

    @model_validator(mode="after")
    def _ready_requires_exact_authority(self) -> Self:
        if self.status != SourceReadinessStatus.READY:
            return self
        required = {
            "sourceConfigRef": self.source_config_ref,
            "mappingRef": self.mapping_ref,
            "schemaRef": self.schema_ref,
            "maskingPolicyRef": self.masking_policy_ref,
            "freshnessPolicyRef": self.freshness_policy_ref,
            "qualityPolicyRef": self.quality_policy_ref,
            "reconciliationPolicyRef": self.reconciliation_policy_ref,
            "queryCapabilityRef": self.query_capability_ref,
        }
        missing = sorted(name for name, value in required.items() if value is None)
        if missing:
            raise ValueError("ready source is missing exact refs: " + ",".join(missing))
        if self.quality.status != PolicyCheckStatus.PASS:
            raise ValueError("ready source requires quality pass")
        if self.reconciliation.status != PolicyCheckStatus.PASS:
            raise ValueError("ready source requires reconciliation pass")
        if self.latest_run.status != ObservationStatus.SUCCEEDED:
            raise ValueError("ready source requires a succeeded latest run")
        if self.freshness_expires_at is None or self.data_cutoff is None:
            raise ValueError("ready source requires freshness expiry and data cutoff")
        if self.blockers:
            raise ValueError("ready source must not contain blockers")
        return self


class InvestigationReadinessBlockerProjection(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    fact: str | None = Field(default=None, max_length=160)
    source_ids: list[str] = Field(default_factory=list, max_length=50)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("source_ids")
    @classmethod
    def _unique_sources(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("blocker sourceIds must be non-empty and unique")
        return cleaned


class InvestigationReadinessProjection(AipContractModel):
    requirement_ref: ExactResourceRef
    status: SourceReadinessStatus
    evaluated_at: datetime
    required_cutoff: datetime
    freshness_expires_at: datetime | None = None
    required_fact_count: int = Field(ge=1)
    covered_fact_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0, le=1)
    unmet_facts: list[str] = Field(default_factory=list, max_length=100)
    blockers: list[InvestigationReadinessBlockerProjection] = Field(
        default_factory=list, max_length=100
    )

    @field_validator("unmet_facts")
    @classmethod
    def _unique_facts(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("unmetFacts must be non-empty and unique")
        return cleaned

    @model_validator(mode="after")
    def _coverage_is_honest(self) -> Self:
        if self.requirement_ref.resource_type != "DataRequirementRevision":
            raise ValueError("requirementRef must be a DataRequirementRevision")
        if self.covered_fact_count > self.required_fact_count:
            raise ValueError("coveredFactCount exceeds requiredFactCount")
        expected = self.covered_fact_count / self.required_fact_count
        if abs(self.coverage_ratio - expected) > 1e-9:
            raise ValueError("coverageRatio does not match fact counts")
        if self.covered_fact_count == self.required_fact_count:
            if self.unmet_facts:
                raise ValueError("complete coverage cannot contain unmetFacts")
        elif not self.unmet_facts:
            raise ValueError("partial coverage requires unmetFacts")
        if self.status == SourceReadinessStatus.READY:
            if self.coverage_ratio != 1 or self.blockers:
                raise ValueError("ready investigation requires full coverage and no blockers")
            if self.freshness_expires_at is None or self.freshness_expires_at <= self.evaluated_at:
                raise ValueError("ready investigation requires unexpired freshness")
        return self


class SourceReadinessEnvelope(AipContractModel):
    schema_version: str = SOURCE_READINESS_SCHEMA_VERSION
    tenant: TenantContext
    checked_at: datetime
    cutoff_at: datetime
    status: SourceReadinessStatus
    sources: list[SourceReadinessItem]
    receipt_ref: ExactResourceRef | None = None
    investigation: InvestigationReadinessProjection | None = None

    @model_validator(mode="after")
    def _validate_atomic_canonical_set(self) -> Self:
        pipeline_ids = tuple(item.pipeline_id for item in self.sources)
        if pipeline_ids != CANONICAL_QYH_PIPELINE_IDS:
            raise ValueError("sources must be the ordered, unique canonical P01-P12 set")
        if any(item.tenant != self.tenant for item in self.sources):
            raise ValueError("every source must use the envelope tenant")
        if any(item.checked_at != self.checked_at for item in self.sources):
            raise ValueError("every source must share the envelope checkedAt")
        aggregate = aggregate_source_readiness_status(
            [item.status for item in self.sources]
        )
        if self.status != aggregate:
            raise ValueError("envelope status must equal strict source aggregate")
        if self.investigation is not None:
            projection = self.investigation
            if projection.evaluated_at != self.checked_at:
                raise ValueError("investigation evaluatedAt must equal envelope checkedAt")
            if projection.required_cutoff > self.cutoff_at:
                raise ValueError("investigation requiredCutoff exceeds envelope cutoffAt")
            if (
                projection.status == SourceReadinessStatus.READY
                and self.status != SourceReadinessStatus.READY
            ):
                raise ValueError("historical investigation success cannot override current envelope")
        return self
