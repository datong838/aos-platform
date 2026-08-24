"""Tenant-bound W3-13 ecommerce analyst authority contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext


class AnalystExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class InsightKind(StrEnum):
    OBSERVATION = "observation"
    CORRELATION = "correlation"
    ATTRIBUTION = "attribution"
    CAUSAL_CLAIM = "causal_claim"


class GrowthPlanLifecycle(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class EffectReviewStatus(StrEnum):
    PENDING = "pending"
    MATURE = "mature"
    INCONCLUSIVE = "inconclusive"
    UNKNOWN = "unknown"
    CORRECTED = "corrected"


def _require_type(ref: AnalystExactRef | None, expected: set[str], name: str) -> None:
    if ref is not None and ref.resource_type not in expected:
        raise ValueError(f"{name} must reference {sorted(expected)}")


def _unique_refs(refs: list[AnalystExactRef], name: str) -> list[AnalystExactRef]:
    keys = [(ref.resource_type, ref.resource_id, ref.revision) for ref in refs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{name} must be unique")
    return refs


class _RevisionBase(AipContractModel):
    tenant: TenantContext
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    prior_ref: AnalystExactRef | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("createdAt must include a timezone")
        return value

    def _validate_chain(self, identity: str, resource_type: str) -> None:
        if self.version != self.revision:
            raise ValueError("version must equal revision")
        if (self.revision == 1) != (self.prior_ref is None):
            raise ValueError("revisions after r1 require priorRef")
        _require_type(self.prior_ref, {resource_type}, "priorRef")
        if self.prior_ref is not None:
            if self.prior_ref.resource_id != identity:
                raise ValueError("priorRef must retain identity")
            if self.prior_ref.revision != self.revision - 1:
                raise ValueError("priorRef must target the preceding revision")


class InsightRevision(_RevisionBase):
    insight_id: str = Field(min_length=1, max_length=200)
    kind: InsightKind
    summary: str = Field(min_length=1, max_length=4000)
    metric_refs: list[AnalystExactRef] = Field(min_length=1, max_length=100)
    evidence_refs: list[AnalystExactRef] = Field(min_length=1, max_length=100)
    method_ref: AnalystExactRef
    eval_ref: AnalystExactRef
    cutoff_at: datetime
    assumptions: list[str] = Field(default_factory=list, max_length=50)
    uncertainty: str = Field(min_length=1, max_length=2000)

    @field_validator("cutoff_at")
    @classmethod
    def _aware_cutoff(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("cutoffAt must include a timezone")
        return value

    @field_validator("metric_refs")
    @classmethod
    def _metric_refs(cls, value: list[AnalystExactRef]) -> list[AnalystExactRef]:
        _unique_refs(value, "metricRefs")
        for ref in value:
            _require_type(ref, {"MetricDefinitionRevision", "MetricObservationRevision"}, "metricRefs")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_refs(cls, value: list[AnalystExactRef]) -> list[AnalystExactRef]:
        _unique_refs(value, "evidenceRefs")
        for ref in value:
            _require_type(ref, {"EvidenceBundleRevision"}, "evidenceRefs")
        return value

    @model_validator(mode="after")
    def _integrity(self) -> "InsightRevision":
        self._validate_chain(self.insight_id, "InsightRevision")
        _require_type(self.method_ref, {"MethodRevision"}, "methodRef")
        _require_type(self.eval_ref, {"EvalContractRevision", "EvalRunRevision"}, "evalRef")
        return self


class DecisionSummaryRevision(_RevisionBase):
    decision_id: str = Field(min_length=1, max_length=200)
    insight_ref: AnalystExactRef
    conclusion: str = Field(min_length=1, max_length=4000)
    evidence_refs: list[AnalystExactRef] = Field(min_length=1, max_length=100)
    attribution_path: list[str] = Field(min_length=1, max_length=100)
    key_assumptions: list[str] = Field(default_factory=list, max_length=50)
    counter_evidence: list[str] = Field(default_factory=list, max_length=50)
    alternative_explanations: list[str] = Field(default_factory=list, max_length=50)
    uncertainty: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _integrity(self) -> "DecisionSummaryRevision":
        self._validate_chain(self.decision_id, "DecisionSummaryRevision")
        _require_type(self.insight_ref, {"InsightRevision"}, "insightRef")
        _unique_refs(self.evidence_refs, "evidenceRefs")
        for ref in self.evidence_refs:
            _require_type(ref, {"EvidenceBundleRevision"}, "evidenceRefs")
        return self


class GrowthPlanItem(AipContractModel):
    item_id: str = Field(min_length=1, max_length=200)
    task_type: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    objective: str = Field(min_length=1, max_length=2000)
    priority: int = Field(default=50, ge=0, le=100)
    eligible: bool = True


class GrowthPlanRevision(_RevisionBase):
    plan_id: str = Field(min_length=1, max_length=200)
    lifecycle: GrowthPlanLifecycle
    decision_ref: AnalystExactRef
    objective: str = Field(min_length=1, max_length=4000)
    constraints: list[str] = Field(default_factory=list, max_length=100)
    budget: str = Field(pattern=r"^(0|[1-9][0-9]*)([.][0-9]{1,6})?$")
    expected_effect: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    stop_conditions: list[str] = Field(min_length=1, max_length=100)
    items: list[GrowthPlanItem] = Field(min_length=1, max_length=500)
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def _integrity(self) -> "GrowthPlanRevision":
        self._validate_chain(self.plan_id, "GrowthPlanRevision")
        _require_type(self.decision_ref, {"DecisionSummaryRevision"}, "decisionRef")
        ids = [item.item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("plan itemId must be unique")
        if self.lifecycle is GrowthPlanLifecycle.APPROVED:
            if self.approved_at is None or self.approved_at.utcoffset() is None:
                raise ValueError("approved plans require timezone-aware approvedAt")
        elif self.approved_at is not None:
            raise ValueError("only approved plans may carry approvedAt")
        return self


class TaskGraphMapping(AipContractModel):
    plan_item_id: str = Field(min_length=1, max_length=200)
    task_ref: AnalystExactRef

    @model_validator(mode="after")
    def _task_type(self) -> "TaskGraphMapping":
        _require_type(self.task_ref, {"Task"}, "taskRef")
        return self


class TaskGraphRevision(_RevisionBase):
    graph_id: str = Field(min_length=1, max_length=200)
    plan_ref: AnalystExactRef
    eligible_plan_item_count: int = Field(ge=0)
    canonical_task_count: int = Field(ge=0)
    mappings: list[TaskGraphMapping] = Field(max_length=500)
    materialized_at: datetime

    @model_validator(mode="after")
    def _integrity(self) -> "TaskGraphRevision":
        self._validate_chain(self.graph_id, "TaskGraphRevision")
        _require_type(self.plan_ref, {"GrowthPlanRevision"}, "planRef")
        if self.materialized_at.utcoffset() is None:
            raise ValueError("materializedAt must include a timezone")
        item_ids = [item.plan_item_id for item in self.mappings]
        task_ids = [item.task_ref.resource_id for item in self.mappings]
        if len(item_ids) != len(set(item_ids)) or len(task_ids) != len(set(task_ids)):
            raise ValueError("TaskGraph mappings must be one-to-one")
        if not (self.eligible_plan_item_count == self.canonical_task_count == len(self.mappings)):
            raise ValueError("TaskGraph count conservation failed")
        return self


class EcommerceEffectReviewRevision(_RevisionBase):
    review_id: str = Field(min_length=1, max_length=200)
    plan_ref: AnalystExactRef
    task_graph_ref: AnalystExactRef
    action_receipt_refs: list[AnalystExactRef] = Field(default_factory=list, max_length=500)
    baseline: str = Field(min_length=1, max_length=2000)
    comparison: str = Field(min_length=1, max_length=2000)
    maturity_window: str = Field(min_length=1, max_length=500)
    eligible_population: str = Field(min_length=1, max_length=1000)
    method_ref: AnalystExactRef
    assumptions: list[str] = Field(default_factory=list, max_length=50)
    limitations: list[str] = Field(min_length=1, max_length=50)
    counterfactual_limitations: list[str] = Field(min_length=1, max_length=50)
    status: EffectReviewStatus
    effect_value: str | None = None
    memory_candidate_ref: AnalystExactRef | None = None

    @model_validator(mode="after")
    def _integrity(self) -> "EcommerceEffectReviewRevision":
        self._validate_chain(self.review_id, "EcommerceEffectReviewRevision")
        _require_type(self.plan_ref, {"GrowthPlanRevision"}, "planRef")
        _require_type(self.task_graph_ref, {"TaskGraphRevision"}, "taskGraphRef")
        _require_type(self.method_ref, {"MethodRevision"}, "methodRef")
        _require_type(self.memory_candidate_ref, {"MemoryCandidate"}, "memoryCandidateRef")
        for ref in self.action_receipt_refs:
            _require_type(ref, {"ActionReceipt"}, "actionReceiptRefs")
        _unique_refs(self.action_receipt_refs, "actionReceiptRefs")
        if self.status not in {EffectReviewStatus.MATURE, EffectReviewStatus.CORRECTED} and self.effect_value is not None:
            raise ValueError("effectValue requires a mature or corrected review")
        if self.status in {EffectReviewStatus.MATURE, EffectReviewStatus.CORRECTED} and self.effect_value is None:
            raise ValueError("mature or corrected reviews require effectValue")
        return self


class AnalystAuthorityReceipt(AipContractModel):
    receipt_id: str
    operation: str
    idempotency_key: str
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_ref: AnalystExactRef
    created_by: str
    created_at: datetime
