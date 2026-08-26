"""Governed BI-W3 schema profiling contracts and PostgreSQL authority access.

Only aggregate statistics and exact authority references are accepted.  The
module deliberately has no mapping publication, browser, Adapter, LLM, or
external execution path.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

import psycopg
from psycopg.types.json import Jsonb
from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_observation_store import (
    ObservationAuthorityWrite,
)
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


JOB_SCHEMA = "aos.business-investigation.schema-profiling-job/v1"
HYPOTHESIS_SCHEMA = "aos.business-investigation.semantic-hypothesis/v1"
PROFILE_SCHEMA = "aos.business-investigation.adaptive-profile-revision/v1"
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
HIGH_RISK = frozenset({"identity", "customer_ownership", "commission", "health", "pii"})


def _exact(ref: InvestigationExactRef, expected: str, name: str) -> None:
    if ref.resource_type != expected:
        raise ValueError(f"{name} must reference {expected}")


def _unique(values: list[str], name: str) -> list[str]:
    cleaned = [value.strip() for value in values]
    if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
        raise ValueError(f"{name} must contain unique non-empty values")
    return cleaned


def _aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return value


class ProfilingRiskCategory(StrEnum):
    ORDINARY = "ordinary"
    IDENTITY = "identity"
    CUSTOMER_OWNERSHIP = "customer_ownership"
    COMMISSION = "commission"
    HEALTH = "health"
    PII = "pii"


class SchemaProfilingJobStatus(StrEnum):
    REQUESTED = "requested"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class AdaptiveProfileStatus(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class FieldAggregateSummary(AipContractModel):
    source_field: str = Field(min_length=1, max_length=500)
    data_type: str = Field(min_length=1, max_length=100)
    row_count: int = Field(ge=0)
    non_null_count: int = Field(ge=0)
    null_count: int = Field(ge=0)
    distinct_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    range_summary_ref: InvestigationExactRef
    distribution_summary_ref: InvestigationExactRef
    markings: list[str] = Field(default_factory=list, max_length=50)
    risk_category: ProfilingRiskCategory
    receipt_ref: InvestigationExactRef
    observation_ref: InvestigationExactRef

    @field_validator("markings")
    @classmethod
    def _markings(cls, value: list[str]) -> list[str]:
        return _unique(value, "markings")

    @model_validator(mode="after")
    def _counts(self) -> Self:
        if self.row_count != self.non_null_count + self.null_count:
            raise ValueError("field aggregate counts must conserve rowCount")
        if self.distinct_count > self.non_null_count:
            raise ValueError("field aggregate counts exceed nonNullCount")
        if self.duplicate_count != self.non_null_count - self.distinct_count:
            raise ValueError("field aggregate counts must conserve duplicates")
        _exact(self.range_summary_ref, "AggregateRangeSummaryRevision", "rangeSummaryRef")
        _exact(
            self.distribution_summary_ref,
            "AggregateDistributionSummaryRevision",
            "distributionSummaryRef",
        )
        _exact(self.receipt_ref, "ObservationReceipt", "receiptRef")
        _exact(self.observation_ref, "PlatformObservation", "observationRef")
        return self


class SchemaProfilingJobRevision(AipContractModel):
    schema_version: str = JOB_SCHEMA
    tenant: TenantContext
    job_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    receipt_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=500)
    observation_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=500)
    ontology_requirement_ref: InvestigationExactRef
    field_summaries: list[FieldAggregateSummary] = Field(min_length=1, max_length=1000)
    cutoff_at: datetime
    max_fields: int = Field(ge=1, le=1000)
    status: SchemaProfilingJobStatus
    blockers: list[str] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("cutoff_at", "created_at")
    @classmethod
    def _times(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("blockers")
    @classmethod
    def _blockers(cls, value: list[str]) -> list[str]:
        return _unique(value, "blockers")

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != JOB_SCHEMA or self.revision != 1:
            raise ValueError("unsupported profiling job schema or revision")
        _exact(self.ontology_requirement_ref, "OntologyRequirementRevision", "ontologyRequirementRef")
        for item in self.receipt_refs:
            _exact(item, "ObservationReceipt", "receiptRefs")
        for item in self.observation_refs:
            _exact(item, "PlatformObservation", "observationRefs")
        if len(self.field_summaries) > self.max_fields:
            raise ValueError("field summaries exceed maxFields")
        if len({item.source_field for item in self.field_summaries}) != len(self.field_summaries):
            raise ValueError("field summaries must have unique sourceField")
        receipt_refs = {
            (item.resource_type, item.resource_id, item.revision, item.content_hash)
            for item in self.receipt_refs
        }
        observation_refs = {
            (item.resource_type, item.resource_id, item.revision, item.content_hash)
            for item in self.observation_refs
        }
        if any(
            (
                item.receipt_ref.resource_type,
                item.receipt_ref.resource_id,
                item.receipt_ref.revision,
                item.receipt_ref.content_hash,
            ) not in receipt_refs
            for item in self.field_summaries
        ):
            raise ValueError("field receiptRef must be declared by the job")
        if any(
            (
                item.observation_ref.resource_type,
                item.observation_ref.resource_id,
                item.observation_ref.revision,
                item.observation_ref.content_hash,
            ) not in observation_refs
            for item in self.field_summaries
        ):
            raise ValueError("field observationRef must be declared by the job")
        if self.status is SchemaProfilingJobStatus.REQUESTED and self.blockers:
            raise ValueError("requested profiling job cannot contain blockers")
        if self.status is not SchemaProfilingJobStatus.REQUESTED and not self.blockers:
            raise ValueError("blocked or unknown profiling job requires blockers")
        return self


class SemanticHypothesisRevision(AipContractModel):
    schema_version: str = HYPOTHESIS_SCHEMA
    tenant: TenantContext
    hypothesis_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    job_ref: InvestigationExactRef
    source_field: str = Field(min_length=1, max_length=500)
    target_ref: InvestigationExactRef
    confidence: float = Field(ge=0, le=1)
    risk_category: ProfilingRiskCategory
    requires_human_review: bool
    conflicts: list[str] = Field(default_factory=list, max_length=100)
    evidence_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=2000)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("conflicts")
    @classmethod
    def _conflicts(cls, value: list[str]) -> list[str]:
        return _unique(value, "conflicts")

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != HYPOTHESIS_SCHEMA or self.revision != 1:
            raise ValueError("unsupported semantic hypothesis schema or revision")
        _exact(self.job_ref, "SchemaProfilingJobRevision", "jobRef")
        if self.target_ref.resource_type not in {"OntologyFieldRevision", "OntologyRelationshipRevision"}:
            raise ValueError("targetRef must reference governed ontology, never mapping authority")
        if any(ref.resource_type not in {"ObservationReceipt", "PlatformObservation"} for ref in self.evidence_refs):
            raise ValueError("evidenceRefs must reference observation authority")
        if self.risk_category.value in HIGH_RISK and not self.requires_human_review:
            raise ValueError("high-risk semantic hypothesis requires human review")
        return self


class ProfileCoverage(AipContractModel):
    required: int = Field(ge=0)
    fulfilled: int = Field(ge=0)
    unknown: int = Field(ge=0)


class AdaptiveProfileRevision(AipContractModel):
    schema_version: str = PROFILE_SCHEMA
    tenant: TenantContext
    profile_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    job_ref: InvestigationExactRef
    hypothesis_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=1000)
    required_fields: list[str] = Field(min_length=1, max_length=1000)
    covered_fields: list[str] = Field(default_factory=list, max_length=1000)
    unknown_fields: list[str] = Field(default_factory=list, max_length=1000)
    coverage: ProfileCoverage
    status: AdaptiveProfileStatus
    conflicts: list[str] = Field(default_factory=list, max_length=100)
    blockers: list[str] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("required_fields", "covered_fields", "unknown_fields", "conflicts", "blockers")
    @classmethod
    def _lists(cls, value: list[str], info) -> list[str]:
        return _unique(value, info.field_name)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != PROFILE_SCHEMA or self.revision != 1:
            raise ValueError("unsupported adaptive profile schema or revision")
        _exact(self.job_ref, "SchemaProfilingJobRevision", "jobRef")
        for item in self.hypothesis_refs:
            _exact(item, "SemanticHypothesisRevision", "hypothesisRefs")
        required, covered, unknown = set(self.required_fields), set(self.covered_fields), set(self.unknown_fields)
        if covered & unknown or covered | unknown != required:
            raise ValueError("coverage must partition required fields into covered and unknown")
        if (self.coverage.required, self.coverage.fulfilled, self.coverage.unknown) != (
            len(required), len(covered), len(unknown)
        ):
            raise ValueError("coverage counts must conserve required fields")
        if self.status is AdaptiveProfileStatus.COMPLETED and self.blockers:
            raise ValueError("completed adaptive profile cannot contain blockers")
        if self.status is not AdaptiveProfileStatus.COMPLETED and not self.blockers:
            raise ValueError("blocked or unknown adaptive profile requires blockers")
        return self

    def validate_hypotheses(self, hypotheses: list[SemanticHypothesisRevision]) -> None:
        if len(hypotheses) != len(self.hypothesis_refs):
            raise ValueError("hypothesis authority does not match hypothesisRefs")
        exact = {
            (item.hypothesis_id, item.revision, item.content_hash): item
            for item in hypotheses
        }
        for ref in self.hypothesis_refs:
            hypothesis = exact.get((ref.resource_id, ref.revision, ref.content_hash))
            if hypothesis is None:
                raise ValueError("hypothesis authority does not exactly match hypothesisRefs")
            if hypothesis.tenant != self.tenant or hypothesis.job_ref != self.job_ref:
                raise ValueError("profile and hypothesis authority must share tenant and job")
        if {item.source_field for item in hypotheses} != set(self.covered_fields):
            raise ValueError("covered fields must equal hypothesis source fields")


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BusinessInvestigationProfilingError(RuntimeError):
    code = "BUSINESS_INVESTIGATION_PROFILING_ERROR"


class BusinessInvestigationProfilingValidationError(BusinessInvestigationProfilingError):
    code = "BUSINESS_INVESTIGATION_PROFILING_VALIDATION_ERROR"


class BusinessInvestigationProfilingConflict(BusinessInvestigationProfilingError):
    code = "BUSINESS_INVESTIGATION_PROFILING_CONFLICT"


class BusinessInvestigationProfilingStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def record_job(self, scope: TenantScope, job: SchemaProfilingJobRevision):
        self._scope_matches(scope, job.tenant)
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM schema_profiling_job_record_biw3_003(%s,%s,%s,%s)",
            (job.job_id, job.idempotency_key, job.request_hash, Jsonb(job.model_dump(by_alias=True, mode="json"))),
        )
        return ObservationAuthorityWrite(
            authority=SchemaProfilingJobRevision.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def record_result(
        self,
        scope: TenantScope,
        profile: AdaptiveProfileRevision,
        hypotheses: list[SemanticHypothesisRevision],
    ):
        self._scope_matches(scope, profile.tenant)
        profile.validate_hypotheses(hypotheses)
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM schema_profiling_result_record_biw3_003(%s,%s,%s,%s,%s)",
            (
                profile.profile_id,
                profile.idempotency_key,
                profile.request_hash,
                Jsonb([item.model_dump(by_alias=True, mode="json") for item in hypotheses]),
                Jsonb(profile.model_dump(by_alias=True, mode="json")),
            ),
        )
        return ObservationAuthorityWrite(
            authority=AdaptiveProfileRevision.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def _execute(self, scope: TenantScope, sql: str, params: tuple[Any, ...]):
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(sql, params).fetchone()
                if row is None:
                    raise BusinessInvestigationProfilingConflict("profiling command returned no authority")
                conn.commit()
                return row
        except psycopg.Error as exc:
            if exc.sqlstate == "BO001":
                raise BusinessInvestigationProfilingValidationError(str(exc)) from exc
            if exc.sqlstate in {"BO002", "BO003", "23505", "23503"}:
                raise BusinessInvestigationProfilingConflict(str(exc)) from exc
            raise

    @staticmethod
    def _scope_matches(scope: TenantScope, tenant: TenantContext) -> None:
        if scope.key != (tenant.org_id, tenant.project_id):
            raise BusinessInvestigationProfilingValidationError(
                "payload tenant must equal principal scope"
            )
