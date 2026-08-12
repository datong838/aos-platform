"""AIP-5 E5 contracts for governed knowledge pipeline control.

These DTOs describe the control plane only.  They never authorize tenant
scope, carry provider credentials, or turn an external checkpoint into AOS
memory authority.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_contracts import SHA256_PATTERN


class KnowledgePipelineKind(StrEnum):
    SEED_IMPORT = "seed_import"
    OPERATIONAL_LEARNING = "operational_learning"
    NETWORK_LEARNING = "network_learning"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    PROFESSIONAL_DATABASE = "professional_database"
    CUSTOMER_FEEDBACK = "customer_feedback"
    HUMAN_EXPERIENCE = "human_experience"


class KnowledgePipelineTrigger(StrEnum):
    MANUAL = "manual"
    TASK_EVENT = "task_event"
    SCHEDULED = "scheduled"
    VERSION_EVENT = "version_event"
    DOMAIN_EVENT = "domain_event"


class KnowledgePipelineScheduleStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class KnowledgePipelineRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class KnowledgePipelineAlertSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


TERMINAL_PIPELINE_RUN_STATUSES = frozenset(
    {
        KnowledgePipelineRunStatus.SUCCEEDED,
        KnowledgePipelineRunStatus.PARTIAL,
        KnowledgePipelineRunStatus.FAILED,
        KnowledgePipelineRunStatus.CANCELLED,
        KnowledgePipelineRunStatus.UNKNOWN,
    }
)


def _require_exact_artifact(value: ArtifactRef, message: str) -> ArtifactRef:
    if (
        not value.revision
        or not value.content_hash
        or len(value.content_hash) != 64
        or any(character not in "0123456789abcdef" for character in value.content_hash)
    ):
        raise ValueError(f"{message} requires exact revision/hash")
    return value


def _require_candidate_refs(values: list[ResourceRef]) -> list[ResourceRef]:
    for value in values:
        if (
            value.resource_type != "aip.memory_candidate"
            or value.authority != "postgresql"
            or not value.revision
        ):
            raise ValueError("candidate refs require exact PostgreSQL memory candidates")
    if len({value.resource_id for value in values}) != len(values):
        raise ValueError("candidate refs must be unique")
    return values


class CreateKnowledgePipelineScheduleRequest(AipContractModel):
    schedule_id: str = Field(min_length=1, max_length=200)
    pipeline_kind: KnowledgePipelineKind
    trigger: KnowledgePipelineTrigger
    config: ArtifactRef
    initial_status: KnowledgePipelineScheduleStatus = KnowledgePipelineScheduleStatus.PAUSED
    schedule_spec: str | None = Field(default=None, min_length=1, max_length=240)

    @model_validator(mode="after")
    def _safe_initial_state(self) -> CreateKnowledgePipelineScheduleRequest:
        _require_exact_artifact(self.config, "pipeline config")
        if self.initial_status is KnowledgePipelineScheduleStatus.ACTIVE:
            raise ValueError("a knowledge pipeline schedule cannot start active")
        if (
            self.trigger is KnowledgePipelineTrigger.SCHEDULED
            and self.schedule_spec is None
        ):
            raise ValueError("scheduled pipeline requires a normalized schedule spec")
        if (
            self.trigger is not KnowledgePipelineTrigger.SCHEDULED
            and self.schedule_spec is not None
        ):
            raise ValueError("schedule spec is only valid for scheduled pipelines")
        return self


class TransitionKnowledgePipelineScheduleRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    from_status: KnowledgePipelineScheduleStatus
    to_status: KnowledgePipelineScheduleStatus
    reason_code: str = Field(min_length=1, max_length=120)
    dependency_review: ResourceRef | None = None

    @model_validator(mode="after")
    def _valid_transition(self) -> TransitionKnowledgePipelineScheduleRequest:
        allowed = {
            KnowledgePipelineScheduleStatus.ACTIVE: {
                KnowledgePipelineScheduleStatus.PAUSED,
                KnowledgePipelineScheduleStatus.DISABLED,
            },
            KnowledgePipelineScheduleStatus.PAUSED: {
                KnowledgePipelineScheduleStatus.ACTIVE,
                KnowledgePipelineScheduleStatus.DISABLED,
            },
            KnowledgePipelineScheduleStatus.DISABLED: {
                KnowledgePipelineScheduleStatus.PAUSED,
            },
        }
        if self.to_status not in allowed[self.from_status]:
            raise ValueError("invalid knowledge pipeline schedule transition")
        if (
            self.from_status is KnowledgePipelineScheduleStatus.DISABLED
            or self.to_status is KnowledgePipelineScheduleStatus.ACTIVE
        ):
            review = self.dependency_review
            if (
                review is None
                or review.resource_type != "aip.eval_report"
                or review.authority != "postgresql"
                or not review.revision
            ):
                raise ValueError(
                    "schedule activation/recovery requires an exact PostgreSQL dependency review"
                )
        return self


class StartKnowledgePipelineRunRequest(AipContractModel):
    pipeline_run_id: str = Field(min_length=1, max_length=200)
    schedule_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    trigger: KnowledgePipelineTrigger
    expected_checkpoint_version: int = Field(ge=0)
    scheduled_for: datetime
    retry_of_run_id: str | None = Field(default=None, min_length=1, max_length=200)


class ClaimKnowledgePipelineRunRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    lease_owner: str = Field(min_length=1, max_length=200)
    lease_seconds: int = Field(ge=1, le=900)


class TransitionKnowledgePipelineRunRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    from_status: KnowledgePipelineRunStatus
    to_status: KnowledgePipelineRunStatus
    reason_code: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def _valid_transition(self) -> TransitionKnowledgePipelineRunRequest:
        allowed = {
            KnowledgePipelineRunStatus.RUNNING: {KnowledgePipelineRunStatus.PAUSED},
            KnowledgePipelineRunStatus.PAUSED: {KnowledgePipelineRunStatus.QUEUED},
        }
        if self.to_status not in allowed.get(self.from_status, set()):
            raise ValueError("invalid recoverable knowledge pipeline run transition")
        return self


class CompleteKnowledgePipelineRunRequest(AipContractModel):
    expected_run_version: int = Field(ge=1)
    status: KnowledgePipelineRunStatus
    input_hash: str = Field(pattern=SHA256_PATTERN)
    output_hash: str = Field(pattern=SHA256_PATTERN)
    candidate_refs: list[ResourceRef] = Field(default_factory=list, max_length=1000)
    checkpoint: ArtifactRef | None = None
    produced_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    error_codes: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("candidate_refs")
    @classmethod
    def _exact_candidates(cls, value: list[ResourceRef]) -> list[ResourceRef]:
        return _require_candidate_refs(value)

    @field_validator("error_codes")
    @classmethod
    def _unique_errors(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("error codes must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _terminal_evidence(self) -> CompleteKnowledgePipelineRunRequest:
        if self.status not in TERMINAL_PIPELINE_RUN_STATUSES:
            raise ValueError("completion status must be terminal")
        if self.produced_count != len(self.candidate_refs):
            raise ValueError("produced count must match exact candidate refs")
        if self.checkpoint is not None:
            _require_exact_artifact(self.checkpoint, "pipeline checkpoint")
            if self.status not in {
                KnowledgePipelineRunStatus.SUCCEEDED,
                KnowledgePipelineRunStatus.PARTIAL,
            }:
                raise ValueError("failed/unknown/cancelled run cannot advance checkpoint")
        if self.status is KnowledgePipelineRunStatus.SUCCEEDED and self.failed_count:
            raise ValueError("succeeded run cannot report failed items")
        if self.status is KnowledgePipelineRunStatus.SUCCEEDED and self.error_codes:
            raise ValueError("succeeded run cannot report error codes")
        if self.status is KnowledgePipelineRunStatus.PARTIAL and not self.failed_count:
            raise ValueError("partial run requires failed items")
        if self.status in {
            KnowledgePipelineRunStatus.PARTIAL,
            KnowledgePipelineRunStatus.FAILED,
            KnowledgePipelineRunStatus.UNKNOWN,
        } and not self.error_codes:
            raise ValueError("partial/failed/unknown run requires error codes")
        return self


class KnowledgePipelineSchedule(AipContractModel):
    tenant: TenantContext
    schedule_id: str
    pipeline_kind: KnowledgePipelineKind
    trigger: KnowledgePipelineTrigger
    config: ArtifactRef
    status: KnowledgePipelineScheduleStatus
    schedule_spec: str | None = None
    checkpoint_version: int = Field(ge=0)
    version: int = Field(ge=1)
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgePipelineRun(AipContractModel):
    tenant: TenantContext
    pipeline_run_id: str
    schedule_id: str
    task_id: str
    run_id: str
    trigger: KnowledgePipelineTrigger
    status: KnowledgePipelineRunStatus
    attempt: int = Field(ge=1)
    retry_of_run_id: str | None = None
    expected_checkpoint_version: int = Field(ge=0)
    idempotency_key: str
    request_hash: str = Field(pattern=SHA256_PATTERN)
    version: int = Field(ge=1)
    scheduled_for: datetime
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _complete_lease(self) -> KnowledgePipelineRun:
        if (self.lease_owner is None) != (self.lease_expires_at is None):
            raise ValueError("pipeline run lease owner/expiry must be present together")
        return self


class KnowledgePipelineScheduleEvent(AipContractModel):
    tenant: TenantContext
    event_id: str
    schedule_id: str
    sequence: int = Field(ge=1)
    event_type: str
    from_status: KnowledgePipelineScheduleStatus | None = None
    to_status: KnowledgePipelineScheduleStatus
    schedule_version: int = Field(ge=1)
    reason_code: str
    dependency_review: ResourceRef | None = None
    event_hash: str = Field(pattern=SHA256_PATTERN)
    actor: str
    occurred_at: datetime


class KnowledgePipelineRunEvent(AipContractModel):
    tenant: TenantContext
    event_id: str
    pipeline_run_id: str
    sequence: int = Field(ge=1)
    event_type: str
    from_status: KnowledgePipelineRunStatus | None = None
    to_status: KnowledgePipelineRunStatus
    run_version: int = Field(ge=1)
    reason_code: str
    lease_owner: str | None = None
    event_hash: str = Field(pattern=SHA256_PATTERN)
    actor: str
    occurred_at: datetime


class KnowledgePipelineReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str
    pipeline_run_id: str
    status: KnowledgePipelineRunStatus
    input_hash: str = Field(pattern=SHA256_PATTERN)
    output_hash: str = Field(pattern=SHA256_PATTERN)
    candidate_refs: list[ResourceRef]
    checkpoint_before_version: int = Field(ge=0)
    checkpoint_after_version: int = Field(ge=0)
    produced_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    error_codes: list[str]
    receipt_hash: str = Field(pattern=SHA256_PATTERN)
    created_at: datetime

    @field_validator("candidate_refs")
    @classmethod
    def _exact_candidates(cls, value: list[ResourceRef]) -> list[ResourceRef]:
        return _require_candidate_refs(value)

    @model_validator(mode="after")
    def _monotonic_checkpoint(self) -> KnowledgePipelineReceipt:
        if self.status not in TERMINAL_PIPELINE_RUN_STATUSES:
            raise ValueError("receipt status must be terminal")
        if self.checkpoint_after_version < self.checkpoint_before_version:
            raise ValueError("checkpoint version cannot move backward")
        if self.status not in {
            KnowledgePipelineRunStatus.SUCCEEDED,
            KnowledgePipelineRunStatus.PARTIAL,
        } and self.checkpoint_after_version != self.checkpoint_before_version:
            raise ValueError("failed/unknown/cancelled receipt cannot advance checkpoint")
        if self.produced_count != len(self.candidate_refs):
            raise ValueError("produced count must match exact candidate refs")
        return self


class KnowledgePipelineCheckpointRevision(AipContractModel):
    tenant: TenantContext
    schedule_id: str
    revision: int = Field(ge=1)
    pipeline_run_id: str
    receipt_id: str
    checkpoint: ArtifactRef
    checkpoint_hash: str = Field(pattern=SHA256_PATTERN)
    created_at: datetime

    @model_validator(mode="after")
    def _exact_checkpoint(self) -> KnowledgePipelineCheckpointRevision:
        _require_exact_artifact(self.checkpoint, "pipeline checkpoint")
        if self.checkpoint.content_hash != self.checkpoint_hash:
            raise ValueError("checkpoint hash must match exact artifact")
        return self


class KnowledgePipelineAlert(AipContractModel):
    tenant: TenantContext
    alert_id: str
    pipeline_run_id: str
    code: str
    severity: KnowledgePipelineAlertSeverity
    evidence_ref: ResourceRef
    alert_hash: str = Field(pattern=SHA256_PATTERN)
    created_at: datetime


__all__ = [
    "ClaimKnowledgePipelineRunRequest",
    "CompleteKnowledgePipelineRunRequest",
    "CreateKnowledgePipelineScheduleRequest",
    "KnowledgePipelineAlert",
    "KnowledgePipelineAlertSeverity",
    "KnowledgePipelineCheckpointRevision",
    "KnowledgePipelineKind",
    "KnowledgePipelineReceipt",
    "KnowledgePipelineRun",
    "KnowledgePipelineRunEvent",
    "KnowledgePipelineRunStatus",
    "KnowledgePipelineSchedule",
    "KnowledgePipelineScheduleEvent",
    "KnowledgePipelineScheduleStatus",
    "KnowledgePipelineTrigger",
    "StartKnowledgePipelineRunRequest",
    "TERMINAL_PIPELINE_RUN_STATUSES",
    "TransitionKnowledgePipelineScheduleRequest",
    "TransitionKnowledgePipelineRunRequest",
]
