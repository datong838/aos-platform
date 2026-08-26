"""Confirmed BI-W3 SourceField to canonical ontology mapping authority."""

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
from aos_api.business_investigation_observation_store import ObservationAuthorityWrite
from aos_api.business_investigation_profiling import (
    AdaptiveProfileRevision,
    SemanticHypothesisRevision,
)
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


SOURCE_MAPPING_REVISION_SCHEMA = "aos.business-investigation.source-mapping-revision/v1"
SOURCE_MAPPING_REVIEW_SCHEMA = "aos.business-investigation.source-mapping-review-decision/v1"
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


def _type(ref: InvestigationExactRef, expected: str, name: str) -> None:
    if ref.resource_type != expected:
        raise ValueError(f"{name} must reference {expected}")


def _aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return value


class SourceMappingStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class SourceMappingReviewDecision(StrEnum):
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class SourceMappingReviewDecisionRevision(AipContractModel):
    schema_version: str = SOURCE_MAPPING_REVIEW_SCHEMA
    tenant: TenantContext
    decision_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    job_ref: InvestigationExactRef
    profile_ref: InvestigationExactRef
    hypothesis_ref: InvestigationExactRef
    source_field: str = Field(min_length=1, max_length=500)
    canonical_target_ref: InvestigationExactRef
    decision: SourceMappingReviewDecision
    reviewer: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)
    decided_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    created_at: datetime

    @field_validator("decided_at", "created_at")
    @classmethod
    def _review_times(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _review_integrity(self) -> Self:
        if self.schema_version != SOURCE_MAPPING_REVIEW_SCHEMA or self.revision != 1:
            raise ValueError("unsupported source mapping review schema or revision")
        _type(self.job_ref, "SchemaProfilingJobRevision", "jobRef")
        _type(self.profile_ref, "AdaptiveProfileRevision", "profileRef")
        _type(self.hypothesis_ref, "SemanticHypothesisRevision", "hypothesisRef")
        if self.canonical_target_ref.resource_type not in {
            "OntologyFieldRevision", "OntologyRelationshipRevision"
        }:
            raise ValueError("canonicalTargetRef must reference governed ontology")
        if self.decided_at > self.created_at:
            raise ValueError("decidedAt must not be after createdAt")
        return self


class SourceMappingRevision(AipContractModel):
    schema_version: str = SOURCE_MAPPING_REVISION_SCHEMA
    tenant: TenantContext
    mapping_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    prior_ref: InvestigationExactRef | None = None
    content_hash: str = Field(pattern=SHA256_PATTERN)
    job_ref: InvestigationExactRef
    profile_ref: InvestigationExactRef
    hypothesis_ref: InvestigationExactRef
    receipt_ref: InvestigationExactRef
    observation_ref: InvestigationExactRef
    source_field: str = Field(min_length=1, max_length=500)
    canonical_target_ref: InvestigationExactRef
    status: SourceMappingStatus
    confirmation_ref: InvestigationExactRef
    confirmed_by: str = Field(min_length=1, max_length=200)
    confirmed_at: datetime
    reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("confirmed_at", "created_at")
    @classmethod
    def _times(cls, value: datetime) -> datetime:
        return _aware(value)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != SOURCE_MAPPING_REVISION_SCHEMA:
            raise ValueError("unsupported source mapping revision schemaVersion")
        _type(self.job_ref, "SchemaProfilingJobRevision", "jobRef")
        _type(self.profile_ref, "AdaptiveProfileRevision", "profileRef")
        _type(self.hypothesis_ref, "SemanticHypothesisRevision", "hypothesisRef")
        _type(self.receipt_ref, "ObservationReceipt", "receiptRef")
        _type(self.observation_ref, "PlatformObservation", "observationRef")
        _type(self.confirmation_ref, "HumanReviewDecisionRevision", "confirmationRef")
        if self.canonical_target_ref.resource_type not in {
            "OntologyFieldRevision",
            "OntologyRelationshipRevision",
        }:
            raise ValueError("canonicalTargetRef must reference governed ontology")
        if (self.revision == 1) != (self.prior_ref is None):
            raise ValueError("priorRef is absent only for revision 1")
        if self.prior_ref is not None:
            _type(self.prior_ref, "SourceMappingRevision", "priorRef")
            if (
                self.prior_ref.resource_id != self.mapping_id
                or self.prior_ref.revision != self.revision - 1
            ):
                raise ValueError("priorRef must exactly identify the preceding mapping revision")
        if self.confirmed_at > self.created_at:
            raise ValueError("confirmedAt must not be after createdAt")
        return self

    def validate_profile_hypothesis(
        self,
        profile: AdaptiveProfileRevision,
        hypothesis: SemanticHypothesisRevision,
    ) -> None:
        if self.tenant != profile.tenant or self.tenant != hypothesis.tenant:
            raise ValueError("mapping, profile and hypothesis tenant must match")
        if (
            self.profile_ref.resource_id != profile.profile_id
            or self.profile_ref.revision != profile.revision
            or self.profile_ref.content_hash != profile.content_hash
        ):
            raise ValueError("mapping profileRef must exactly match profile authority")
        if (
            self.hypothesis_ref.resource_id != hypothesis.hypothesis_id
            or self.hypothesis_ref.revision != hypothesis.revision
            or self.hypothesis_ref.content_hash != hypothesis.content_hash
        ):
            raise ValueError("mapping hypothesisRef must exactly match hypothesis authority")
        if self.job_ref != profile.job_ref or self.job_ref != hypothesis.job_ref:
            raise ValueError("mapping requires one exact profiling job")
        if self.source_field in profile.unknown_fields:
            raise ValueError("unknown source field cannot become mapping authority")
        if self.source_field not in profile.covered_fields or self.source_field != hypothesis.source_field:
            raise ValueError("source field must be covered by the exact hypothesis")
        if self.canonical_target_ref != hypothesis.target_ref:
            raise ValueError("canonical target must exactly match confirmed hypothesis")
        if self.hypothesis_ref not in profile.hypothesis_refs:
            # Pydantic models are comparable even though they are not hashable.
            raise ValueError("exact hypothesis must belong to exact adaptive profile")
        if self.receipt_ref not in hypothesis.evidence_refs:
            raise ValueError("receiptRef must be retained in hypothesis evidence")

    def validate_review(self, review: SourceMappingReviewDecisionRevision) -> None:
        if review.decision is not SourceMappingReviewDecision.CONFIRMED:
            raise ValueError("mapping requires a confirmed human review decision")
        if (
            review.tenant != self.tenant
            or review.job_ref != self.job_ref
            or review.profile_ref != self.profile_ref
            or review.hypothesis_ref != self.hypothesis_ref
            or review.source_field != self.source_field
            or review.canonical_target_ref != self.canonical_target_ref
            or review.reviewer != self.confirmed_by
        ):
            raise ValueError("mapping must exactly match the confirmed human review")
        if (
            self.confirmation_ref.resource_id != review.decision_id
            or self.confirmation_ref.revision != review.revision
            or self.confirmation_ref.content_hash != review.content_hash
        ):
            raise ValueError("confirmationRef must exactly match review authority")


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BusinessInvestigationMappingError(RuntimeError):
    code = "BUSINESS_INVESTIGATION_MAPPING_ERROR"


class BusinessInvestigationMappingValidationError(BusinessInvestigationMappingError):
    code = "BUSINESS_INVESTIGATION_MAPPING_VALIDATION_ERROR"


class BusinessInvestigationMappingConflict(BusinessInvestigationMappingError):
    code = "BUSINESS_INVESTIGATION_MAPPING_CONFLICT"


class BusinessInvestigationMappingStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def publish(
        self,
        scope: TenantScope,
        mapping: SourceMappingRevision,
        *,
        expected_version: int,
    ) -> ObservationAuthorityWrite[SourceMappingRevision]:
        if scope.key != (mapping.tenant.org_id, mapping.tenant.project_id):
            raise BusinessInvestigationMappingValidationError(
                "payload tenant must equal principal scope"
            )
        if expected_version < 0:
            raise BusinessInvestigationMappingValidationError(
                "expected version must be non-negative"
            )
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM source_mapping_publish_biw3_004(%s,%s,%s,%s,%s)",
            (
                mapping.mapping_id,
                expected_version,
                mapping.idempotency_key,
                mapping.request_hash,
                Jsonb(mapping.model_dump(by_alias=True, mode="json")),
            ),
        )
        return ObservationAuthorityWrite(
            authority=SourceMappingRevision.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def record_review(
        self,
        scope: TenantScope,
        review: SourceMappingReviewDecisionRevision,
    ) -> ObservationAuthorityWrite[SourceMappingReviewDecisionRevision]:
        if scope.key != (review.tenant.org_id, review.tenant.project_id):
            raise BusinessInvestigationMappingValidationError(
                "payload tenant must equal principal scope"
            )
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM source_mapping_review_record_biw3_004(%s,%s,%s,%s)",
            (
                review.decision_id,
                review.idempotency_key,
                review.request_hash,
                Jsonb(review.model_dump(by_alias=True, mode="json")),
            ),
        )
        return ObservationAuthorityWrite(
            authority=SourceMappingReviewDecisionRevision.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def _execute(self, scope: TenantScope, sql: str, params: tuple[Any, ...]):
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(sql, params).fetchone()
                if row is None:
                    raise BusinessInvestigationMappingConflict(
                        "mapping command returned no authority"
                    )
                conn.commit()
                return row
        except psycopg.Error as exc:
            if exc.sqlstate == "BO001":
                raise BusinessInvestigationMappingValidationError(str(exc)) from exc
            if exc.sqlstate in {"BO002", "BO003", "23505", "23503"}:
                raise BusinessInvestigationMappingConflict(str(exc)) from exc
            raise
