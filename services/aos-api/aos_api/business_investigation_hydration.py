"""Receipt-first BI-W3 semantic hydration contracts and authority store."""

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
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


JOB_SCHEMA = "aos.business-investigation.semantic-hydration-job/v1"
RECEIPT_SCHEMA = "aos.business-investigation.semantic-hydration-receipt/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"
OWNER_COMMAND_TYPES = {"OntologyOwnerWriteCommandRevision", "DataProductOwnerWriteCommandRevision"}
OWNER_RECEIPT_TYPES = {"OntologyOwnerWriteReceiptRevision", "DataProductOwnerWriteReceiptRevision"}
OUTPUT_TYPES = {"OntologyObjectRevision", "OntologyLinkRevision", "DataProductRevision"}


def _type(ref: InvestigationExactRef, allowed: set[str], name: str) -> None:
    if ref.resource_type not in allowed:
        raise ValueError(f"{name} must reference {sorted(allowed)}")


def _aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return value


def _unique(values: list[str], name: str) -> list[str]:
    cleaned = [value.strip() for value in values]
    if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
        raise ValueError(f"{name} must contain unique non-empty values")
    return cleaned


class HydrationJobStatus(StrEnum):
    REQUESTED = "requested"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class HydrationReceiptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class IdentityResolutionMethod(StrEnum):
    NONE = "none"
    EXACT = "exact"
    EXTERNAL_REVIEWED = "external_reviewed"


class OwnerCommandBinding(AipContractModel):
    mapping_ref: InvestigationExactRef
    owner_command_ref: InvestigationExactRef
    canonical_target_ref: InvestigationExactRef

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        _type(self.mapping_ref, {"SourceMappingRevision"}, "ownerCommandBindings.mappingRef")
        _type(self.owner_command_ref, OWNER_COMMAND_TYPES, "ownerCommandBindings.ownerCommandRef")
        return self


class SemanticHydrationJobRevision(AipContractModel):
    schema_version: str = JOB_SCHEMA
    tenant: TenantContext
    hydration_job_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256)
    profile_ref: InvestigationExactRef
    mapping_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=1000)
    receipt_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=500)
    observation_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=500)
    source_snapshot_ref: InvestigationExactRef
    cutoff_at: datetime
    owner_command_bindings: list[OwnerCommandBinding] = Field(min_length=1, max_length=1000)
    unknown_fields: list[str] = Field(default_factory=list, max_length=1000)
    status: HydrationJobStatus
    blockers: list[str] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("cutoff_at", "created_at")
    @classmethod
    def _times(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("unknown_fields", "blockers")
    @classmethod
    def _lists(cls, value: list[str], info) -> list[str]:
        return _unique(value, info.field_name)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != JOB_SCHEMA or self.revision != 1:
            raise ValueError("unsupported hydration job schema or revision")
        _type(self.profile_ref, {"AdaptiveProfileRevision"}, "profileRef")
        _type(self.source_snapshot_ref, {"PlatformSourceSnapshotRevision"}, "sourceSnapshotRef")
        for ref in self.mapping_refs:
            _type(ref, {"SourceMappingRevision"}, "mappingRefs")
        for ref in self.receipt_refs:
            _type(ref, {"ObservationReceipt"}, "receiptRefs")
        for ref in self.observation_refs:
            _type(ref, {"PlatformObservation"}, "observationRefs")
        binding_mapping_refs = [binding.mapping_ref for binding in self.owner_command_bindings]
        if binding_mapping_refs != self.mapping_refs:
            raise ValueError("ownerCommandBindings must bind every exact mappingRef once and in order")
        owner_command_identities = {
            (
                binding.owner_command_ref.resource_type,
                binding.owner_command_ref.resource_id,
                binding.owner_command_ref.revision,
                binding.owner_command_ref.content_hash,
            )
            for binding in self.owner_command_bindings
        }
        if len(owner_command_identities) != len(self.owner_command_bindings):
            raise ValueError("ownerCommandBindings must contain unique owner command refs")
        if self.status is HydrationJobStatus.REQUESTED and self.blockers:
            raise ValueError("requested hydration job cannot contain blockers")
        if self.status is not HydrationJobStatus.REQUESTED and not self.blockers:
            raise ValueError("blocked or unknown hydration job requires blockers")
        return self


class HydrationCounts(AipContractModel):
    attempted: int = Field(ge=0)
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    quarantined: int = Field(ge=0)
    unknown: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserve(self) -> Self:
        if self.attempted != self.created + self.updated + self.quarantined + self.unknown:
            raise ValueError("hydration counts must conserve attempted quantity")
        return self


class SemanticHydrationReceipt(AipContractModel):
    schema_version: str = RECEIPT_SCHEMA
    tenant: TenantContext
    hydration_id: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=SHA256)
    job_ref: InvestigationExactRef
    mapping_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=1000)
    owner_write_receipt_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=1000)
    output_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=1000)
    status: HydrationReceiptStatus
    counts: HydrationCounts
    zero_observed: bool
    unknown_fields: list[str] = Field(default_factory=list, max_length=1000)
    identity_resolution_method: IdentityResolutionMethod
    quality_violation_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=500)
    watermark_ref: InvestigationExactRef | None = None
    outbox_receipt_ref: InvestigationExactRef | None = None
    lineage_ref: InvestigationExactRef | None = None
    masked_policy_ref: InvestigationExactRef
    unmet_semantic_facts: list[str] = Field(default_factory=list, max_length=1000)
    rollback_ref: InvestigationExactRef
    rebuild_ref: InvestigationExactRef
    hydrated_at: datetime
    blockers: list[str] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    created_by: str = Field(min_length=1, max_length=200)

    @field_validator("hydrated_at")
    @classmethod
    def _hydrated_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("unknown_fields", "unmet_semantic_facts", "blockers")
    @classmethod
    def _lists(cls, value: list[str], info) -> list[str]:
        return _unique(value, info.field_name)

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != RECEIPT_SCHEMA:
            raise ValueError("unsupported hydration receipt schema")
        _type(self.job_ref, {"SemanticHydrationJobRevision"}, "jobRef")
        for ref in self.mapping_refs:
            _type(ref, {"SourceMappingRevision"}, "mappingRefs")
        for ref in self.owner_write_receipt_refs:
            _type(ref, OWNER_RECEIPT_TYPES, "ownerWriteReceiptRefs")
        for ref in self.output_refs:
            _type(ref, OUTPUT_TYPES, "outputRefs")
        _type(self.masked_policy_ref, {"DataMarkingPolicyRevision"}, "maskedPolicyRef")
        _type(self.rollback_ref, {"OwnerRollbackPlanRevision"}, "rollbackRef")
        _type(self.rebuild_ref, {"ProjectionRebuildPlanRevision"}, "rebuildRef")
        if self.status is HydrationReceiptStatus.SUCCEEDED:
            if not self.owner_write_receipt_refs:
                raise ValueError("succeeded hydration requires owner write receipt")
            if not self.output_refs and not self.zero_observed:
                raise ValueError("succeeded hydration requires outputs unless zeroObserved")
            if self.blockers:
                raise ValueError("succeeded hydration cannot contain blockers")
        elif not self.blockers:
            raise ValueError("non-succeeded hydration requires blockers")
        if self.zero_observed:
            if self.status is not HydrationReceiptStatus.SUCCEEDED or self.counts.attempted != 0 or self.output_refs:
                raise ValueError("zeroObserved is only valid for an evidenced successful empty observation")
        if self.counts.unknown > 0 and not self.unknown_fields:
            raise ValueError("unknown hydration count requires unknown fields")
        return self

    def validate_job(self, job: SemanticHydrationJobRevision) -> None:
        if self.tenant != job.tenant:
            raise ValueError("hydration receipt and job tenant must match")
        if self.job_ref.resource_id != job.hydration_job_id or self.job_ref.revision != job.revision or self.job_ref.content_hash != job.content_hash:
            raise ValueError("jobRef must exactly match hydration job authority")
        if self.mapping_refs != job.mapping_refs:
            raise ValueError("mappingRefs must exactly match hydration job")
        if set(self.unknown_fields) != set(job.unknown_fields):
            raise ValueError("unknown fields must be conserved from hydration job")
        if not set(self.unknown_fields).issubset(self.unmet_semantic_facts):
            raise ValueError("unknown fields must remain unmet semantic facts")


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BusinessInvestigationHydrationError(RuntimeError): pass
class BusinessInvestigationHydrationValidationError(BusinessInvestigationHydrationError): pass
class BusinessInvestigationHydrationConflict(BusinessInvestigationHydrationError): pass


class BusinessInvestigationHydrationStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def request(self, scope: TenantScope, job: SemanticHydrationJobRevision):
        self._scope(scope, job.tenant)
        row = self._execute(scope, "SELECT authority_data,replayed FROM semantic_hydration_request_biw3_005(%s,%s,%s,%s)", (
            job.hydration_job_id, job.idempotency_key, job.request_hash, Jsonb(job.model_dump(by_alias=True, mode="json"))))
        return ObservationAuthorityWrite(authority=SemanticHydrationJobRevision.model_validate(row["authority_data"]), replayed=bool(row["replayed"]))

    def record(self, scope: TenantScope, receipt: SemanticHydrationReceipt):
        self._scope(scope, receipt.tenant)
        row = self._execute(scope, "SELECT authority_data,replayed FROM semantic_hydration_record_biw3_005(%s,%s,%s,%s)", (
            receipt.hydration_id, receipt.idempotency_key, receipt.request_hash, Jsonb(receipt.model_dump(by_alias=True, mode="json"))))
        return ObservationAuthorityWrite(authority=SemanticHydrationReceipt.model_validate(row["authority_data"]), replayed=bool(row["replayed"]))

    def _execute(self, scope: TenantScope, sql: str, params: tuple[Any, ...]):
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(sql, params).fetchone()
                if row is None: raise BusinessInvestigationHydrationConflict("hydration command returned no authority")
                conn.commit(); return row
        except psycopg.Error as exc:
            if exc.sqlstate == "BO001": raise BusinessInvestigationHydrationValidationError(str(exc)) from exc
            if exc.sqlstate in {"BO002", "BO003", "23505", "23503"}: raise BusinessInvestigationHydrationConflict(str(exc)) from exc
            raise

    @staticmethod
    def _scope(scope: TenantScope, tenant: TenantContext) -> None:
        if scope.key != (tenant.org_id, tenant.project_id):
            raise BusinessInvestigationHydrationValidationError("payload tenant must equal principal scope")
