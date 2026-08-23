"""Fail-closed SC01-SC03 acceptance EvidencePack compiler.

The compiler assembles replayable draft evidence from exact references only.
It does not execute a Task, retry a Pipeline, call a Provider/Action or persist
business, memory or Wiki data.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_ecommerce_growth_core_agents import SourceReadinessGateSnapshot, SourceReadinessStatus
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef


SCENARIO_LOGICS: dict[str, tuple[str, ...]] = {
    "SC01": ("D02", "D03", *(f"C{i:02d}" for i in range(1, 9)), *(f"G{i:02d}" for i in range(1, 7)), "S01", "S06"),
    "SC02": ("D01", "D03", *(f"P{i:02d}" for i in range(2, 6)), "C02", "C03", "G02", "G04", "S02"),
    "SC03": (*(f"S{i:02d}" for i in range(1, 7)), "D01", "D06", "C06", "C08", "G03", "G05", "A05"),
}

SCENARIO_CHAINS: dict[str, tuple[str, ...]] = {
    "SC01": ("ContentArtifactRevision", "LeadSignalRevision", "ConsultationSessionRevision", "RecommendationRevision", "OrderFeedbackRevision", "AttributionRevision"),
    "SC02": ("CustomerLiteProjectionRevision", "ContactPolicyRevision", "ConsentEventRevision", "ContentDraftRevision", "RecommendationRevision", "OrderFeedbackRevision", "EffectReviewRevision"),
    "SC03": ("ServiceCaseAggregateRevision", "ProblemImpactRevision", "ContentCorrectionDraftRevision", "RecommendationCorrectionDraftRevision", "PromotionPauseProposalRevision", "MetricValidationRevision"),
}

_NON_REAL = re.compile(r"(?:^|[-_\s])(mock|fixture|sample|fake|placeholder)(?:$|[-_\s])", re.IGNORECASE)


def _exact(value: ExactRevisionRef, kind: str, label: str) -> None:
    if value.resource_type != kind:
        raise ValueError(f"{label} must reference {kind}")


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _block(code: str, message: str, ref: ExactRevisionRef | None = None) -> ContractBlocker:
    return ContractBlocker(code=code, message=message, resource_ref=ref)


def _digest(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()


class DecisionState(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    UNKNOWN = "unknown"


class ScenarioAcceptanceState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"


class ScenarioLogicStage(AipContractModel):
    order: int = Field(ge=1, le=24)
    logic_id: str = Field(pattern=r"^[DCPGSA]\d{2}$")
    logic_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _canonical(self) -> "ScenarioLogicStage":
        _exact(self.logic_ref, "LogicGraphRevision", "logicRef")
        if self.logic_ref.resource_id != f"ecommerce.logic.{self.logic_id}":
            raise ValueError("logicRef must bind canonical ecommerce Logic ID")
        return self


class ScenarioGuardSnapshot(AipContractModel):
    consent: DecisionState
    channel: DecisionState
    frequency_cap: DecisionState
    opt_out: DecisionState
    complaint_guard: DecisionState
    aggregation_count: int = Field(ge=0)
    single_case_substitution: bool = False


class ScenarioAcceptanceInput(AipContractModel):
    scenario_id: Literal["SC01", "SC02", "SC03"]
    scenario_ref: ExactRevisionRef
    source_readiness: SourceReadinessGateSnapshot
    task_ref: ExactRevisionRef
    task_run_ref: ExactRevisionRef
    logic_stages: list[ScenarioLogicStage] = Field(min_length=1, max_length=24)
    handoff_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=32)
    receipt_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=64)
    lineage_ref: ExactRevisionRef
    effect_review_ref: ExactRevisionRef
    chain_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=24)
    guard: ScenarioGuardSnapshot
    window_start: datetime
    window_end: datetime
    observed_cutoff: datetime
    fresh_until: datetime
    source_labels: list[str] = Field(min_length=1, max_length=16)
    external_action_state: Literal["draft", "blocked"]

    @field_validator("source_labels")
    @classmethod
    def _real_sources(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or _NON_REAL.search(value) for value in cleaned):
            raise ValueError("source labels cannot contain mock, fixture, sample, fake or placeholder")
        return cleaned

    @model_validator(mode="after")
    def _authority(self) -> "ScenarioAcceptanceInput":
        for value, kind, label in (
            (self.scenario_ref, "ScenarioRevision", "scenarioRef"),
            (self.task_ref, "TaskRevision", "taskRef"),
            (self.task_run_ref, "TaskRunRevision", "taskRunRef"),
            (self.lineage_ref, "LineageRevision", "lineageRef"),
            (self.effect_review_ref, "EffectReviewRevision", "effectReviewRef"),
        ):
            _exact(value, kind, label)
        if self.scenario_ref.resource_id != f"ecommerce.{self.scenario_id}":
            raise ValueError("scenarioRef must match scenarioId")
        for item in self.handoff_refs:
            _exact(item, "HandoffRevision", "handoffRefs")
        for item in self.receipt_refs:
            _exact(item, "ReceiptRevision", "receiptRefs")
        for field, label in (
            (self.window_start, "windowStart"),
            (self.window_end, "windowEnd"),
            (self.observed_cutoff, "observedCutoff"),
            (self.fresh_until, "freshUntil"),
        ):
            _aware(field, label)
        if self.window_end <= self.window_start:
            raise ValueError("windowEnd must follow windowStart")
        if self.fresh_until <= self.window_end:
            raise ValueError("freshUntil must follow windowEnd")
        return self


class ScenarioEvidencePackDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    scenario_id: Literal["SC01", "SC02", "SC03"]
    state: ScenarioAcceptanceState
    source_readiness_ref: ExactRevisionRef
    scenario_ref: ExactRevisionRef
    task_ref: ExactRevisionRef
    task_run_ref: ExactRevisionRef
    logic_refs: list[ExactRevisionRef]
    handoff_refs: list[ExactRevisionRef]
    receipt_refs: list[ExactRevisionRef]
    lineage_ref: ExactRevisionRef
    effect_review_ref: ExactRevisionRef
    chain_refs: list[ExactRevisionRef]
    window_start: datetime
    window_end: datetime
    replay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    blockers: list[ContractBlocker]
    external_action_authorized: Literal[False] = False
    production_written: Literal[False] = False


class SC01SC03Compilation(AipContractModel):
    tenant: TenantContext
    requested_at: datetime
    state: ScenarioAcceptanceState
    evidence_packs: list[ScenarioEvidencePackDraft] = Field(min_length=3, max_length=3)
    database_written: Literal[False] = False
    provider_called: Literal[False] = False
    action_executed: Literal[False] = False
    memory_written: Literal[False] = False
    pipeline_retried: Literal[False] = False
    production_written: Literal[False] = False


def _scenario_blockers(value: ScenarioAcceptanceInput, requested_at: datetime) -> list[ContractBlocker]:
    blockers: list[ContractBlocker] = []
    if value.source_readiness.status is not SourceReadinessStatus.READY:
        blockers.append(_block("SC_SOURCE_READINESS_NOT_READY", "SourceReadiness is not current 12/12 READY", value.source_readiness.evidence_pack_ref))
    if value.source_readiness.fresh_until <= requested_at or value.fresh_until <= requested_at:
        blockers.append(_block("SC_SOURCE_READINESS_STALE", "scenario or SourceReadiness evidence is stale", value.source_readiness.evidence_pack_ref))
    if value.observed_cutoff != value.source_readiness.cutoff_at:
        blockers.append(_block("SC_CUTOFF_MISMATCH", "scenario observation and SourceReadiness must share a cutoff", value.source_readiness.evidence_pack_ref))
    actual_logics = tuple(item.logic_id for item in sorted(value.logic_stages, key=lambda item: item.order))
    actual_orders = tuple(item.order for item in value.logic_stages)
    expected_logics = SCENARIO_LOGICS[value.scenario_id]
    if actual_logics != expected_logics or actual_orders != tuple(range(1, len(expected_logics) + 1)):
        blockers.append(_block("SC_LOGIC_SEQUENCE_INVALID", "scenario requires the exact ordered Logic set", value.scenario_ref))
    actual_chain = tuple(item.resource_type for item in value.chain_refs)
    if actual_chain != SCENARIO_CHAINS[value.scenario_id]:
        blockers.append(_block("SC_CHAIN_INCOMPLETE", "scenario business chain is missing or out of order", value.scenario_ref))
    if value.scenario_id == "SC02":
        checks = (
            (value.guard.consent, DecisionState.ALLOW, "SC02_CONSENT_BLOCKED"),
            (value.guard.channel, DecisionState.ALLOW, "SC02_CHANNEL_BLOCKED"),
            (value.guard.frequency_cap, DecisionState.ALLOW, "SC02_FREQUENCY_BLOCKED"),
            (value.guard.opt_out, DecisionState.BLOCK, "SC02_OPT_OUT_BLOCKED"),
            (value.guard.complaint_guard, DecisionState.ALLOW, "SC02_COMPLAINT_GUARD_BLOCKED"),
        )
        for actual, expected, code in checks:
            if actual is not expected:
                blockers.append(_block(code, "SC02 contact or complaint guard failed closed", value.scenario_ref))
    if value.scenario_id == "SC03":
        if value.guard.aggregation_count < 2:
            blockers.append(_block("SC03_AGGREGATION_INSUFFICIENT", "SC03 requires an aggregate, not a single case", value.scenario_ref))
        if value.guard.single_case_substitution:
            blockers.append(_block("SC03_SINGLE_CASE_SUBSTITUTION", "SC09 single-case evidence cannot replace SC03", value.scenario_ref))
    return blockers


def compile_sc01_sc03_acceptance(
    *,
    tenant: TenantContext,
    requested_at: datetime,
    scenarios: list[ScenarioAcceptanceInput],
) -> SC01SC03Compilation:
    """Build three independent replay drafts without runtime side effects."""

    _aware(requested_at, "requestedAt")
    ids = [item.scenario_id for item in scenarios]
    if sorted(ids) != ["SC01", "SC02", "SC03"]:
        raise ValueError("exactly one SC01, SC02 and SC03 input is required")
    packs: list[ScenarioEvidencePackDraft] = []
    for value in sorted(scenarios, key=lambda item: item.scenario_id):
        blockers = _scenario_blockers(value, requested_at)
        replay_digest = _digest(
            value.scenario_ref.content_hash,
            value.task_ref.content_hash,
            value.task_run_ref.content_hash,
            value.lineage_ref.content_hash,
            value.effect_review_ref.content_hash,
            value.source_readiness.evidence_pack_ref.content_hash,
            value.window_start.isoformat(),
            value.window_end.isoformat(),
            *(item.logic_ref.content_hash for item in value.logic_stages),
            *(item.content_hash for item in value.chain_refs),
        )
        packs.append(
            ScenarioEvidencePackDraft(
                scenario_id=value.scenario_id,
                state=ScenarioAcceptanceState.BLOCKED if blockers else ScenarioAcceptanceState.READY_FOR_REVIEW,
                source_readiness_ref=value.source_readiness.evidence_pack_ref,
                scenario_ref=value.scenario_ref,
                task_ref=value.task_ref,
                task_run_ref=value.task_run_ref,
                logic_refs=[item.logic_ref for item in value.logic_stages],
                handoff_refs=value.handoff_refs,
                receipt_refs=value.receipt_refs,
                lineage_ref=value.lineage_ref,
                effect_review_ref=value.effect_review_ref,
                chain_refs=value.chain_refs,
                window_start=value.window_start,
                window_end=value.window_end,
                replay_digest=replay_digest,
                blockers=blockers,
            )
        )
    state = (
        ScenarioAcceptanceState.READY_FOR_REVIEW
        if all(item.state is ScenarioAcceptanceState.READY_FOR_REVIEW for item in packs)
        else ScenarioAcceptanceState.BLOCKED
    )
    return SC01SC03Compilation(
        tenant=tenant,
        requested_at=requested_at,
        state=state,
        evidence_packs=packs,
    )


__all__ = [
    "DecisionState",
    "SCENARIO_CHAINS",
    "SCENARIO_LOGICS",
    "SC01SC03Compilation",
    "ScenarioAcceptanceInput",
    "ScenarioAcceptanceState",
    "ScenarioEvidencePackDraft",
    "ScenarioGuardSnapshot",
    "ScenarioLogicStage",
    "compile_sc01_sc03_acceptance",
]
