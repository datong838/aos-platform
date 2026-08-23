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
from aos_api.aip_memory_contracts import (
    SHA256_PATTERN,
    KnowledgeScope,
    KnowledgeSourceKind,
    KnowledgeSourceRef,
    RuntimeMemoryLayer,
)


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


class KnowledgePipelineDependencyStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class KnowledgePipelineOperationalStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    PAUSED = "paused"
    DISABLED = "disabled"
    UNCONFIGURED = "unconfigured"


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


class KnowledgePipelineDependencyResult(AipContractModel):
    dependency: str = Field(min_length=1, max_length=120)
    status: KnowledgePipelineDependencyStatus
    evidence_ref: ResourceRef | None = None
    reason_code: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("dependency")
    @classmethod
    def _dependency_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("dependency name must not be blank")
        return cleaned

    @model_validator(mode="after")
    def _evidence_shape(self) -> KnowledgePipelineDependencyResult:
        if self.status is KnowledgePipelineDependencyStatus.AVAILABLE:
            evidence = self.evidence_ref
            if (
                evidence is None
                or evidence.resource_type != "aip.eval_report"
                or evidence.authority != "postgresql"
                or not evidence.revision
            ):
                raise ValueError("available dependency requires exact PostgreSQL evidence")
            if self.reason_code is not None:
                raise ValueError("available dependency cannot carry a failure reason")
        elif self.reason_code is None:
            raise ValueError("unavailable/unknown dependency requires a reason")
        return self


class KnowledgePipelineDependencySnapshot(AipContractModel):
    pipeline_kind: KnowledgePipelineKind
    review_ref: ResourceRef
    review_hash: str = Field(pattern=SHA256_PATTERN)
    dependencies: list[KnowledgePipelineDependencyResult] = Field(
        min_length=1, max_length=64
    )
    reviewed_at: datetime
    expires_at: datetime

    @field_validator("dependencies")
    @classmethod
    def _unique_dependencies(
        cls, value: list[KnowledgePipelineDependencyResult]
    ) -> list[KnowledgePipelineDependencyResult]:
        names = [item.dependency for item in value]
        if len(names) != len(set(names)):
            raise ValueError("dependency snapshot entries must be unique")
        return value

    @model_validator(mode="after")
    def _exact_review(self) -> KnowledgePipelineDependencySnapshot:
        if (
            self.review_ref.resource_type != "aip.eval_report"
            or self.review_ref.authority != "postgresql"
            or not self.review_ref.revision
        ):
            raise ValueError("dependency snapshot requires exact PostgreSQL eval report")
        if self.reviewed_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("dependency snapshot timestamps require timezones")
        if self.expires_at <= self.reviewed_at:
            raise ValueError("dependency snapshot expiry must follow review time")
        return self


