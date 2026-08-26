"""BI-W3 data-handling bindings and receipt-first security evidence."""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

import psycopg
from psycopg.types.json import Jsonb
from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_observation_store import ObservationAuthorityWrite
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


BINDING_SCHEMA = "aos.business-investigation.data-handling-binding/v1"
REDACTION_SCHEMA = "aos.business-investigation.redaction-receipt/v1"
RETENTION_SCHEMA = "aos.business-investigation.retention-disposition-receipt/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"
SUBJECT_TYPES = {"ObservationReceipt", "SemanticHydrationReceipt"}
ARTIFACT_TYPES = {
    "PageScreenshotArtifactRevision",
    "DOMSnapshotArtifactRevision",
    "ReadOnlyExportArtifactRevision",
    "HydrationArtifactRevision",
    "EvidenceArtifactRevision",
}


def _type(ref: InvestigationExactRef, allowed: set[str], name: str) -> None:
    if ref.resource_type not in allowed:
        raise ValueError(f"{name} must reference {sorted(allowed)}")


def _aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return value


def _strings(values: list[str], name: str) -> list[str]:
    cleaned = [value.strip() for value in values]
    if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
        raise ValueError(f"{name} must contain unique non-empty values")
    return cleaned


class BindingStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ArtifactHandlingMode(StrEnum):
    REDACTED_ONLY = "redacted_only"
    BLOCKED = "blocked"


class RedactionStatus(StrEnum):
    SAFE = "safe"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class SensitiveCategory(StrEnum):
    PII = "pii"
    SECRET = "secret"
    TOKEN = "token"
    COOKIE = "cookie"
    PASSWORD = "password"
    DSN = "dsn"
    PROVIDER_BODY = "provider_body"
    RAW_SAMPLE = "raw_sample"


class RetentionDisposition(StrEnum):
    RETAIN_REDACTED = "retain_redacted"
    QUARANTINE = "quarantine"
    DELETE_CONTENT_KEEP_HASH = "delete_content_keep_hash"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class InvestigationDataHandlingBindingRevision(AipContractModel):
    schema_version: str = BINDING_SCHEMA
    tenant: TenantContext
    binding_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256)
    subject_refs: list[InvestigationExactRef] = Field(min_length=1, max_length=500)
    marking_policy_ref: InvestigationExactRef
    purpose_policy_ref: InvestigationExactRef
    minimum_population_policy_ref: InvestigationExactRef
    secret_handling_policy_ref: InvestigationExactRef
    retention_policy_ref: InvestigationExactRef
    dom_mode: ArtifactHandlingMode
    screenshot_mode: ArtifactHandlingMode
    log_mode: ArtifactHandlingMode
    sample_mode: ArtifactHandlingMode
    export_mode: ArtifactHandlingMode
    customer_order_detail_allowed: Literal[False]
    download_allowed: Literal[False]
    status: BindingStatus
    blockers: list[str] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _created_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("blockers")
    @classmethod
    def _blockers(cls, value: list[str]) -> list[str]:
        return _strings(value, "blockers")

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != BINDING_SCHEMA or self.revision != 1:
            raise ValueError("unsupported data-handling binding schema or revision")
        for ref in self.subject_refs:
            _type(ref, SUBJECT_TYPES, "subjectRefs")
        _type(self.marking_policy_ref, {"DataMarkingPolicyRevision"}, "markingPolicyRef")
        _type(self.purpose_policy_ref, {"PurposePolicyRevision"}, "purposePolicyRef")
        _type(self.minimum_population_policy_ref, {"MinimumPopulationPolicyRevision"}, "minimumPopulationPolicyRef")
        _type(self.secret_handling_policy_ref, {"SecretHandlingPolicyRevision"}, "secretHandlingPolicyRef")
        _type(self.retention_policy_ref, {"OntologyRetentionPolicyRevision"}, "retentionPolicyRef")
        if self.status is BindingStatus.ACTIVE and self.blockers:
            raise ValueError("active binding cannot contain blockers")
        if self.status is not BindingStatus.ACTIVE and not self.blockers:
            raise ValueError("blocked or unknown binding requires blockers")
        return self


