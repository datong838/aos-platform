"""Deterministic quality checks over trusted, fixed-query Owner measurements.

This module neither queries data nor authenticates measurement provenance. It
must not be exposed as a public self-reported score/fulfillment API. The Host
must read the exact requirement and validate source/query lineage separately.
Version stamps name internal executable policies, not invented domain owners.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, TypeAdapter, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord, DataRequirementTimeWindow
from aos_api.data_requirement_store import canonical_revision_content_hash
from aos_api.tenant_scope import TenantScope

Count = Annotated[StrictInt, Field(ge=0, le=9_223_372_036_854_775_807)]


class MeasurementPolicyVersion(AipContractModel):
    identity: str = Field(min_length=1, max_length=200)
    revision: str = Field(min_length=1, max_length=160)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("identity", "revision")
    @classmethod
    def _identity(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("policy identity must be nonblank and canonical")
        return value


class FactQualityMeasurement(AipContractModel):
    fact_id: str = Field(min_length=1, max_length=200)
    observed_count: Count
    eligible_count: Count
    valid_count: Count
    excluded_count: Count
    duplicate_count: Count

    @model_validator(mode="after")
    def _counts(self) -> Self:
        if self.fact_id != self.fact_id.strip() or not self.fact_id.strip():
            raise ValueError("fact identity must be canonical")
        if self.observed_count != self.eligible_count + self.excluded_count + self.duplicate_count:
            raise ValueError("observed count must partition into eligible, excluded and duplicate")
        if self.valid_count > self.eligible_count:
            raise ValueError("valid count exceeds eligible population")
        return self


class ResolvedPopulationPolicy(AipContractModel):
    """Host-resolved policy inputs, never derived from a caller's measurement."""
    version: MeasurementPolicyVersion
    grain: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    population_unit: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")


