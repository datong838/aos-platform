"""Fail-closed G0/G1 ecommerce daily operating-loop contracts.

The module is a SolutionPack-facing domain compiler.  It reuses canonical AIP
Plan, Task and EffectReview authorities through exact references and performs
no persistence, model, adapter, scheduler, approval or production action.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef


SOURCE_IDS = tuple(f"P{index:02d}" for index in range(1, 13))
LOGIC_IDS = tuple(f"D{index:02d}" for index in range(1, 7))


def _exact_type(value: ExactRevisionRef, expected: str, label: str) -> None:
    if value.resource_type != expected:
        raise ValueError(f"{label} must reference {expected}")


def _same_exact_ref(left: ExactRevisionRef, right: ExactRevisionRef) -> bool:
    return (
        left.resource_type,
        left.resource_id,
        left.revision,
        left.content_hash,
    ) == (
        right.resource_type,
        right.resource_id,
        right.revision,
        right.content_hash,
    )


class SourceRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STALE = "stale"
    UNKNOWN = "unknown"


class DailyOperatingState(StrEnum):
    READY_FOR_PLAN_REVIEW = "ready_for_plan_review"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"


class EffectOutcome(StrEnum):
    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"
    HARMFUL = "harmful"
    INCONCLUSIVE = "inconclusive"
    NOT_EXECUTED = "not_executed"


class EffectMaturity(StrEnum):
    IMMATURE = "immature"
    MATURE = "mature"
    INSUFFICIENT = "insufficient"
    UNKNOWN = "unknown"


class DailySourceObservation(AipContractModel):
    source_id: str = Field(pattern=r"^P(?:0[1-9]|1[0-2])$")
    latest_run_ref: ExactRevisionRef
    cutoff_at: datetime
    fresh_until: datetime
    status: SourceRunStatus
    reconciliation_passed: bool
    source_count: int = Field(ge=0)
    projection_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _source_integrity(self) -> "DailySourceObservation":
        _exact_type(self.latest_run_ref, "PipelineRunRevision", "latestRunRef")
        for label, value in (("cutoffAt", self.cutoff_at), ("freshUntil", self.fresh_until)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{label} must be timezone-aware")
        if self.fresh_until <= self.cutoff_at:
            raise ValueError("freshUntil must be after cutoffAt")
        return self


class DailyLogicStage(AipContractModel):
    order: int = Field(ge=1, le=6)
    logic_id: str = Field(pattern=r"^D0[1-6]$")
    logic_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _logic_exactness(self) -> "DailyLogicStage":
        _exact_type(self.logic_ref, "LogicGraphRevision", "logicRef")
        if self.logic_ref.resource_id != f"ecommerce.logic.{self.logic_id}":
            raise ValueError("logicRef must bind the canonical ecommerce Logic ID")
        return self


class DailyOperatingInput(AipContractModel):
    source_evidence_pack_ref: ExactRevisionRef
    source_observations: list[DailySourceObservation] = Field(min_length=12, max_length=12)
    research_evidence_refs: list[ExactRevisionRef] = Field(default_factory=list, max_length=32)
    wiki_snapshot_ref: ExactRevisionRef
    okf_mapping_ref: ExactRevisionRef
    logic_stages: list[DailyLogicStage] = Field(min_length=6, max_length=6)
    objective: str = Field(min_length=1, max_length=1000)
    baseline: str = Field(min_length=1, max_length=2000)
    target: str = Field(min_length=1, max_length=2000)
    constraints: list[str] = Field(min_length=1, max_length=32)
    guardrails: list[str] = Field(min_length=1, max_length=32)
    budget_limit: str = Field(min_length=1, max_length=500)
    stop_conditions: list[str] = Field(min_length=1, max_length=32)
    expected_effect: str = Field(min_length=1, max_length=2000)
    observed_at: datetime

    @field_validator("constraints", "guardrails", "stop_conditions")
    @classmethod
    def _unique_non_blank(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("list values must be unique and non-blank")
        return normalized

    @model_validator(mode="after")
    def _composition_integrity(self) -> "DailyOperatingInput":
        _exact_type(
            self.source_evidence_pack_ref,
            "SourceReadinessEvidencePackRevision",
            "sourceEvidencePackRef",
        )
        _exact_type(self.wiki_snapshot_ref, "WikiSnapshotRevision", "wikiSnapshotRef")
        _exact_type(self.okf_mapping_ref, "OkfMappingRevision", "okfMappingRef")
        for value in self.research_evidence_refs:
            _exact_type(value, "IntelligenceEvidenceRevision", "researchEvidenceRefs")
        if [value.source_id for value in self.source_observations] != list(SOURCE_IDS):
            raise ValueError("sourceObservations must contain ordered P01 through P12")
        actual_logic = [(value.order, value.logic_id) for value in self.logic_stages]
        if actual_logic != list(enumerate(LOGIC_IDS, start=1)):
            raise ValueError("logicStages must contain ordered D01 through D06")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observedAt must be timezone-aware")
        return self


class GrowthPlanSpec(AipContractModel):
    status: Literal["draft"] = "draft"
    objective: str
    baseline: str
    target: str
    constraints: list[str]
    guardrails: list[str]
    budget_limit: str
    stop_conditions: list[str]
    expected_effect: str
    data_cutoff_at: datetime
    evidence_refs: list[ExactRevisionRef] = Field(min_length=4, max_length=64)
    production_written: Literal[False] = False


class TaskGraphMaterializationProposal(AipContractModel):
    tenant: TenantContext
    status: Literal["draft"] = "draft"
    plan_ref: ExactRevisionRef
    approval_ref: ExactRevisionRef
    canonical_logic_ids: list[str] = Field(default_factory=lambda: list(LOGIC_IDS))
    execution_authorized: Literal[False] = False
    production_written: Literal[False] = False

    @model_validator(mode="after")
    def _exact_authorities(self) -> "TaskGraphMaterializationProposal":
        _exact_type(self.plan_ref, "GrowthPlanRevision", "planRef")
        _exact_type(self.approval_ref, "GrowthApprovalEventRevision", "approvalRef")
        if self.canonical_logic_ids != list(LOGIC_IDS):
            raise ValueError("canonicalLogicIds must remain D01 through D06")
        return self


class GrowthEffectBinding(AipContractModel):
    effect_review_ref: ExactRevisionRef
    accepted: bool
    effect_completed: bool
    maturity_status: EffectMaturity
    outcome: EffectOutcome

    @model_validator(mode="after")
    def _separate_axes(self) -> "GrowthEffectBinding":
        _exact_type(self.effect_review_ref, "EffectReviewRevision", "effectReviewRef")
        if self.effect_completed and self.maturity_status is not EffectMaturity.MATURE:
            raise ValueError("effectCompleted requires mature EffectReview authority")
        if self.maturity_status is not EffectMaturity.MATURE and self.outcome in {
            EffectOutcome.EFFECTIVE,
            EffectOutcome.INEFFECTIVE,
            EffectOutcome.HARMFUL,
        }:
            raise ValueError("non-mature review cannot claim a conclusive effect outcome")
        return self


class DailyOperatingCompilation(AipContractModel):
    tenant: TenantContext
    state: DailyOperatingState
    blockers: list[ContractBlocker]
    plan_spec: GrowthPlanSpec | None = None
    task_graph_proposal: TaskGraphMaterializationProposal | None = None
    effect_binding: GrowthEffectBinding | None = None
    production_written: Literal[False] = False

    @model_validator(mode="after")
    def _honest_state(self) -> "DailyOperatingCompilation":
        if self.state is DailyOperatingState.READY_FOR_PLAN_REVIEW:
            if self.blockers or self.plan_spec is None:
                raise ValueError("ready compilation requires a plan spec and no blockers")
        elif self.plan_spec is not None:
            raise ValueError("inconclusive or blocked compilation cannot contain a plan spec")
        return self


def _blockers(value: DailyOperatingInput) -> list[ContractBlocker]:
    blockers: list[ContractBlocker] = []
    cutoffs = {item.cutoff_at for item in value.source_observations}
    if len(cutoffs) != 1:
        blockers.append(
            ContractBlocker(
                code="DAILY_SOURCE_CUTOFF_MISMATCH",
                message="P01-P12 do not share one exact data cutoff",
            )
        )
    for source in value.source_observations:
        if source.status is not SourceRunStatus.SUCCEEDED:
            blockers.append(
                ContractBlocker(
                    code="DAILY_SOURCE_LATEST_RUN_NOT_SUCCEEDED",
                    message=f"{source.source_id} latest run is not succeeded",
                    resource_ref=source.latest_run_ref,
                )
            )
        if source.fresh_until <= value.observed_at:
            blockers.append(
                ContractBlocker(
                    code="DAILY_SOURCE_STALE",
                    message=f"{source.source_id} is stale at the requested observation time",
                    resource_ref=source.latest_run_ref,
                )
            )
        if not source.reconciliation_passed:
            blockers.append(
                ContractBlocker(
                    code="DAILY_SOURCE_RECONCILIATION_FAILED",
                    message=f"{source.source_id} reconciliation did not pass",
                    resource_ref=source.latest_run_ref,
                )
            )
        if source.source_count != source.projection_count:
            blockers.append(
                ContractBlocker(
                    code="DAILY_SOURCE_COUNT_MISMATCH",
                    message=f"{source.source_id} source/projection counts differ",
                    resource_ref=source.latest_run_ref,
                )
            )
    if not value.research_evidence_refs:
        blockers.append(
            ContractBlocker(
                code="DAILY_RESEARCH_EVIDENCE_MISSING",
                message="No approved external research evidence is available",
            )
        )
    return blockers


def compile_daily_operating_loop(
    tenant: TenantContext,
    value: DailyOperatingInput,
) -> DailyOperatingCompilation:
    """Compile a draft-only GrowthPlanSpec from exact, same-cutoff inputs."""

    blockers = _blockers(value)
    if blockers:
        return DailyOperatingCompilation(
            tenant=tenant,
            state=DailyOperatingState.INCONCLUSIVE,
            blockers=blockers,
        )
    evidence_refs = [
        value.source_evidence_pack_ref,
        value.wiki_snapshot_ref,
        value.okf_mapping_ref,
        *value.research_evidence_refs,
    ]
    return DailyOperatingCompilation(
        tenant=tenant,
        state=DailyOperatingState.READY_FOR_PLAN_REVIEW,
        blockers=[],
        plan_spec=GrowthPlanSpec(
            objective=value.objective,
            baseline=value.baseline,
            target=value.target,
            constraints=value.constraints,
            guardrails=value.guardrails,
            budget_limit=value.budget_limit,
            stop_conditions=value.stop_conditions,
            expected_effect=value.expected_effect,
            data_cutoff_at=value.source_observations[0].cutoff_at,
            evidence_refs=evidence_refs,
        ),
    )


def propose_task_graph_materialization(
    *,
    tenant: TenantContext,
    plan_ref: ExactRevisionRef,
    approval_ref: ExactRevisionRef,
    approved_plan_ref: ExactRevisionRef,
    current_plan_ref: ExactRevisionRef,
) -> TaskGraphMaterializationProposal:
    """Create a non-executable D04 proposal only for the current exact plan."""

    _exact_type(plan_ref, "GrowthPlanRevision", "planRef")
    _exact_type(approved_plan_ref, "GrowthPlanRevision", "approvedPlanRef")
    _exact_type(current_plan_ref, "GrowthPlanRevision", "currentPlanRef")
    _exact_type(approval_ref, "GrowthApprovalEventRevision", "approvalRef")
    if not (
        _same_exact_ref(plan_ref, approved_plan_ref)
        and _same_exact_ref(plan_ref, current_plan_ref)
    ):
        raise ValueError("D04 requires one current, approved exact plan revision")
    return TaskGraphMaterializationProposal(
        tenant=tenant,
        plan_ref=plan_ref,
        approval_ref=approval_ref,
    )


__all__ = [
    "DailyLogicStage",
    "DailyOperatingCompilation",
    "DailyOperatingInput",
    "DailyOperatingState",
    "DailySourceObservation",
    "EffectMaturity",
    "EffectOutcome",
    "GrowthEffectBinding",
    "GrowthPlanSpec",
    "LOGIC_IDS",
    "SOURCE_IDS",
    "SourceRunStatus",
    "TaskGraphMaterializationProposal",
    "compile_daily_operating_loop",
    "propose_task_graph_materialization",
]