class InvestigationRedactionReceipt(AipContractModel):
    schema_version: str = REDACTION_SCHEMA
    tenant: TenantContext
    redaction_id: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=SHA256)
    binding_ref: InvestigationExactRef
    input_artifact_ref: InvestigationExactRef
    output_artifact_ref: InvestigationExactRef | None = None
    scanner_ref: InvestigationExactRef
    marking_policy_ref: InvestigationExactRef
    retention_policy_ref: InvestigationExactRef
    status: RedactionStatus
    category_counts: dict[SensitiveCategory, int] = Field(default_factory=dict, max_length=8)
    redacted_field_paths: list[str] = Field(default_factory=list, max_length=1000)
    raw_body_persisted: Literal[False]
    download_allowed: Literal[False]
    inspected_at: datetime
    blockers: list[str] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    created_by: str = Field(min_length=1, max_length=200)

    @field_validator("inspected_at")
    @classmethod
    def _inspected_at(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("redacted_field_paths", "blockers")
    @classmethod
    def _lists(cls, value: list[str], info) -> list[str]:
        values = _strings(value, info.field_name)
        if info.field_name == "redacted_field_paths" and any(
            re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,199}", item) is None for item in values
        ):
            raise ValueError("redacted field paths must be bounded logical paths")
        return values

    @field_validator("category_counts")
    @classmethod
    def _counts(cls, value: dict[SensitiveCategory, int]) -> dict[SensitiveCategory, int]:
        if any(count < 0 for count in value.values()):
            raise ValueError("category counts cannot be negative")
        return value

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != REDACTION_SCHEMA:
            raise ValueError("unsupported redaction receipt schema")
        _type(self.binding_ref, {"InvestigationDataHandlingBindingRevision"}, "bindingRef")
        _type(self.input_artifact_ref, ARTIFACT_TYPES, "inputArtifactRef")
        if self.output_artifact_ref is not None:
            _type(self.output_artifact_ref, {"RedactedArtifactRevision"}, "outputArtifactRef")
        _type(self.scanner_ref, {"SensitiveDataScannerRevision"}, "scannerRef")
        _type(self.marking_policy_ref, {"DataMarkingPolicyRevision"}, "markingPolicyRef")
        _type(self.retention_policy_ref, {"OntologyRetentionPolicyRevision"}, "retentionPolicyRef")
        if self.status is RedactionStatus.SAFE:
            if self.output_artifact_ref is None:
                raise ValueError("safe redaction requires exact redacted output")
            if self.blockers:
                raise ValueError("safe redaction cannot contain blockers")
        elif not self.blockers:
            raise ValueError("non-safe redaction requires blockers")
        return self

    def validate_binding(self, binding: InvestigationDataHandlingBindingRevision) -> None:
        if self.tenant != binding.tenant:
            raise ValueError("redaction receipt and binding tenant must match")
        if (
            self.binding_ref.resource_id != binding.binding_id
            or self.binding_ref.revision != binding.revision
            or self.binding_ref.content_hash != binding.content_hash
        ):
            raise ValueError("bindingRef must exactly match data-handling binding")
        if self.marking_policy_ref != binding.marking_policy_ref or self.retention_policy_ref != binding.retention_policy_ref:
            raise ValueError("redaction policy refs must exactly match binding")