class KnowledgePipelinePolicy(AipContractModel):
    pipeline_kind: KnowledgePipelineKind
    allowed_triggers: list[KnowledgePipelineTrigger] = Field(min_length=1)
    default_status: KnowledgePipelineScheduleStatus
    required_dependencies: list[str] = Field(min_length=1)
    allowed_receipt_types: list[str] = Field(min_length=1)
    allowed_source_kinds: list[KnowledgeSourceKind] = Field(min_length=1)

    @field_validator(
        "allowed_triggers",
        "required_dependencies",
        "allowed_receipt_types",
        "allowed_source_kinds",
    )
    @classmethod
    def _unique_policy_values(cls, value: list[object]) -> list[object]:
        normalized = [str(item) for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("pipeline policy values must be unique")
        return value


class KnowledgePipelineStatusCount(AipContractModel):
    status: str = Field(min_length=1, max_length=64)
    count: int = Field(ge=0)


class KnowledgePipelineActivitySnapshot(AipContractModel):
    pipeline_kind: KnowledgePipelineKind
    schedule_counts: list[KnowledgePipelineStatusCount] = Field(default_factory=list)
    run_counts: list[KnowledgePipelineStatusCount] = Field(default_factory=list)
    last_run: KnowledgePipelineRun | None = None
    last_receipt: KnowledgePipelineReceipt | None = None
    last_checkpoint: KnowledgePipelineCheckpointRevision | None = None
    alert_count: int = Field(default=0, ge=0)


class KnowledgePipelineOperationalReadiness(AipContractModel):
    tenant: TenantContext
    pipeline_kind: KnowledgePipelineKind
    default_status: KnowledgePipelineScheduleStatus
    dependency_allowed: bool
    dependency_reason_codes: list[str]
    adapter_required: bool
    adapter_registered: bool
    schedule_counts: list[KnowledgePipelineStatusCount]
    run_counts: list[KnowledgePipelineStatusCount]
    last_run: KnowledgePipelineRun | None = None
    last_receipt: KnowledgePipelineReceipt | None = None
    last_checkpoint: KnowledgePipelineCheckpointRevision | None = None
    alert_count: int = Field(ge=0)
    operational_status: KnowledgePipelineOperationalStatus
    blocker_codes: list[str]
    observed_at: datetime

    @model_validator(mode="after")
    def _consistent_operational_state(self) -> KnowledgePipelineOperationalReadiness:
        if len(self.blocker_codes) != len(set(self.blocker_codes)):
            raise ValueError("pipeline readiness blockers must be unique")
        if self.operational_status is KnowledgePipelineOperationalStatus.READY:
            if self.blocker_codes or not self.dependency_allowed:
                raise ValueError("ready pipeline cannot carry blockers")
        elif not self.blocker_codes:
            raise ValueError("non-ready pipeline requires blockers")
        if not self.adapter_required and not self.adapter_registered:
            raise ValueError("pipeline without adapter requirement is adapter-ready by definition")
        return self


class KnowledgePipelineOperationalReadinessEnvelope(AipContractModel):
    tenant: TenantContext
    pipelines: list[KnowledgePipelineOperationalReadiness]
    observed_at: datetime

    @field_validator("pipelines")
    @classmethod
    def _all_pipeline_kinds_once(
        cls, value: list[KnowledgePipelineOperationalReadiness]
    ) -> list[KnowledgePipelineOperationalReadiness]:
        kinds = [item.pipeline_kind for item in value]
        if len(kinds) != len(KnowledgePipelineKind) or set(kinds) != set(KnowledgePipelineKind):
            raise ValueError("pipeline readiness requires all seven unique kinds")
        return value


class TrustedKnowledgeAdapterDefinition(AipContractModel):
    adapter_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    contract_hash: str = Field(pattern=SHA256_PATTERN)
    pipeline_kinds: list[KnowledgePipelineKind] = Field(min_length=1)
    receipt_types: list[str] = Field(min_length=1)
    source_kinds: list[KnowledgeSourceKind] = Field(min_length=1)

    @field_validator("adapter_id")
    @classmethod
    def _adapter_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("adapter id must not be blank")
        return cleaned

    @field_validator("pipeline_kinds", "receipt_types", "source_kinds")
    @classmethod
    def _unique_adapter_values(cls, value: list[object]) -> list[object]:
        normalized = [str(item) for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("adapter definition values must be unique")
        return value


class KnowledgePipelineInputReceipt(AipContractModel):
    tenant: TenantContext
    receipt_ref: ResourceRef
    artifact: ArtifactRef
    task_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    source: KnowledgeSourceRef

    @model_validator(mode="after")
    def _exact_authority(self) -> KnowledgePipelineInputReceipt:
        if self.receipt_ref.authority != "postgresql" or not self.receipt_ref.revision:
            raise ValueError("pipeline input requires exact PostgreSQL receipt")
        _require_exact_artifact(self.artifact, "pipeline input artifact")
        if self.source.source_ref != self.receipt_ref or self.source.source_uri is not None:
            raise ValueError("pipeline input source must bind its exact receipt")
        if self.source.content_hash != self.artifact.content_hash:
            raise ValueError("pipeline input source hash must match its artifact")
        return self


class TrustedKnowledgeCandidateDraft(AipContractModel):
    candidate_id: str = Field(min_length=1, max_length=200)
    source_id: str = Field(min_length=1, max_length=200)
    source_revision: int = Field(ge=1)
    knowledge_scope: KnowledgeScope
    candidate_layer: RuntimeMemoryLayer
    subject: ResourceRef
    confidence: float = Field(ge=0.0, le=1.0)
    marking: list[str] = Field(min_length=1, max_length=32)

    @field_validator("marking")
    @classmethod
    def _unique_markings(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("candidate markings must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _promotable_layer(self) -> TrustedKnowledgeCandidateDraft:
        if self.candidate_layer is RuntimeMemoryLayer.WORKING:
            raise ValueError("adapter cannot create working memory candidates")
        return self


__all__ = [
    "ClaimKnowledgePipelineRunRequest",
    "CompleteKnowledgePipelineRunRequest",
    "CreateKnowledgePipelineScheduleRequest",
    "KnowledgePipelineAlert",
    "KnowledgePipelineAlertSeverity",
    "KnowledgePipelineCheckpointRevision",
    "KnowledgePipelineDependencyResult",
    "KnowledgePipelineDependencySnapshot",
    "KnowledgePipelineDependencyStatus",
    "KnowledgePipelineInputReceipt",
    "KnowledgePipelineKind",
    "KnowledgePipelinePolicy",
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
    "TrustedKnowledgeAdapterDefinition",
    "TrustedKnowledgeCandidateDraft",
]
