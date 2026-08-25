"""Compose W8-06 batch contribution without preparing, starting or reconciling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from aos_api.ecommerce_workshop_batch_scenario_contracts import (
    BatchScenarioBlocker,
    BatchScenarioChildOutcome,
    BatchScenarioCommands,
    BatchScenarioComposition,
    BatchScenarioContribution,
    BatchScenarioExactRef,
    BatchScenarioLedger,
    BatchScenarioOutcomeAxis,
    BatchScenarioOutcomeAxisId,
    BatchScenarioPreparationDecision,
    BatchScenarioStage,
    BatchScenarioStageId,
)
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class BatchScenarioObservation:
    scope: TenantScope
    cutoff: datetime
    batch_preparation_revision_ref: BatchScenarioExactRef
    batch_start_decision_ref: BatchScenarioExactRef
    batch_start_binding_hash: str
    composition: BatchScenarioComposition
    preparation_decisions: tuple[BatchScenarioPreparationDecision, ...]
    child_outcomes: tuple[BatchScenarioChildOutcome, ...]
    stages: tuple[BatchScenarioStage, ...]
    ledger: BatchScenarioLedger
    outcome_axes: tuple[BatchScenarioOutcomeAxis, ...]


class BatchScenarioCanonicalReader(Protocol):
    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> BatchScenarioObservation | None: ...


def batch_start_binding_hash(observation: BatchScenarioObservation) -> str:
    refs = (observation.batch_preparation_revision_ref, observation.batch_start_decision_ref)
    identities = [f"{ref.resource_type}:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in refs]
    identities.append(f"logic:{observation.composition.logic_revision_ref.resource_id}:{observation.composition.logic_revision_ref.revision}:{observation.composition.logic_revision_ref.content_hash}")
    identities.extend(f"skill:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in observation.composition.atomic_skill_refs)
    identities.extend(f"role:{item.role_ref.resource_id}:{item.assignee_ref.resource_id}:{item.skill_binding_ref.resource_id}:{item.skill_binding_ref.revision}:{item.skill_binding_ref.content_hash}" for item in observation.composition.role_bindings)
    for decision in observation.preparation_decisions:
        identities.append(f"decision:{decision.item_key}:{decision.disposition}:{decision.decision_ref.resource_id}:{decision.decision_ref.revision}:{decision.decision_ref.content_hash}")
    for outcome in observation.child_outcomes:
        identities.append(f"outcome:{outcome.item_key}:{outcome.status}:{outcome.request_fingerprint}:{outcome.attempt_ref.resource_id}:{outcome.attempt_ref.revision}:{outcome.attempt_ref.content_hash}")
        identities.extend(f"reconcile:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in outcome.reconcile_receipt_refs)
    for stage in observation.stages:
        identities.extend(f"stage:{stage.stage_id}:{ref.resource_type}:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in stage.exact_refs)
    return sha256("|".join(identities).encode()).hexdigest()


class EcommerceWorkshopBatchScenario:
    def __init__(self, *, reader: BatchScenarioCanonicalReader | None = None) -> None:
        self._reader = reader

    def read(self, *, scope: TenantScope, cutoff: datetime) -> BatchScenarioContribution:
        if cutoff.utcoffset() is None:
            raise ValueError("batch scenario cutoff requires timezone")
        observation = self._reader.read_scenario(scope, cutoff=cutoff) if self._reader is not None else None
        if observation is None:
            return self._blocked(cutoff, "BATCH_EXACT_ROOTS_REQUIRED", "aip.batch-authority")
        if observation.scope != scope or observation.cutoff != cutoff:
            return self._blocked(cutoff, "BATCH_SCENARIO_SCOPE_OR_CUTOFF_DRIFT", "workshop.batch-scenario-reader")
        if observation.batch_start_binding_hash != batch_start_binding_hash(observation):
            return self._blocked(cutoff, "BATCH_START_BINDING_DRIFT", "workshop.batch-scenario-binding")
        root_stage = observation.stages[0]
        if root_stage.stage_id != BatchScenarioStageId.PREPARE_ROOT or root_stage.status != "ready" or observation.batch_preparation_revision_ref not in root_stage.exact_refs or observation.batch_start_decision_ref not in root_stage.exact_refs:
            return self._blocked(cutoff, "BATCH_ROOT_STAGE_DRIFT", "aip.batch-authority")
        blockers = [stage.blockers[0] for stage in observation.stages if stage.status != "ready"]
        blockers.extend(blocker for axis in observation.outcome_axes for blocker in axis.blockers)
        if not blockers:
            return self._blocked(cutoff, "BATCH_OPERATIONAL_AUTHORIZATION_REQUIRED", "workshop.batch-operational-gate")
        return BatchScenarioContribution(
            batchPreparationRevisionRef=observation.batch_preparation_revision_ref,
            batchStartDecisionRef=observation.batch_start_decision_ref,
            batchStartBindingHash=observation.batch_start_binding_hash,
            composition=observation.composition,
            evaluatedAt=cutoff,
            preparationDecisions=list(observation.preparation_decisions),
            childOutcomes=list(observation.child_outcomes),
            stages=list(observation.stages),
            ledger=observation.ledger,
            outcomeAxes=list(observation.outcome_axes),
            blockers=blockers,
            commands=BatchScenarioCommands(),
        )

    @staticmethod
    def _blocked(cutoff: datetime, code: str, dependency: str) -> BatchScenarioContribution:
        blocker = BatchScenarioBlocker(code=code, dependency=dependency, requiredAction="provide same-cutoff tenant-bound BatchPreparationRevision, BatchStartDecision, Skill/Logic/role bindings, item decisions and reconcile receipts")
        return BatchScenarioContribution(
            evaluatedAt=cutoff,
            stages=[BatchScenarioStage(stageId=stage, status="blocked", contribution="等待 exact authority；不准备、不启动、不自动重试、不制造 Reconcile 事实", blockers=[blocker]) for stage in BatchScenarioStageId],
            ledger=BatchScenarioLedger(frozenTotal=0, included=0, excluded=0, blocked=0, preparationUnknown=0, childrenExpected=0, childrenObserved=0, succeeded=0, failed=0, cancelled=0, childUnknown=0, reconciled=0, reconcileReceiptsObserved=0),
            outcomeAxes=[BatchScenarioOutcomeAxis(axisId=axis, status="blocked", blockers=[blocker]) for axis in BatchScenarioOutcomeAxisId],
            blockers=[blocker],
        )


__all__ = ["BatchScenarioCanonicalReader", "BatchScenarioObservation", "EcommerceWorkshopBatchScenario", "batch_start_binding_hash"]
