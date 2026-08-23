"""Fail-closed SC04-SC06 ecommerce scenario acceptance compiler.

This module only composes replayable review drafts from exact revisions.  It
never retries a Pipeline, publishes content, pauses a campaign, promotes a
memory candidate, calls a Provider, or writes production data.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_ecommerce_growth_core_agents import SourceReadinessGateSnapshot, SourceReadinessStatus
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef


SCENARIO_LOGICS: dict[str, tuple[str, ...]] = {
    "SC04": (*(f"A{i:02d}" for i in range(1, 7)), *(f"D{i:02d}" for i in range(3, 7)), *(f"C{i:02d}" for i in range(2, 7)), "P03", "S01"),
    "SC05": ("D02", "D03", *(f"C{i:02d}" for i in range(1, 7)), "G02", "G03", "G04", "A01", "A04", "S01"),
    "SC06": (*(f"D{i:02d}" for i in range(1, 7)),),
}

SCENARIO_CHAINS: dict[str, tuple[str, ...]] = {
    "SC04": ("CampaignPlanRevision", "BudgetEnvelopeRevision", "CostSnapshotRevision", "PriceSnapshotRevision", "InventorySnapshotRevision", "FulfillmentSnapshotRevision", "ExperimentRevision", "StopPolicyRevision", "MetricValidationRevision"),
    "SC05": ("ProductFactsRevision", "ContentAssetRevision", "CopyrightEvidenceRevision", "PlatformRuleReviewRevision", "PublishDraftRevision"),
    "SC06": ("PatrolTaskRevision", "CheckpointRevision", "CheckpointReceiptRevision", "EffectReviewRevision", "MemoryCandidateRevision"),
}


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _exact(value: ExactRevisionRef, kind: str, label: str) -> None:
    if value.resource_type != kind:
        raise ValueError(f"{label} must reference {kind}")


def _block(code: str, message: str, ref: ExactRevisionRef | None = None) -> ContractBlocker:
    return ContractBlocker(code=code, message=message, resource_ref=ref)


def _digest(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()


class PatrolOutcome(StrEnum):
    OPPORTUNITY = "opportunity"
    ANOMALY = "anomaly"
    NO_ACTION = "no_action"


class R29ScenarioState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"


class Scenario04Guard(AipContractModel):
    budget_limit: float = Field(ge=0)
    budget_requested: float = Field(ge=0)
    margin_floor: float = Field(ge=0, le=1)
    projected_margin: float = Field(ge=-1, le=1)
    price_ready: bool
    inventory_ready: bool
    fulfillment_ready: bool
    capacity_ready: bool
    experiment_frozen: bool
    assignment_clean: bool
    stop_triggered: bool
    pause_proposal_present: bool
    pause_executed: bool


class Scenario05Guard(AipContractModel):
    product_facts_fresh: bool
    asset_reviewed: bool
    copyright_evidence_present: bool
    platform_rules_passed: bool
    publish_authorized: bool
    platform_receipt_present: bool


class Scenario06Guard(AipContractModel):
    outcome: PatrolOutcome
    recommendation_count: int = Field(ge=0)
    pause_requested: bool
    resume_requested: bool
    pause_checkpoint_ref: ExactRevisionRef | None = None
    resume_checkpoint_ref: ExactRevisionRef | None = None
    memory_promoted: bool

    @model_validator(mode="after")
    def _checkpoint_types(self) -> "Scenario06Guard":
        if self.pause_checkpoint_ref is not None:
            _exact(self.pause_checkpoint_ref, "CheckpointRevision", "pauseCheckpointRef")
        if self.resume_checkpoint_ref is not None:
            _exact(self.resume_checkpoint_ref, "CheckpointRevision", "resumeCheckpointRef")
        return self


class R29ScenarioInput(AipContractModel):
    scenario_id: Literal["SC04", "SC05", "SC06"]
    scenario_ref: ExactRevisionRef
    source_readiness: SourceReadinessGateSnapshot
    logic_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=24)
    chain_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=16)
    task_run_ref: ExactRevisionRef
    lineage_ref: ExactRevisionRef
    effect_review_ref: ExactRevisionRef
    observed_cutoff: datetime
    fresh_until: datetime
    promotion_guard: Scenario04Guard | None = None
    product_guard: Scenario05Guard | None = None
    patrol_guard: Scenario06Guard | None = None

    @model_validator(mode="after")
    def _authority(self) -> "R29ScenarioInput":
        for value, kind, label in (
            (self.scenario_ref, "ScenarioRevision", "scenarioRef"),
            (self.task_run_ref, "TaskRunRevision", "taskRunRef"),
            (self.lineage_ref, "LineageRevision", "lineageRef"),
            (self.effect_review_ref, "EffectReviewRevision", "effectReviewRef"),
        ):
            _exact(value, kind, label)
        if self.scenario_ref.resource_id != f"ecommerce.{self.scenario_id}":
            raise ValueError("scenarioRef must match scenarioId")
        for item in self.logic_refs:
            _exact(item, "LogicGraphRevision", "logicRefs")
        _aware(self.observed_cutoff, "observedCutoff")
        _aware(self.fresh_until, "freshUntil")
        guards = {
            "SC04": self.promotion_guard,
            "SC05": self.product_guard,
            "SC06": self.patrol_guard,
        }
        if guards[self.scenario_id] is None or sum(value is not None for value in guards.values()) != 1:
            raise ValueError("exactly the guard matching scenarioId is required")
        return self


class R29EvidencePackDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    scenario_id: Literal["SC04", "SC05", "SC06"]
    state: R29ScenarioState
    scenario_ref: ExactRevisionRef
    source_readiness_ref: ExactRevisionRef
    logic_refs: list[ExactRevisionRef]
    chain_refs: list[ExactRevisionRef]
    task_run_ref: ExactRevisionRef
    lineage_ref: ExactRevisionRef
    effect_review_ref: ExactRevisionRef
    patrol_outcome: PatrolOutcome | None = None
    replay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    blockers: list[ContractBlocker]
    external_action_authorized: Literal[False] = False
    production_written: Literal[False] = False


class R29Compilation(AipContractModel):
    tenant: TenantContext
    requested_at: datetime
    state: R29ScenarioState
    evidence_packs: list[R29EvidencePackDraft] = Field(min_length=3, max_length=3)
    pipeline_retried: Literal[False] = False
    database_written: Literal[False] = False
    action_executed: Literal[False] = False
    provider_called: Literal[False] = False
    memory_promoted: Literal[False] = False
    production_written: Literal[False] = False


def _common_blockers(value: R29ScenarioInput, requested_at: datetime) -> list[ContractBlocker]:
    blockers: list[ContractBlocker] = []
    readiness = value.source_readiness
    if readiness.status is not SourceReadinessStatus.READY or readiness.ready_count != readiness.source_count or readiness.source_count != 12:
        blockers.append(_block("R29_SOURCE_READINESS_NOT_READY", "SourceReadiness must be current 12/12 READY", readiness.evidence_pack_ref))
    if readiness.fresh_until <= requested_at or value.fresh_until <= requested_at:
        blockers.append(_block("R29_SOURCE_READINESS_STALE", "scenario and SourceReadiness evidence must be fresh", readiness.evidence_pack_ref))
    if value.observed_cutoff != readiness.cutoff_at:
        blockers.append(_block("R29_CUTOFF_MISMATCH", "scenario and SourceReadiness must share the exact cutoff", readiness.evidence_pack_ref))
    expected_logic_ids = tuple(f"ecommerce.logic.{item}" for item in SCENARIO_LOGICS[value.scenario_id])
    if tuple(item.resource_id for item in value.logic_refs) != expected_logic_ids:
        blockers.append(_block("R29_LOGIC_SEQUENCE_INVALID", "scenario requires the exact ordered Logic set", value.scenario_ref))
    if tuple(item.resource_type for item in value.chain_refs) != SCENARIO_CHAINS[value.scenario_id]:
        blockers.append(_block("R29_CHAIN_INVALID", "scenario authority chain is incomplete or out of order", value.scenario_ref))
    return blockers


def _scenario_blockers(value: R29ScenarioInput, requested_at: datetime) -> list[ContractBlocker]:
    blockers = _common_blockers(value, requested_at)
    if value.scenario_id == "SC04":
        guard = value.promotion_guard
        assert guard is not None
        checks = (
            (guard.budget_requested > guard.budget_limit, "SC04_BUDGET_EXCEEDED", "requested budget exceeds the approved envelope"),
            (guard.projected_margin < guard.margin_floor, "SC04_MARGIN_BELOW_FLOOR", "projected margin is below the approved floor"),
            (not guard.price_ready, "SC04_PRICE_NOT_READY", "price snapshot is not ready"),
            (not guard.inventory_ready, "SC04_INVENTORY_NOT_READY", "inventory snapshot is not ready"),
            (not guard.fulfillment_ready, "SC04_FULFILLMENT_NOT_READY", "fulfillment snapshot is not ready"),
            (not guard.capacity_ready, "SC04_CAPACITY_NOT_READY", "capacity snapshot is not ready"),
            (not guard.experiment_frozen, "SC04_EXPERIMENT_NOT_FROZEN", "experiment revision is not frozen"),
            (not guard.assignment_clean, "SC04_ASSIGNMENT_CONTAMINATED", "experiment assignment is contaminated"),
            (guard.stop_triggered and not guard.pause_proposal_present, "SC04_PAUSE_PROPOSAL_MISSING", "stop trigger requires a reviewable pause Proposal"),
            (guard.pause_executed, "SC04_UNAUTHORIZED_PAUSE_EXECUTION", "compiler cannot claim campaign pause execution"),
        )
    elif value.scenario_id == "SC05":
        guard = value.product_guard
        assert guard is not None
        checks = (
            (not guard.product_facts_fresh, "SC05_PRODUCT_FACTS_STALE", "product facts are stale"),
            (not guard.asset_reviewed, "SC05_ASSET_NOT_REVIEWED", "content assets are not reviewed"),
            (not guard.copyright_evidence_present, "SC05_COPYRIGHT_EVIDENCE_MISSING", "copyright evidence is missing"),
            (not guard.platform_rules_passed, "SC05_PLATFORM_RULES_BLOCKED", "platform rule review did not pass"),
            (guard.publish_authorized, "SC05_PUBLISH_NOT_AUTHORIZED", "compiler cannot authorize publishing"),
            (guard.platform_receipt_present, "SC05_FAKE_PLATFORM_RECEIPT", "a draft compiler cannot claim a platform receipt"),
        )
    else:
        guard = value.patrol_guard
        assert guard is not None
        checks = (
            (guard.outcome is PatrolOutcome.NO_ACTION and guard.recommendation_count > 0, "SC06_FORCED_OPPORTUNITY", "no-action patrol cannot contain a forced recommendation"),
            (guard.pause_requested and guard.pause_checkpoint_ref is None, "SC06_PAUSE_CHECKPOINT_MISSING", "pause requires an exact checkpoint"),
            (guard.resume_requested and guard.resume_checkpoint_ref is None, "SC06_RESUME_CHECKPOINT_MISSING", "resume requires an exact checkpoint"),
            (guard.resume_requested and guard.pause_checkpoint_ref is None, "SC06_PAUSE_CHECKPOINT_MISSING", "resume requires the paired pause checkpoint"),
            (guard.memory_promoted, "SC06_MEMORY_AUTO_PROMOTION_FORBIDDEN", "patrol may only create a MemoryCandidate draft"),
        )
    for failed, code, message in checks:
        if failed:
            blockers.append(_block(code, message, value.scenario_ref))
    return blockers


def compile_sc04_sc06_acceptance(
    *,
    tenant: TenantContext,
    requested_at: datetime,
    scenarios: list[R29ScenarioInput],
) -> R29Compilation:
    """Compose three independent draft EvidencePacks without side effects."""

    _aware(requested_at, "requestedAt")
    if sorted(item.scenario_id for item in scenarios) != ["SC04", "SC05", "SC06"]:
        raise ValueError("exactly one SC04, SC05 and SC06 input is required")
    packs: list[R29EvidencePackDraft] = []
    for value in sorted(scenarios, key=lambda item: item.scenario_id):
        blockers = _scenario_blockers(value, requested_at)
        patrol_outcome = value.patrol_guard.outcome if value.patrol_guard is not None else None
        replay_digest = _digest(
            value.scenario_ref.content_hash,
            value.source_readiness.evidence_pack_ref.content_hash,
            value.task_run_ref.content_hash,
            value.lineage_ref.content_hash,
            value.effect_review_ref.content_hash,
            value.observed_cutoff.isoformat(),
            *(item.content_hash for item in value.logic_refs),
            *(item.content_hash for item in value.chain_refs),
        )
        packs.append(
            R29EvidencePackDraft(
                scenario_id=value.scenario_id,
                state=R29ScenarioState.BLOCKED if blockers else R29ScenarioState.READY_FOR_REVIEW,
                scenario_ref=value.scenario_ref,
                source_readiness_ref=value.source_readiness.evidence_pack_ref,
                logic_refs=value.logic_refs,
                chain_refs=value.chain_refs,
                task_run_ref=value.task_run_ref,
                lineage_ref=value.lineage_ref,
                effect_review_ref=value.effect_review_ref,
                patrol_outcome=patrol_outcome,
                replay_digest=replay_digest,
                blockers=blockers,
            )
        )
    state = R29ScenarioState.READY_FOR_REVIEW if all(item.state is R29ScenarioState.READY_FOR_REVIEW for item in packs) else R29ScenarioState.BLOCKED
    return R29Compilation(tenant=tenant, requested_at=requested_at, state=state, evidence_packs=packs)


__all__ = [
    "PatrolOutcome",
    "R29Compilation",
    "R29EvidencePackDraft",
    "R29ScenarioInput",
    "R29ScenarioState",
    "SCENARIO_CHAINS",
    "SCENARIO_LOGICS",
    "Scenario04Guard",
    "Scenario05Guard",
    "Scenario06Guard",
    "compile_sc04_sc06_acceptance",
]