class InvestigationRetentionDispositionReceipt(AipContractModel):
    schema_version: str = RETENTION_SCHEMA
    tenant: TenantContext
    disposition_id: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=SHA256)
    binding_ref: InvestigationExactRef
    artifact_ref: InvestigationExactRef
    retention_policy_ref: InvestigationExactRef
    disposition: RetentionDisposition
    retained_content_hash: str = Field(pattern=SHA256)
    cleanup_receipt_ref: InvestigationExactRef | None = None
    due_at: datetime
    decided_at: datetime
    blockers: list[str] = Field(default_factory=list, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    created_by: str = Field(min_length=1, max_length=200)

    @field_validator("due_at", "decided_at")
    @classmethod
    def _times(cls, value: datetime) -> datetime:
        return _aware(value)

    @field_validator("blockers")
    @classmethod
    def _blocker_list(cls, value: list[str]) -> list[str]:
        return _strings(value, "blockers")

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if self.schema_version != RETENTION_SCHEMA:
            raise ValueError("unsupported retention disposition schema")
        _type(self.binding_ref, {"InvestigationDataHandlingBindingRevision"}, "bindingRef")
        _type(self.artifact_ref, {"RedactedArtifactRevision"}, "artifactRef")
        _type(self.retention_policy_ref, {"OntologyRetentionPolicyRevision"}, "retentionPolicyRef")
        if self.cleanup_receipt_ref is not None:
            _type(self.cleanup_receipt_ref, {"OntologyEvidenceCleanupReceipt"}, "cleanupReceiptRef")
        if self.disposition is RetentionDisposition.DELETE_CONTENT_KEEP_HASH and self.cleanup_receipt_ref is None:
            raise ValueError("delete_content_keep_hash requires exact canonical cleanup receipt")
        if self.disposition in {RetentionDisposition.BLOCKED, RetentionDisposition.UNKNOWN}:
            if not self.blockers:
                raise ValueError("blocked or unknown retention disposition requires blockers")
        elif self.blockers:
            raise ValueError("successful retention disposition cannot contain blockers")
        if self.decided_at > self.due_at and self.disposition is RetentionDisposition.RETAIN_REDACTED:
            raise ValueError("expired retention cannot be reported as retained")
        return self

    def validate_binding(self, binding: InvestigationDataHandlingBindingRevision) -> None:
        if self.tenant != binding.tenant:
            raise ValueError("retention disposition and binding tenant must match")
        if (
            self.binding_ref.resource_id != binding.binding_id
            or self.binding_ref.revision != binding.revision
            or self.binding_ref.content_hash != binding.content_hash
        ):
            raise ValueError("bindingRef must exactly match data-handling binding")
        if self.retention_policy_ref != binding.retention_policy_ref:
            raise ValueError("retention policy ref must exactly match binding")


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BusinessInvestigationDataHandlingError(RuntimeError):
    pass


class BusinessInvestigationDataHandlingValidationError(BusinessInvestigationDataHandlingError):
    pass


class BusinessInvestigationDataHandlingConflict(BusinessInvestigationDataHandlingError):
    pass


class BusinessInvestigationDataHandlingStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def bind(self, scope: TenantScope, item: InvestigationDataHandlingBindingRevision):
        self._scope(scope, item.tenant)
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM investigation_data_handling_bind_biw3_006(%s,%s,%s,%s)",
            (item.binding_id, item.idempotency_key, item.request_hash, Jsonb(item.model_dump(by_alias=True, mode="json"))),
        )
        return ObservationAuthorityWrite(
            authority=InvestigationDataHandlingBindingRevision.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def record_redaction(self, scope: TenantScope, item: InvestigationRedactionReceipt):
        self._scope(scope, item.tenant)
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM investigation_redaction_record_biw3_006(%s,%s,%s,%s)",
            (item.redaction_id, item.idempotency_key, item.request_hash, Jsonb(item.model_dump(by_alias=True, mode="json"))),
        )
        return ObservationAuthorityWrite(
            authority=InvestigationRedactionReceipt.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def record_retention(self, scope: TenantScope, item: InvestigationRetentionDispositionReceipt):
        self._scope(scope, item.tenant)
        row = self._execute(
            scope,
            "SELECT authority_data,replayed FROM investigation_retention_record_biw3_006(%s,%s,%s,%s)",
            (item.disposition_id, item.idempotency_key, item.request_hash, Jsonb(item.model_dump(by_alias=True, mode="json"))),
        )
        return ObservationAuthorityWrite(
            authority=InvestigationRetentionDispositionReceipt.model_validate(row["authority_data"]),
            replayed=bool(row["replayed"]),
        )

    def _execute(self, scope: TenantScope, sql: str, params: tuple[Any, ...]) -> dict[str, Any]:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(sql, params).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            if exc.sqlstate == "BO003":
                raise BusinessInvestigationDataHandlingConflict(str(exc)) from exc
            raise BusinessInvestigationDataHandlingValidationError(str(exc)) from exc
        if row is None:
            raise BusinessInvestigationDataHandlingValidationError("data-handling function returned no authority")
        return dict(row)

    @staticmethod
    def _scope(scope: TenantScope, tenant: TenantContext) -> None:
        if scope.key != (tenant.org_id, tenant.project_id):
            raise BusinessInvestigationDataHandlingValidationError("tenant scope mismatch")
