"""Compose the W8-01 exact-binding scenario without creating business facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from aos_api.ecommerce_workshop_growth_scenario_contracts import (
    GrowthScenarioBlocker,
    GrowthScenarioCommands,
    GrowthScenarioConservationLedger,
    GrowthScenarioContribution,
    GrowthScenarioExactRef,
    GrowthScenarioOutcomeAxis,
    GrowthScenarioOutcomeAxisId,
    GrowthScenarioStage,
    GrowthScenarioStageId,
)
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class GrowthScenarioObservation:
    scope: TenantScope
    cutoff: datetime
    root_plan_ref: GrowthScenarioExactRef
    scenario_binding_hash: str
    stages: tuple[GrowthScenarioStage, ...]
    ledger: GrowthScenarioConservationLedger
    outcome_axes: tuple[GrowthScenarioOutcomeAxis, ...]


class GrowthScenarioCanonicalReader(Protocol):
    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> GrowthScenarioObservation | None: ...


def scenario_binding_hash(root: GrowthScenarioExactRef, stages: tuple[GrowthScenarioStage, ...]) -> str:
    identities = [f"{root.resource_type}:{root.resource_id}:{root.revision}:{root.content_hash}"]
    for stage in stages:
        identities.extend(f"{stage.stage_id}:{ref.resource_type}:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in stage.exact_refs)
    return sha256("|".join(identities).encode()).hexdigest()


class EcommerceWorkshopGrowthScenario:
    def __init__(self, *, reader: GrowthScenarioCanonicalReader | None = None) -> None:
        self._reader = reader

    def read(self, *, scope: TenantScope, cutoff: datetime) -> GrowthScenarioContribution:
        if cutoff.utcoffset() is None:
            raise ValueError("growth scenario cutoff requires timezone")
        observation = self._reader.read_scenario(scope, cutoff=cutoff) if self._reader is not None else None
        if observation is None:
            return self._blocked(cutoff, "GROWTH_PLAN_EXACT_ROOT_REQUIRED", "workshop.growth-plan-authority")
        if observation.scope != scope or observation.cutoff != cutoff:
            return self._blocked(cutoff, "GROWTH_SCENARIO_SCOPE_OR_CUTOFF_DRIFT", "workshop.growth-scenario-reader")
        if observation.scenario_binding_hash != scenario_binding_hash(observation.root_plan_ref, observation.stages):
            return self._blocked(cutoff, "GROWTH_SCENARIO_BINDING_DRIFT", "workshop.growth-scenario-binding")
        growth_plan_stage = observation.stages[list(GrowthScenarioStageId).index(GrowthScenarioStageId.GROWTH_PLAN)]
        if growth_plan_stage.status != "ready" or observation.root_plan_ref not in growth_plan_stage.exact_refs:
            return self._blocked(cutoff, "GROWTH_PLAN_ROOT_STAGE_DRIFT", "workshop.growth-plan-authority")
        blockers = [stage.blockers[0] for stage in observation.stages if stage.status != "ready"]
        blockers.extend(axis.blocker for axis in observation.outcome_axes if axis.status != "ready" and axis.blocker is not None)
        if not blockers:
            return self._blocked(cutoff, "GROWTH_SCENARIO_OPERATIONAL_AUTHORIZATION_REQUIRED", "workshop.growth-scenario-operational-gate")
        return GrowthScenarioContribution(
            rootPlanRef=observation.root_plan_ref,
            scenarioBindingHash=observation.scenario_binding_hash,
            evaluatedAt=cutoff,
            stages=list(observation.stages),
            ledger=observation.ledger,
            outcomeAxes=list(observation.outcome_axes),
            blockers=blockers,
            commands=GrowthScenarioCommands(),
        )

    @staticmethod
    def _blocked(cutoff: datetime, code: str, dependency: str) -> GrowthScenarioContribution:
        blocker = GrowthScenarioBlocker(code=code, dependency=dependency, requiredAction="provide tenant-bound exact refs at one cutoff and binding hash")
        stages = [GrowthScenarioStage(stageId=stage, status="blocked", contribution="等待 exact authority；不制造业务事实", blockers=[blocker]) for stage in GrowthScenarioStageId]
        axes = [GrowthScenarioOutcomeAxis(axisId=axis, status="blocked", blocker=blocker) for axis in GrowthScenarioOutcomeAxisId]
        return GrowthScenarioContribution(
            evaluatedAt=cutoff,
            stages=stages,
            ledger=GrowthScenarioConservationLedger(tasksExpected=0, tasksObserved=0, handoffsExpected=0, handoffsObserved=0, outcomesExpected=4, outcomesReady=0, outcomesBlocked=4, outcomesUnknown=0),
            outcomeAxes=axes,
            blockers=[blocker],
        )


__all__ = ["EcommerceWorkshopGrowthScenario", "GrowthScenarioCanonicalReader", "GrowthScenarioObservation", "scenario_binding_hash"]