class _QualityMeasurementBase(AipContractModel):
    tenant: TenantContext
    requirement_ref: InvestigationExactRef
    channel_ref: InvestigationExactRef
    entity_ref: InvestigationExactRef
    time_window: DataRequirementTimeWindow
    cutoff_at: datetime
    grain: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    source_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=200)
    query_version: MeasurementPolicyVersion
    rule_version: MeasurementPolicyVersion
    population_policy_version: MeasurementPolicyVersion
    population_unit: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    distinct_population_count: Count
    # Owner must supply the oldest observation among ALL required sources;
    # this is not the query's run timestamp nor the newest source's timestamp.
    source_observed_at: datetime
    measured_at: datetime
    facts: list[FactQualityMeasurement] = Field(max_length=100)

    @field_validator("cutoff_at", "source_observed_at", "measured_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("measurement timestamps require timezone")
        return value

    @model_validator(mode="after")
    def _shape(self) -> Self:
        for reference, kind in ((self.requirement_ref, "DataRequirementRevision"),
                                (self.channel_ref, "ChannelRevision"),
                                (self.entity_ref, "BusinessEntityRevision")):
            if reference.resource_type != kind:
                raise ValueError("incorrect measurement reference type")
        for refs in (self.source_refs,):
            keys = [(r.resource_type, r.resource_id, r.revision, r.content_hash) for r in refs]
            if len(keys) != len(set(keys)):
                raise ValueError("duplicate measurement lineage")
        if len(self.facts) != len({fact.fact_id for fact in self.facts}):
            raise ValueError("duplicate measured fact")
        if self.source_observed_at > self.measured_at:
            raise ValueError("source observation is after measurement")
        return self


class QualityMeasurement(_QualityMeasurementBase):
    """Original hydration provenance; serialization remains v1-compatible."""
    schema_version: Literal["aos.data-requirement-quality-measurement/v1"] = "aos.data-requirement-quality-measurement/v1"
    hydration_ref: InvestigationExactRef
    mapping_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _hydration(self) -> Self:
        if self.hydration_ref.resource_type != "SemanticHydrationReceipt":
            raise ValueError("incorrect hydration reference type")
        if any(ref.resource_type != "SourceMappingRevision" for ref in self.mapping_refs):
            raise ValueError("incorrect mapping reference type")
        keys = [(r.resource_type, r.resource_id, r.revision, r.content_hash) for r in self.mapping_refs]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate measurement lineage")
        return self


class CanonicalQueryQualityMeasurement(_QualityMeasurementBase):
    """Explicit existing-canonical-data read, not a semantic hydration write."""
    schema_version: Literal["aos.data-requirement-query-quality-measurement/v1"] = "aos.data-requirement-query-quality-measurement/v1"
    query_result_ref: InvestigationExactRef

    @model_validator(mode="after")
    def _query(self) -> Self:
        if (self.query_result_ref.resource_type != "QueryResultRevision"
            or type(self.query_result_ref.revision) is not int or self.query_result_ref.receipt_id is not None):
            raise ValueError("exact query result reference required")
        if any(ref.resource_type != "EcommerceObjectRevision" for ref in self.source_refs):
            raise ValueError("canonical query requires actual ecommerce source references")
        return self


class SnapshotQueryQualityMeasurement(_QualityMeasurementBase):
    """Complete-group provenance, distinct from hydration and per-object reads.

    This is only a typed measurement. Current source and fixed query Owners
    must authenticate the complete group before any fulfillment use.
    """
    schema_version: Literal["aos.data-requirement-snapshot-query-quality-measurement/v1"] = "aos.data-requirement-snapshot-query-quality-measurement/v1"
    query_result_ref: InvestigationExactRef
    source_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def _snapshot_query(self) -> Self:
        query = self.query_result_ref
        if (query.resource_type != "QueryResultRevision"
            or type(query.revision) is not int or query.receipt_id is not None):
            raise ValueError("exact snapshot query result reference required")
        source = self.source_refs[0]
        if (source.resource_type != "Evidence" or type(source.revision) is not int
            or source.revision != 1 or source.receipt_id is not None
            or source.resource_id != "evidence-analysis-snapshot-source-" + source.content_hash[7:]):
            raise ValueError("single complete snapshot source Evidence required")
        return self


QualityMeasurementRecord = Annotated[
    QualityMeasurement | CanonicalQueryQualityMeasurement | SnapshotQueryQualityMeasurement, Field(discriminator="schema_version")
]
_MEASUREMENT_ADAPTER = TypeAdapter(QualityMeasurementRecord)


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    satisfied: bool
    reasons: tuple[str, ...]
    freshness_expires_at: datetime


def evaluate_quality(
    scope: TenantScope,
    requirement: DataRequirementRevisionRecord,
    measurement: QualityMeasurementRecord,
    *,
    evaluated_at: datetime,
    population_policy: ResolvedPopulationPolicy,
) -> QualityAssessment:
    """Check every requested fact independently; no rounding, averaging or I/O."""
    req = DataRequirementRevisionRecord.model_validate(requirement.model_dump())
    item = _MEASUREMENT_ADAPTER.validate_python(measurement.model_dump())
    policy = ResolvedPopulationPolicy.model_validate(population_policy.model_dump())
    if req.content_hash != canonical_revision_content_hash(req):
        raise ValueError("requirement content hash mismatch")
    if evaluated_at.utcoffset() is None:
        raise ValueError("evaluation timestamp requires timezone")
    expected_ref = InvestigationExactRef(resource_type="DataRequirementRevision",
        resource_id=req.requirement_id, revision=req.revision, content_hash=req.content_hash)
    if (req.tenant.org_id != scope.org_id or req.tenant.project_id != scope.project_id
        or item.tenant != req.tenant or item.requirement_ref != expected_ref
        or item.channel_ref != req.channel_ref or item.entity_ref != req.entity_ref
        or item.time_window != req.time_window or item.cutoff_at != req.cutoff_at
        or item.grain != req.grain or policy.grain != req.grain
        or item.population_unit != policy.population_unit
        or item.population_policy_version != policy.version):
        raise ValueError("measurement scope does not match exact requirement")
    if req.status.value not in {"requested", "accepted", "planned"} or req.blockers:
        raise ValueError("requirement is not eligible for quality evaluation")
    if item.measured_at > evaluated_at or item.measured_at < req.created_at:
        raise ValueError("measurement time is outside requirement evaluation interval")
    facts = {fact.fact_id: fact for fact in item.facts}
    if set(facts) - set(req.required_facts):
        raise ValueError("unrequested measurement fact")
    expiry = min(req.expires_at, item.source_observed_at + timedelta(seconds=req.freshness_max_age_seconds))
    reasons: list[str] = []
    if evaluated_at >= expiry:
        reasons.append("MEASUREMENT_STALE")
    if item.distinct_population_count < req.min_population:
        reasons.append("POPULATION_BELOW_MINIMUM")
    # Decimal avoids binary float thresholds; integer cross multiplication also
    # avoids Decimal-context precision loss for very large measured populations.
    numerator, denominator = Decimal(str(req.quality_threshold)).as_integer_ratio()
    for fact_id in req.required_facts:
        fact = facts.get(fact_id)
        if fact is None:
            reasons.append(f"MISSING_FACT:{fact_id}")
        elif fact.eligible_count == 0:
            reasons.append(f"EMPTY_DENOMINATOR:{fact_id}")
        elif fact.valid_count * denominator < fact.eligible_count * numerator:
            reasons.append(f"QUALITY_BELOW_THRESHOLD:{fact_id}")
    return QualityAssessment(not reasons, tuple(reasons), expiry)
