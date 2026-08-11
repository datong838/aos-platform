"""AIP-4 public contracts for Evals, release gates, lineage, and usage facts.

The models in this module are intentionally storage-agnostic.  They freeze the
cross-wave envelopes without registering routes, creating stores, or implying
that Agent/Skill registries from later AIP waves already exist.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ArtifactRef, TenantContext


SHA256_PATTERN = r"^[0-9a-f]{64}$"


class AssetType(StrEnum):
    LOGIC_GRAPH = "logic_graph"
    AGENT_TEMPLATE = "agent_template"
    AGENT_INSTANCE = "agent_instance"
    SKILL_TEMPLATE = "skill_template"
    MODEL_ROUTE = "model_route"
    POLICY = "policy"
    WIKI_SNAPSHOT = "wiki_snapshot"
    FDE_BUNDLE = "fde_bundle"
    CONTENT_PIPELINE = "content_pipeline"
    SCENARIO = "scenario"
    RESEARCH_PROVIDER = "research_provider"
    EVAL_SUITE = "eval_suite"
    EVAL_REPORT = "eval_report"
    RELEASE_GATE = "release_gate"


class EvidenceQuality(StrEnum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class EvalCaseKind(StrEnum):
    POSITIVE = "positive"
    BOUNDARY = "boundary"
    NEGATIVE = "negative"
    TENANT = "tenant"
    TOOL_FAILURE = "tool_failure"
    INJECTION = "injection"
    PII = "pii"


class EvalRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ReleaseGateStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    INVALIDATED = "invalidated"


class PublicationEventType(StrEnum):
    PUBLISHED = "published"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"


class LineageRootType(StrEnum):
    TASK_RUN = "task_run"
    ACTION = "action"
    RESEARCH_JOB = "research_job"
    LEGACY_DECISION = "legacy_decision_lineage"


class LineageEventType(StrEnum):
    INPUT = "input"
    RETRIEVAL = "retrieval"
    MODEL = "model"
    TOOL = "tool"
    ACTION = "action"
    ARTIFACT = "artifact"
    EVAL = "eval"
    APPROVAL = "approval"
    RECEIPT = "receipt"
    EFFECT_REVIEW = "effect_review"
    MEMORY_CANDIDATE = "memory_candidate"
    FALLBACK = "fallback"
    RECONCILE = "reconcile"
    ERROR = "error"


class UsageKind(StrEnum):
    INPUT_TOKEN = "input_token"
    OUTPUT_TOKEN = "output_token"
    CACHED_TOKEN = "cached_token"
    COST = "cost"
    LATENCY = "latency"
    TOOL_UNIT = "tool_unit"


class AssetRevisionRef(AipContractModel):
    asset_type: AssetType
    asset_id: str = Field(min_length=1, max_length=200)
    revision: str = Field(min_length=1, max_length=120)
    content_hash: str = Field(pattern=SHA256_PATTERN)

    @field_validator("asset_id", "revision")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("asset reference values must not be blank")
        return cleaned


class DatasetRevisionRef(AipContractModel):
    dataset_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    source_hash: str = Field(pattern=SHA256_PATTERN)
    redaction_policy: AssetRevisionRef


class JudgeRevisionRef(AipContractModel):
    judge_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    model_route: AssetRevisionRef | None = None


class EvalCaseDefinition(AipContractModel):
    case_id: str = Field(min_length=1, max_length=200)
    kind: EvalCaseKind
    input_artifact: ArtifactRef
    expected_artifact: ArtifactRef | None = None
    timeout_ms: int = Field(gt=0, le=3_600_000)
    required: bool = True


class EvalSuiteRevision(AipContractModel):
    suite_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    target: AssetRevisionRef
    dataset: DatasetRevisionRef
    judge: JudgeRevisionRef
    cases: list[EvalCaseDefinition] = Field(min_length=1)
    gate_threshold: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _unique_cases(self) -> "EvalSuiteRevision":
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("eval case ids must be unique inside a suite revision")
        return self


class EvalRunRecord(AipContractModel):
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    suite: EvalSuiteRevision
    status: EvalRunStatus
    idempotency_key: str = Field(min_length=1, max_length=200)
    created_by: str = Field(min_length=1, max_length=320)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    version: int = Field(ge=1)


class ReleaseGateDecision(AipContractModel):
    tenant: TenantContext
    decision_id: str = Field(min_length=1, max_length=200)
    target: AssetRevisionRef
    suite_ref: AssetRevisionRef
    eval_run_id: str = Field(min_length=1, max_length=200)
    eval_report: ArtifactRef
    status: ReleaseGateStatus
    decision_hash: str = Field(pattern=SHA256_PATTERN)
    decided_by: str = Field(min_length=1, max_length=320)
    decided_at: datetime
    invalidated_by: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _invalidation_reason(self) -> "ReleaseGateDecision":
        if self.status is ReleaseGateStatus.INVALIDATED and not self.invalidated_by:
            raise ValueError("invalidated gate requires invalidated_by")
        if self.status is not ReleaseGateStatus.INVALIDATED and self.invalidated_by:
            raise ValueError("only invalidated gate may carry invalidated_by")
        return self


class PublicationEvent(AipContractModel):
    tenant: TenantContext
    event_id: str = Field(min_length=1, max_length=200)
    publication_id: str = Field(min_length=1, max_length=200)
    target: AssetRevisionRef
    event_type: PublicationEventType
    release_gate_decision_id: str = Field(min_length=1, max_length=200)
    reason_hash: str = Field(pattern=SHA256_PATTERN)
    actor: str = Field(min_length=1, max_length=320)
    occurred_at: datetime


class LineageEvent(AipContractModel):
    tenant: TenantContext
    event_id: str = Field(min_length=1, max_length=200)
    lineage_id: str = Field(min_length=1, max_length=200)
    root_type: LineageRootType
    root_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1)
    event_type: LineageEventType
    subject: AssetRevisionRef | None = None
    artifact: ArtifactRef | None = None
    payload_hash: str = Field(pattern=SHA256_PATTERN)
    quality: EvidenceQuality
    occurred_at: datetime
    observed_at: datetime

    @model_validator(mode="after")
    def _observation_not_early(self) -> "LineageEvent":
        if self.observed_at < self.occurred_at:
            raise ValueError("observed_at must not precede occurred_at")
        return self


class UsageReceipt(AipContractModel):
    tenant: TenantContext
    receipt_id: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=200)
    provider_receipt_id: str = Field(min_length=1, max_length=240)
    lineage_id: str = Field(min_length=1, max_length=200)
    usage_kind: UsageKind
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=40)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    quality: EvidenceQuality
    source_hash: str = Field(pattern=SHA256_PATTERN)
    observed_at: datetime

    @model_validator(mode="after")
    def _cost_currency(self) -> "UsageReceipt":
        if self.usage_kind is UsageKind.COST and self.currency is None:
            raise ValueError("cost receipt requires currency")
        if self.usage_kind is not UsageKind.COST and self.currency is not None:
            raise ValueError("currency is only valid for cost receipts")
        return self


class UsageAdjustment(AipContractModel):
    tenant: TenantContext
    adjustment_id: str = Field(min_length=1, max_length=200)
    receipt_id: str = Field(min_length=1, max_length=200)
    delta: float
    reason_hash: str = Field(pattern=SHA256_PATTERN)
    actor: str = Field(min_length=1, max_length=320)
    created_at: datetime


class MetricDefinitionRevision(AipContractModel):
    metric_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=200)
    window: str = Field(min_length=1, max_length=80)
    aggregation: str = Field(min_length=1, max_length=80)
    accepted_quality: list[EvidenceQuality] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_quality(self) -> "MetricDefinitionRevision":
        if len(self.accepted_quality) != len(set(self.accepted_quality)):
            raise ValueError("accepted_quality must not contain duplicates")
        return self


__all__ = [
    "AssetRevisionRef",
    "AssetType",
    "DatasetRevisionRef",
    "EvalCaseDefinition",
    "EvalCaseKind",
    "EvalRunRecord",
    "EvalRunStatus",
    "EvalSuiteRevision",
    "EvidenceQuality",
    "JudgeRevisionRef",
    "LineageEvent",
    "LineageEventType",
    "LineageRootType",
    "MetricDefinitionRevision",
    "PublicationEvent",
    "PublicationEventType",
    "ReleaseGateDecision",
    "ReleaseGateStatus",
    "UsageAdjustment",
    "UsageKind",
    "UsageReceipt",
]
