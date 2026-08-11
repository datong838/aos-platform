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


class DatasetSourceKind(StrEnum):
    OBJECT_SNAPSHOT = "object_snapshot"
    SELECTION_SNAPSHOT = "selection_snapshot"
    WIKI_SNAPSHOT = "wiki_snapshot"
    ARTIFACT_SNAPSHOT = "artifact_snapshot"
    EXTERNAL_SNAPSHOT = "external_snapshot"


class DatasetPiiState(StrEnum):
    NONE = "none"
    REDACTED = "redacted"


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
    EVAL_RUN = "eval_run"
    PUBLICATION = "publication"
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


class LineageSourceKind(StrEnum):
    TASK_RUN = "task_run"
    STEP_RUN = "step_run"
    CHECKPOINT = "checkpoint"
    ARTIFACT = "artifact"
    EVIDENCE = "evidence"
    ACTION_EVENT = "action_event"
    ACTION_RECEIPT = "action_receipt"
    EVAL_RUN = "eval_run"
    EVAL_RUN_EVENT = "eval_run_event"
    EVAL_REPORT = "eval_report"
    PUBLICATION_EVENT = "publication_event"


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


class EvalDatasetManifest(AipContractModel):
    """Metadata-only manifest; business rows never live in the registry."""

    source_kind: DatasetSourceKind
    source_id: str = Field(min_length=1, max_length=240)
    source_revision: str = Field(min_length=1, max_length=120)
    source_hash: str = Field(pattern=SHA256_PATTERN)
    fields_allowlist: list[str] = Field(min_length=1)
    redaction_receipt: ArtifactRef
    pii_state: DatasetPiiState
    case_count: int = Field(gt=0)
    captured_at: datetime

    @model_validator(mode="after")
    def _metadata_only(self) -> EvalDatasetManifest:
        fields = [field.strip() for field in self.fields_allowlist]
        if any(not field for field in fields) or len(fields) != len(set(fields)):
            raise ValueError("fields_allowlist must contain unique non-blank fields")
        receipt = self.redaction_receipt
        if not receipt.revision or not receipt.content_hash:
            raise ValueError("redaction_receipt requires exact revision/hash")
        forbidden = {"mock", "synthetic", "demo"}
        source_tokens = {
            token.lower()
            for token in self.source_id.replace(":", "-").replace("_", "-").split("-")
        }
        if forbidden & source_tokens:
            raise ValueError("mock/synthetic/demo datasets are not authoritative")
        return self


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
    def _unique_cases(self) -> EvalSuiteRevision:
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


class EvalRunAuthorityRecord(AipContractModel):
    """Durable run snapshot; large Suite definitions remain separate assets."""

    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    suite_ref: AssetRevisionRef
    target: AssetRevisionRef
    dataset: DatasetRevisionRef
    judge: JudgeRevisionRef
    status: EvalRunStatus
    idempotency_key: str = Field(min_length=1, max_length=200)
    created_by: str = Field(min_length=1, max_length=320)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def _suite_reference(self) -> EvalRunAuthorityRecord:
        if self.suite_ref.asset_type is not AssetType.EVAL_SUITE:
            raise ValueError("suite_ref must reference an eval_suite")
        return self


class EvalRunEvent(AipContractModel):
    tenant: TenantContext
    event_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1)
    event_type: str = Field(min_length=1, max_length=120)
    from_status: EvalRunStatus | None = None
    to_status: EvalRunStatus
    payload_hash: str = Field(pattern=SHA256_PATTERN)
    actor: str = Field(min_length=1, max_length=320)
    created_at: datetime


class EvalCaseResultEvidence(AipContractModel):
    case_id: str = Field(min_length=1, max_length=200)
    passed: bool
    actual_hash: str = Field(pattern=SHA256_PATTERN)
    expected_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    detail_code: str = Field(min_length=1, max_length=120)
    duration_ms: int = Field(ge=0)


class EvalReportRevision(AipContractModel):
    tenant: TenantContext
    report_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    run_id: str = Field(min_length=1, max_length=200)
    suite_ref: AssetRevisionRef
    target: AssetRevisionRef
    dataset: DatasetRevisionRef
    judge: JudgeRevisionRef
    results: list[EvalCaseResultEvidence] = Field(min_length=1)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    total: int = Field(gt=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    gate_passed: bool
    created_at: datetime

    @model_validator(mode="after")
    def _consistent_counts(self) -> EvalReportRevision:
        if self.suite_ref.asset_type is not AssetType.EVAL_SUITE:
            raise ValueError("suite_ref must reference an eval_suite")
        actual_passed = sum(1 for result in self.results if result.passed)
        if (
            self.total != len(self.results)
            or self.passed != actual_passed
            or self.failed != self.total - self.passed
        ):
            raise ValueError("eval report result counts are inconsistent")
        expected_rate = round(self.passed / self.total, 6)
        if abs(self.pass_rate - expected_rate) > 0.000001:
            raise ValueError("eval report pass rate is inconsistent")
        return self


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
    def _invalidation_reason(self) -> ReleaseGateDecision:
        if not self.eval_report.revision or not self.eval_report.content_hash:
            raise ValueError("release gate requires an exact eval report revision/hash")
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
    source_kind: LineageSourceKind | None = None
    source_id: str | None = Field(default=None, min_length=1, max_length=240)
    source_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _observation_not_early(self) -> LineageEvent:
        if self.observed_at < self.occurred_at:
            raise ValueError("observed_at must not precede occurred_at")
        source = (self.source_kind, self.source_id, self.source_hash)
        if any(value is not None for value in source) and not all(
            value is not None for value in source
        ):
            raise ValueError("lineage source kind/id/hash must be provided together")
        if self.root_type is not LineageRootType.LEGACY_DECISION and not all(
            value is not None for value in source
        ):
            raise ValueError("non-legacy lineage requires an authority source")
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
    def _cost_currency(self) -> UsageReceipt:
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
    def _unique_quality(self) -> MetricDefinitionRevision:
        if len(self.accepted_quality) != len(set(self.accepted_quality)):
            raise ValueError("accepted_quality must not contain duplicates")
        return self


__all__ = [
    "AssetRevisionRef",
    "AssetType",
    "DatasetPiiState",
    "DatasetRevisionRef",
    "DatasetSourceKind",
    "EvalCaseDefinition",
    "EvalCaseKind",
    "EvalCaseResultEvidence",
    "EvalDatasetManifest",
    "EvalReportRevision",
    "EvalRunAuthorityRecord",
    "EvalRunEvent",
    "EvalRunRecord",
    "EvalRunStatus",
    "EvalSuiteRevision",
    "EvidenceQuality",
    "JudgeRevisionRef",
    "LineageEvent",
    "LineageEventType",
    "LineageRootType",
    "LineageSourceKind",
    "MetricDefinitionRevision",
    "PublicationEvent",
    "PublicationEventType",
    "ReleaseGateDecision",
    "ReleaseGateStatus",
    "UsageAdjustment",
    "UsageKind",
    "UsageReceipt",
]
