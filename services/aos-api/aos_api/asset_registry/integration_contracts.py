"""Strict M4 contracts for Evidence and Integration Case projections.

The public DTOs in this module intentionally contain no free-form metadata,
raw actor information, secrets, PII, or client-supplied projection facts.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import Field, TypeAdapter, field_validator, model_validator

from aos_api.asset_registry.contracts import SHA256_PATTERN, StrictContract

STAGE_POLICY_VERSION = "aos.integration-stage/v1"
MAX_REFERENCE_LENGTH = 1024
MAX_DISPLAY_NAME_LENGTH = 240
MAX_REASON_REFS = 128
MAX_MARKINGS = 64
MAX_FAILED_CHECKS = 128
MAX_EVIDENCE_PER_SNAPSHOT = 512
MAX_LATEST_EVIDENCE = 256
MAX_STAGE_GATES = 8
MAX_BLOCKERS = 256
MAX_TIMELINE_ITEMS = 100
MAX_EVIDENCE_ENVELOPE_BYTES = 32 * 1024
MAX_CASE_LIST_LIMIT = 100
MAX_CASE_LIST_OFFSET = 10_000

_CONTROL_CHAR = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_EMAIL = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_SECRET = re.compile(
    r"(?i)(?:password|passwd|secret|authorization|bearer|access[_-]?token|"
    r"refresh[_-]?token|api[_-]?key|private[_-]?key)\s*[:=]"
)


class IntegrationStage(StrEnum):
    PLANNED = "planned"
    CONNECTION_VERIFIED = "connection_verified"
    DATA_VERIFIED = "data_verified"
    ONTOLOGY_VERIFIED = "ontology_verified"
    LOGIC_VERIFIED = "logic_verified"
    WORKSHOP_VERIFIED = "workshop_verified"
    PRODUCTION_READY = "production_ready"
    PRODUCTION_ACTIVE = "production_active"


class IntegrationCaseScope(StrEnum):
    CURRENT = "current"
    REFERENCE = "reference"


class EvidenceOutcome(StrEnum):
    VALID = "valid"
    INVALID = "invalid"
    REVOKED = "revoked"


class EvidenceType(StrEnum):
    SOURCE_CONNECTION = "source_connection"
    TENANT_ISOLATION = "tenant_isolation"
    PIPELINE_RUN = "pipeline_run"
    DATASET_REVISION = "dataset_revision"
    DATA_QUALITY = "data_quality"
    ONTOLOGY_REVISION = "ontology_revision"
    MAPPING_VALIDATION = "mapping_validation"
    LOGIC_PUBLICATION = "logic_publication"
    LOGIC_EVAL = "logic_eval"
    WORKSHOP_VALIDATION = "workshop_validation"
    ACTION_SAFETY = "action_safety"
    OPERATIONS_READINESS = "operations_readiness"
    SECURITY_VALIDATION = "security_validation"
    RUNTIME_HEALTH = "runtime_health"


def _normalized_text(value: str, *, label: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{label} must be non-blank and already normalized")
    if _CONTROL_CHAR.search(value):
        raise ValueError(f"{label} must not contain control characters")
    return value


def _safe_reference(value: str, *, label: str) -> str:
    value = _normalized_text(value, label=label)
    if _EMAIL.search(value) or _SECRET.search(value):
        raise ValueError(f"{label} must not contain PII or secret material")
    return value


def _canonical_uuid(value: str, *, label: str) -> str:
    value = _normalized_text(value, label=label)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a UUID") from exc
    if str(parsed) != value:
        raise ValueError(f"{label} must use canonical lowercase UUID form")
    return value


def _utc_datetime(value: datetime, *, label: str) -> datetime:
    if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise ValueError(f"{label} must be an aware UTC datetime")
    return value


def _unique_normalized(values: list[str], *, label: str) -> list[str]:
    checked = [_safe_reference(value, label=label) for value in values]
    if len(checked) != len(set(checked)):
        raise ValueError(f"{label} values must be unique")
    if checked != sorted(checked):
        raise ValueError(f"{label} values must use canonical lexical order")
    return checked


def _strict_enum(value: object, enum_type: type[StrEnum], *, label: str) -> StrEnum:
    if isinstance(value, enum_type):
        return value
    if type(value) is not str:
        raise ValueError(f"{label} must be a canonical string enum")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(f"{label} is not an allowed value") from exc


class _Claims(StrictContract):
    """Closed base for typed claims; strict primitives reject coercion."""


class SourceConnectionClaims(_Claims):
    connection_ref: str = Field(alias="connectionRef", max_length=MAX_REFERENCE_LENGTH)
    auth_mode: Literal["oauth", "service_account", "api_key", "database", "other"] = Field(alias="authMode")
    read_probe: bool = Field(alias="readProbe")
    tenant_binding: bool = Field(alias="tenantBinding")

    _refs = field_validator("connection_ref")(
        lambda value: _safe_reference(value, label="connectionRef")
    )


class TenantIsolationClaims(_Claims):
    positive_tenant: str = Field(alias="positiveTenant", max_length=MAX_REFERENCE_LENGTH)
    negative_tenant: str = Field(alias="negativeTenant", max_length=MAX_REFERENCE_LENGTH)
    cross_tenant_denied: bool = Field(alias="crossTenantDenied")

    @field_validator("positive_tenant", "negative_tenant")
    @classmethod
    def _refs(cls, value: str) -> str:
        return _safe_reference(value, label="tenant reference")

    @model_validator(mode="after")
    def _different_tenants(self) -> TenantIsolationClaims:
        if self.positive_tenant == self.negative_tenant:
            raise ValueError("positiveTenant and negativeTenant must differ")
        return self


class PipelineRunClaims(_Claims):
    pipeline_ref: str = Field(alias="pipelineRef", max_length=MAX_REFERENCE_LENGTH)
    run_id: str = Field(alias="runId", max_length=MAX_REFERENCE_LENGTH)
    result: Literal["succeeded", "failed"]
    input_revision: str = Field(alias="inputRevision", max_length=MAX_REFERENCE_LENGTH)
    output_revision: str = Field(alias="outputRevision", max_length=MAX_REFERENCE_LENGTH)

    @field_validator("pipeline_ref", "run_id", "input_revision", "output_revision")
    @classmethod
    def _refs(cls, value: str) -> str:
        return _safe_reference(value, label="pipeline claim reference")


class DatasetRevisionClaims(_Claims):
    dataset_ref: str = Field(alias="datasetRef", max_length=MAX_REFERENCE_LENGTH)
    revision: str = Field(max_length=MAX_REFERENCE_LENGTH)
    schema_hash: str = Field(alias="schemaHash", pattern=SHA256_PATTERN)
    row_count: int | None = Field(default=None, alias="rowCount", ge=0)

    @field_validator("dataset_ref", "revision")
    @classmethod
    def _refs(cls, value: str) -> str:
        return _safe_reference(value, label="dataset claim reference")


class DataQualityClaims(_Claims):
    dataset_ref: str = Field(alias="datasetRef", max_length=MAX_REFERENCE_LENGTH)
    check_set_hash: str = Field(alias="checkSetHash", pattern=SHA256_PATTERN)
    required_passed: bool = Field(alias="requiredPassed")
    failed_checks: list[str] = Field(alias="failedChecks", max_length=MAX_FAILED_CHECKS)

    @field_validator("dataset_ref")
    @classmethod
    def _ref(cls, value: str) -> str:
        return _safe_reference(value, label="datasetRef")

    @field_validator("failed_checks")
    @classmethod
    def _checks(cls, values: list[str]) -> list[str]:
        return _unique_normalized(values, label="failedChecks")


class OntologyRevisionClaims(_Claims):
    ontology_ref: str = Field(alias="ontologyRef", max_length=MAX_REFERENCE_LENGTH)
    revision: str = Field(max_length=MAX_REFERENCE_LENGTH)
    schema_hash: str = Field(alias="schemaHash", pattern=SHA256_PATTERN)

    @field_validator("ontology_ref", "revision")
    @classmethod
    def _refs(cls, value: str) -> str:
        return _safe_reference(value, label="ontology claim reference")


class MappingValidationClaims(_Claims):
    mapping_ref: str = Field(alias="mappingRef", max_length=MAX_REFERENCE_LENGTH)
    coverage: float = Field(ge=0.0, le=1.0)
    link_validation_passed: bool = Field(alias="linkValidationPassed")

    @field_validator("mapping_ref")
    @classmethod
    def _ref(cls, value: str) -> str:
        return _safe_reference(value, label="mappingRef")

    @field_validator("coverage", mode="before")
    @classmethod
    def _strict_float(cls, value: object) -> object:
        if type(value) is not float:
            raise ValueError("coverage must be a JSON number with decimal precision")
        return value


class LogicPublicationClaims(_Claims):
    logic_ref: str = Field(alias="logicRef", max_length=MAX_REFERENCE_LENGTH)
    immutable_revision: str = Field(alias="immutableRevision", max_length=MAX_REFERENCE_LENGTH)
    publication_hash: str = Field(alias="publicationHash", pattern=SHA256_PATTERN)

    @field_validator("logic_ref", "immutable_revision")
    @classmethod
    def _refs(cls, value: str) -> str:
        return _safe_reference(value, label="logic publication reference")


class LogicEvalClaims(_Claims):
    logic_ref: str = Field(alias="logicRef", max_length=MAX_REFERENCE_LENGTH)
    eval_suite_hash: str = Field(alias="evalSuiteHash", pattern=SHA256_PATTERN)
    required_passed: bool = Field(alias="requiredPassed")

    @field_validator("logic_ref")
    @classmethod
    def _ref(cls, value: str) -> str:
        return _safe_reference(value, label="logicRef")


class WorkshopValidationClaims(_Claims):
    workshop_ref: str = Field(alias="workshopRef", max_length=MAX_REFERENCE_LENGTH)
    real_source: bool = Field(alias="realSource")
    empty_state_passed: bool = Field(alias="emptyStatePassed")
    permission_passed: bool = Field(alias="permissionPassed")
    main_flow_passed: bool = Field(alias="mainFlowPassed")

    @field_validator("workshop_ref")
    @classmethod
    def _ref(cls, value: str) -> str:
        return _safe_reference(value, label="workshopRef")


class ActionSafetyClaims(_Claims):
    action_ref: str = Field(alias="actionRef", max_length=MAX_REFERENCE_LENGTH)
    approval_control_passed: bool = Field(alias="approvalControlPassed")
    rollback_control_passed: bool = Field(alias="rollbackControlPassed")
    idempotency_control_passed: bool = Field(alias="idempotencyControlPassed")
    installation_apply_verified: bool = Field(alias="installationApplyVerified")
    installation_verify_verified: bool = Field(alias="installationVerifyVerified")

    @field_validator("action_ref")
    @classmethod
    def _ref(cls, value: str) -> str:
        return _safe_reference(value, label="actionRef")


class OperationsReadinessClaims(_Claims):
    runbook_ref: str = Field(alias="runbookRef", max_length=MAX_REFERENCE_LENGTH)
    alert_ref: str = Field(alias="alertRef", max_length=MAX_REFERENCE_LENGTH)
    owner_ref: str = Field(alias="ownerRef", max_length=MAX_REFERENCE_LENGTH)
    required_checks_passed: bool = Field(alias="requiredChecksPassed")

    @field_validator("runbook_ref", "alert_ref", "owner_ref")
    @classmethod
    def _refs(cls, value: str) -> str:
        return _safe_reference(value, label="operations reference")


class SecurityValidationClaims(_Claims):
    policy_set_hash: str = Field(alias="policySetHash", pattern=SHA256_PATTERN)
    required_checks_passed: bool = Field(alias="requiredChecksPassed")


class RuntimeHealthClaims(_Claims):
    deployment_ref: str = Field(alias="deploymentRef", max_length=MAX_REFERENCE_LENGTH)
    run_id: str = Field(alias="runId", max_length=MAX_REFERENCE_LENGTH)
    healthy: bool
    latency_ms: int | None = Field(default=None, alias="latencyMs", ge=0)

    @field_validator("deployment_ref", "run_id")
    @classmethod
    def _refs(cls, value: str) -> str:
        return _safe_reference(value, label="runtime reference")


class _EvidenceEnvelope(StrictContract):
    evidence_id: str = Field(alias="evidenceId")
    revision: int = Field(ge=1)
    evidence_type: EvidenceType = Field(alias="evidenceType")
    series_key: str = Field(alias="seriesKey", max_length=MAX_REFERENCE_LENGTH)
    subject_ref: str = Field(alias="subjectRef", max_length=MAX_REFERENCE_LENGTH)
    artifact_ref: str = Field(alias="artifactRef", max_length=MAX_REFERENCE_LENGTH)
    artifact_hash: str = Field(alias="artifactHash", pattern=SHA256_PATTERN)
    outcome: EvidenceOutcome
    observed_at: datetime = Field(alias="observedAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")
    required_markings: list[str] = Field(alias="requiredMarkings", max_length=MAX_MARKINGS)
    producer: str = Field(max_length=MAX_REFERENCE_LENGTH)
    evidence_hash: str = Field(alias="evidenceHash", pattern=SHA256_PATTERN)
    recorded_at: datetime = Field(alias="recordedAt")

    @field_validator("evidence_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _canonical_uuid(value, label="evidenceId")

    @field_validator("outcome", mode="before")
    @classmethod
    def _outcome(cls, value: object) -> EvidenceOutcome:
        return _strict_enum(value, EvidenceOutcome, label="outcome")  # type: ignore[return-value]

    @field_validator("series_key", "subject_ref", "artifact_ref", "producer")
    @classmethod
    def _refs(cls, value: str) -> str:
        return _safe_reference(value, label="evidence reference")

    @field_validator("observed_at", "expires_at", "revoked_at", "recorded_at")
    @classmethod
    def _times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc_datetime(value, label="evidence time")

    @field_validator("required_markings")
    @classmethod
    def _markings(cls, values: list[str]) -> list[str]:
        return _unique_normalized(values, label="requiredMarkings")

    @model_validator(mode="after")
    def _lifecycle(self) -> _EvidenceEnvelope:
        if self.recorded_at < self.observed_at:
            raise ValueError("recordedAt must not precede observedAt")
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("expiresAt must be after observedAt")
        if self.outcome == EvidenceOutcome.REVOKED:
            if self.revoked_at is None:
                raise ValueError("revoked outcome requires revokedAt")
        elif self.revoked_at is not None:
            raise ValueError("revokedAt is only valid for revoked outcome")
        if self.revoked_at is not None and not (
            self.observed_at <= self.revoked_at <= self.recorded_at
        ):
            raise ValueError("revokedAt must be between observedAt and recordedAt")
        payload = json.dumps(
            self.model_dump(mode="json", by_alias=True),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > MAX_EVIDENCE_ENVELOPE_BYTES:
            raise ValueError("evidence envelope exceeds canonical size budget")
        return self


class SourceConnectionEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.SOURCE_CONNECTION] = Field(alias="evidenceType")
    claims: SourceConnectionClaims


class TenantIsolationEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.TENANT_ISOLATION] = Field(alias="evidenceType")
    claims: TenantIsolationClaims


class PipelineRunEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.PIPELINE_RUN] = Field(alias="evidenceType")
    claims: PipelineRunClaims


class DatasetRevisionEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.DATASET_REVISION] = Field(alias="evidenceType")
    claims: DatasetRevisionClaims


class DataQualityEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.DATA_QUALITY] = Field(alias="evidenceType")
    claims: DataQualityClaims


class OntologyRevisionEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.ONTOLOGY_REVISION] = Field(alias="evidenceType")
    claims: OntologyRevisionClaims


class MappingValidationEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.MAPPING_VALIDATION] = Field(alias="evidenceType")
    claims: MappingValidationClaims


class LogicPublicationEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.LOGIC_PUBLICATION] = Field(alias="evidenceType")
    claims: LogicPublicationClaims


class LogicEvalEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.LOGIC_EVAL] = Field(alias="evidenceType")
    claims: LogicEvalClaims


class WorkshopValidationEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.WORKSHOP_VALIDATION] = Field(alias="evidenceType")
    claims: WorkshopValidationClaims


class ActionSafetyEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.ACTION_SAFETY] = Field(alias="evidenceType")
    claims: ActionSafetyClaims


class OperationsReadinessEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.OPERATIONS_READINESS] = Field(alias="evidenceType")
    claims: OperationsReadinessClaims


class SecurityValidationEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.SECURITY_VALIDATION] = Field(alias="evidenceType")
    claims: SecurityValidationClaims


class RuntimeHealthEvidence(_EvidenceEnvelope):
    evidence_type: Literal[EvidenceType.RUNTIME_HEALTH] = Field(alias="evidenceType")
    claims: RuntimeHealthClaims


IntegrationEvidenceEnvelope: TypeAlias = Annotated[
    SourceConnectionEvidence
    | TenantIsolationEvidence
    | PipelineRunEvidence
    | DatasetRevisionEvidence
    | DataQualityEvidence
    | OntologyRevisionEvidence
    | MappingValidationEvidence
    | LogicPublicationEvidence
    | LogicEvalEvidence
    | WorkshopValidationEvidence
    | ActionSafetyEvidence
    | OperationsReadinessEvidence
    | SecurityValidationEvidence
    | RuntimeHealthEvidence,
    Field(discriminator="evidence_type"),
]
INTEGRATION_EVIDENCE_ADAPTER = TypeAdapter(IntegrationEvidenceEnvelope)


class CreateIntegrationCaseRequest(StrictContract):
    installation_id: str = Field(alias="installationId")
    overlay_revision: str = Field(alias="overlayRevision", max_length=160)
    display_name: str = Field(alias="displayName", max_length=MAX_DISPLAY_NAME_LENGTH)

    @field_validator("installation_id")
    @classmethod
    def _installation_id(cls, value: str) -> str:
        return _canonical_uuid(value, label="installationId")

    @field_validator("overlay_revision", "display_name")
    @classmethod
    def _text(cls, value: str) -> str:
        return _safe_reference(value, label="case request value")


class CreateIntegrationEvidenceSnapshotRequest(StrictContract):
    """The public snapshot command has an intentionally empty JSON body."""


class _IntegrationCaseListItemBase(StrictContract):
    case_id: str = Field(alias="caseId")
    display_name: str = Field(alias="displayName", max_length=MAX_DISPLAY_NAME_LENGTH)
    computed_stage: IntegrationStage = Field(alias="computedStage")
    snapshot_revision: int | None = Field(alias="snapshotRevision", ge=1)
    cutoff_at: datetime | None = Field(alias="cutoffAt")
    blocker_count: int = Field(alias="blockerCount", ge=0)
    etag_version: int = Field(alias="etagVersion", ge=1)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    @field_validator("case_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _canonical_uuid(value, label="caseId")

    @field_validator("computed_stage", mode="before")
    @classmethod
    def _stage(cls, value: object) -> IntegrationStage:
        return _strict_enum(value, IntegrationStage, label="computedStage")  # type: ignore[return-value]

    @field_validator("display_name")
    @classmethod
    def _text(cls, value: str) -> str:
        return _safe_reference(value, label="case value")

    @field_validator("cutoff_at", "created_at", "updated_at")
    @classmethod
    def _times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc_datetime(value, label="case time")


class CurrentIntegrationCaseListItem(_IntegrationCaseListItemBase):
    scope: Literal["current"]
    owner: str = Field(max_length=MAX_REFERENCE_LENGTH)
    installation_id: str = Field(alias="installationId")
    overlay_revision: str = Field(alias="overlayRevision", max_length=160)

    @field_validator("installation_id")
    @classmethod
    def _installation_id(cls, value: str) -> str:
        return _canonical_uuid(value, label="installationId")

    @field_validator("owner", "overlay_revision")
    @classmethod
    def _current_text(cls, value: str) -> str:
        return _safe_reference(value, label="current case value")


class ReferenceIntegrationCaseListItem(_IntegrationCaseListItemBase):
    scope: Literal["reference"]
    owner: None
    installation_id: None = Field(alias="installationId")
    overlay_revision: None = Field(alias="overlayRevision")


IntegrationCaseListItem: TypeAlias = Annotated[
    CurrentIntegrationCaseListItem | ReferenceIntegrationCaseListItem,
    Field(discriminator="scope"),
]


class IntegrationStageGate(StrictContract):
    stage: IntegrationStage
    status: Literal["satisfied", "blocked", "not_evaluated"]
    evidence_refs: list[str] = Field(alias="evidenceRefs", max_length=MAX_REASON_REFS)
    reason_refs: list[str] = Field(alias="reasonRefs", max_length=MAX_REASON_REFS)

    @field_validator("stage", mode="before")
    @classmethod
    def _stage(cls, value: object) -> IntegrationStage:
        return _strict_enum(value, IntegrationStage, label="stage")  # type: ignore[return-value]

    @field_validator("evidence_refs", "reason_refs")
    @classmethod
    def _refs(cls, values: list[str]) -> list[str]:
        return _unique_normalized(values, label="stage gate refs")


def _require_complete_stage_gates(
    gates: list[IntegrationStageGate],
) -> list[IntegrationStageGate]:
    if [gate.stage for gate in gates] != list(IntegrationStage):
        raise ValueError("stageGates must contain all 8 stages in canonical order")
    return gates


class LatestEvidenceSummary(StrictContract):
    evidence_id: str = Field(alias="evidenceId")
    revision: int = Field(ge=1)
    evidence_type: EvidenceType = Field(alias="evidenceType")
    subject_ref: str = Field(alias="subjectRef", max_length=MAX_REFERENCE_LENGTH)
    outcome: EvidenceOutcome
    observed_at: datetime = Field(alias="observedAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")
    artifact_hash: str = Field(alias="artifactHash", pattern=SHA256_PATTERN)
    evidence_hash: str = Field(alias="evidenceHash", pattern=SHA256_PATTERN)
    recorded_at: datetime = Field(alias="recordedAt")

    @field_validator("evidence_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _canonical_uuid(value, label="evidenceId")

    @field_validator("evidence_type", mode="before")
    @classmethod
    def _type(cls, value: object) -> EvidenceType:
        return _strict_enum(value, EvidenceType, label="evidenceType")  # type: ignore[return-value]

    @field_validator("outcome", mode="before")
    @classmethod
    def _outcome(cls, value: object) -> EvidenceOutcome:
        return _strict_enum(value, EvidenceOutcome, label="outcome")  # type: ignore[return-value]

    @field_validator("subject_ref")
    @classmethod
    def _ref(cls, value: str) -> str:
        return _safe_reference(value, label="subjectRef")

    @field_validator("observed_at", "expires_at", "revoked_at", "recorded_at")
    @classmethod
    def _times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc_datetime(value, label="evidence summary time")


class IntegrationMetric(StrictContract):
    value: int | float | None
    aggregation: Literal["count", "distinct_count", "sum", "max"]
    measured_case_count: int = Field(alias="measuredCaseCount", ge=0)
    eligible_case_count: int = Field(alias="eligibleCaseCount", ge=0)
    cutoff_at: datetime = Field(alias="cutoffAt")

    @field_validator("value", mode="before")
    @classmethod
    def _number(cls, value: object) -> object:
        if value is not None and type(value) not in {int, float}:
            raise ValueError("metric value must be a number or null")
        return value

    @field_validator("cutoff_at")
    @classmethod
    def _cutoff(cls, value: datetime) -> datetime:
        return _utc_datetime(value, label="metric cutoffAt")

    @model_validator(mode="after")
    def _counts(self) -> IntegrationMetric:
        if self.measured_case_count > self.eligible_case_count:
            raise ValueError("measuredCaseCount must not exceed eligibleCaseCount")
        return self


class IntegrationCaseMetrics(StrictContract):
    connector_count: IntegrationMetric = Field(alias="connectorCount")
    pipeline_count: IntegrationMetric = Field(alias="pipelineCount")
    dataset_row_count: IntegrationMetric = Field(alias="datasetRowCount")
    latency_ms: IntegrationMetric = Field(alias="latencyMs")


class IntegrationCaseStats(IntegrationCaseMetrics):
    case_count: IntegrationMetric = Field(alias="caseCount")
    production_active_count: IntegrationMetric = Field(alias="productionActiveCount")


class _IntegrationCaseDetailBase(_IntegrationCaseListItemBase):
    stage_gates: list[IntegrationStageGate] = Field(alias="stageGates", max_length=MAX_STAGE_GATES)
    latest_evidence: list[LatestEvidenceSummary] = Field(alias="latestEvidence", max_length=MAX_LATEST_EVIDENCE)
    blockers: list[str] = Field(max_length=MAX_BLOCKERS)
    next_projection_at: datetime | None = Field(alias="nextProjectionAt")

    _complete_gates = field_validator("stage_gates")(_require_complete_stage_gates)

    @field_validator("blockers")
    @classmethod
    def _blockers(cls, values: list[str]) -> list[str]:
        return _unique_normalized(values, label="blockers")

    @field_validator("next_projection_at")
    @classmethod
    def _projection_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc_datetime(value, label="nextProjectionAt")


class CurrentIntegrationCaseDetail(_IntegrationCaseDetailBase):
    scope: Literal["current"]
    owner: str = Field(max_length=MAX_REFERENCE_LENGTH)
    installation_id: str = Field(alias="installationId")
    overlay_revision: str = Field(alias="overlayRevision", max_length=160)
    installation_revision: int = Field(alias="installationRevision", ge=1)
    composition_id: str = Field(alias="compositionId")
    lock_revision: int = Field(alias="lockRevision", ge=1)
    lock_hash: str = Field(alias="lockHash", pattern=SHA256_PATTERN)
    metrics: IntegrationCaseMetrics

    @field_validator("installation_id", "composition_id")
    @classmethod
    def _ids(cls, value: str) -> str:
        return _canonical_uuid(value, label="current detail identifier")

    @field_validator("owner", "overlay_revision")
    @classmethod
    def _current_text(cls, value: str) -> str:
        return _safe_reference(value, label="current case value")


class ReferenceIntegrationCaseDetail(_IntegrationCaseDetailBase):
    scope: Literal["reference"]
    owner: None
    installation_id: None = Field(alias="installationId")
    overlay_revision: None = Field(alias="overlayRevision")
    installation_revision: None = Field(alias="installationRevision")
    composition_id: None = Field(alias="compositionId")
    lock_revision: None = Field(alias="lockRevision")
    lock_hash: None = Field(alias="lockHash")
    metrics: None


IntegrationCaseDetail: TypeAlias = Annotated[
    CurrentIntegrationCaseDetail | ReferenceIntegrationCaseDetail,
    Field(discriminator="scope"),
]
INTEGRATION_CASE_DETAIL_ADAPTER = TypeAdapter(IntegrationCaseDetail)


class IntegrationCaseListResponse(StrictContract):
    items: list[IntegrationCaseListItem] = Field(max_length=MAX_CASE_LIST_LIMIT)
    scope: IntegrationCaseScope
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=MAX_CASE_LIST_LIMIT)
    offset: int = Field(ge=0, le=MAX_CASE_LIST_OFFSET)
    stats: IntegrationCaseStats | None

    @field_validator("scope", mode="before")
    @classmethod
    def _scope(cls, value: object) -> IntegrationCaseScope:
        return _strict_enum(value, IntegrationCaseScope, label="scope")  # type: ignore[return-value]

    @model_validator(mode="after")
    def _scope_consistency(self) -> IntegrationCaseListResponse:
        if any(item.scope != self.scope for item in self.items):
            raise ValueError("response items must match response scope")
        if (self.scope == IntegrationCaseScope.CURRENT) != (self.stats is not None):
            raise ValueError("current stats are required and reference stats must be null")
        return self


class IntegrationEvidenceSnapshot(StrictContract):
    """Internal immutable canonical snapshot; never returned by public reads."""

    case_id: str = Field(alias="caseId")
    snapshot_revision: int = Field(alias="snapshotRevision", ge=1)
    instance_revision: int = Field(alias="instanceRevision", ge=1)
    cutoff_at: datetime = Field(alias="cutoffAt")
    evidence: list[IntegrationEvidenceEnvelope] = Field(max_length=MAX_EVIDENCE_PER_SNAPSHOT)
    snapshot_hash: str = Field(alias="snapshotHash", pattern=SHA256_PATTERN)
    computed_stage: IntegrationStage = Field(alias="computedStage")
    stage_policy_version: Literal[STAGE_POLICY_VERSION] = Field(alias="stagePolicyVersion")

    @field_validator("case_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _canonical_uuid(value, label="caseId")

    @field_validator("computed_stage", mode="before")
    @classmethod
    def _stage(cls, value: object) -> IntegrationStage:
        return _strict_enum(value, IntegrationStage, label="computedStage")  # type: ignore[return-value]

    @field_validator("cutoff_at")
    @classmethod
    def _cutoff(cls, value: datetime) -> datetime:
        return _utc_datetime(value, label="cutoffAt")

    @model_validator(mode="after")
    def _unique_evidence(self) -> IntegrationEvidenceSnapshot:
        keys = [(item.producer, item.series_key) for item in self.evidence]
        if len(keys) != len(set(keys)):
            raise ValueError("snapshot must contain only the latest producer/series revision")
        if keys != sorted(keys):
            raise ValueError("snapshot evidence must use canonical producer/series order")
        return self


class IntegrationEvidenceSnapshotResponse(StrictContract):
    case_id: str = Field(alias="caseId")
    snapshot_revision: int = Field(alias="snapshotRevision", ge=1)
    instance_revision: int = Field(alias="instanceRevision", ge=1)
    cutoff_at: datetime = Field(alias="cutoffAt")
    computed_stage: IntegrationStage = Field(alias="computedStage")
    stage_policy_version: Literal[STAGE_POLICY_VERSION] = Field(alias="stagePolicyVersion")
    snapshot_hash: str = Field(alias="snapshotHash", pattern=SHA256_PATTERN)
    next_projection_at: datetime | None = Field(alias="nextProjectionAt")
    evidence_count: int = Field(alias="evidenceCount", ge=0, le=MAX_EVIDENCE_PER_SNAPSHOT)
    stage_gates: list[IntegrationStageGate] = Field(alias="stageGates", max_length=MAX_STAGE_GATES)
    blocker_refs: list[str] = Field(alias="blockerRefs", max_length=MAX_BLOCKERS)
    etag_version: int = Field(alias="etagVersion", ge=1)
    created_at: datetime = Field(alias="createdAt")

    _complete_gates = field_validator("stage_gates")(_require_complete_stage_gates)

    @field_validator("case_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _canonical_uuid(value, label="caseId")

    @field_validator("computed_stage", mode="before")
    @classmethod
    def _stage(cls, value: object) -> IntegrationStage:
        return _strict_enum(value, IntegrationStage, label="computedStage")  # type: ignore[return-value]

    @field_validator("blocker_refs")
    @classmethod
    def _blockers(cls, values: list[str]) -> list[str]:
        return _unique_normalized(values, label="blockerRefs")

    @field_validator("cutoff_at", "next_projection_at", "created_at")
    @classmethod
    def _times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc_datetime(value, label="snapshot response time")


class IntegrationStageEvent(StrictContract):
    sequence: int = Field(ge=1)
    snapshot_revision: int = Field(alias="snapshotRevision", ge=1)
    old_stage: IntegrationStage | None = Field(default=None, alias="oldStage")
    new_stage: IntegrationStage = Field(alias="newStage")
    cause: Literal[
        "created",
        "evidence_added",
        "negative_observed",
        "evidence_expired",
        "evidence_revoked",
        "projection_rebuilt",
    ]
    reason_refs: list[str] = Field(alias="reasonRefs", max_length=MAX_REASON_REFS)
    created_at: datetime = Field(alias="createdAt")

    @field_validator("old_stage", "new_stage", mode="before")
    @classmethod
    def _stages(cls, value: object) -> IntegrationStage | None:
        if value is None:
            return None
        return _strict_enum(value, IntegrationStage, label="timeline stage")  # type: ignore[return-value]

    @field_validator("reason_refs")
    @classmethod
    def _reasons(cls, values: list[str]) -> list[str]:
        return _unique_normalized(values, label="reasonRefs")

    @field_validator("created_at")
    @classmethod
    def _time(cls, value: datetime) -> datetime:
        return _utc_datetime(value, label="timeline createdAt")


class IntegrationCaseTimelineResponse(StrictContract):
    case_id: str = Field(alias="caseId")
    scope: IntegrationCaseScope
    items: list[IntegrationStageEvent] = Field(max_length=MAX_TIMELINE_ITEMS)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=MAX_TIMELINE_ITEMS)
    offset: int = Field(ge=0, le=MAX_CASE_LIST_OFFSET)

    @field_validator("case_id")
    @classmethod
    def _id(cls, value: str) -> str:
        return _canonical_uuid(value, label="caseId")

    @field_validator("scope", mode="before")
    @classmethod
    def _scope(cls, value: object) -> IntegrationCaseScope:
        return _strict_enum(value, IntegrationCaseScope, label="scope")  # type: ignore[return-value]
