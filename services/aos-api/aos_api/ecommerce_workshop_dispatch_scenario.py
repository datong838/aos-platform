"""Compose W8-03 dispatch contribution without issuing a command or mutating owner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from aos_api.ecommerce_workshop_dispatch_scenario_contracts import (
    DispatchScenarioBlocker,
    DispatchScenarioCommands,
    DispatchScenarioComposition,
    DispatchScenarioContribution,
    DispatchScenarioDecisionLedger,
    DispatchScenarioExactRef,
    DispatchScenarioOutcomeAxis,
    DispatchScenarioOutcomeAxisId,
    DispatchScenarioStage,
    DispatchScenarioStageId,
)
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class DispatchScenarioObservation:
    scope: TenantScope
    cutoff: datetime
    root_task_graph_ref: DispatchScenarioExactRef
    root_task_run_ref: DispatchScenarioExactRef
    dispatch_binding_hash: str
    composition: DispatchScenarioComposition
    stages: tuple[DispatchScenarioStage, ...]
    ledger: DispatchScenarioDecisionLedger
    outcome_axes: tuple[DispatchScenarioOutcomeAxis, ...]


class DispatchScenarioCanonicalReader(Protocol):
    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> DispatchScenarioObservation | None: ...


def dispatch_binding_hash(
    graph: DispatchScenarioExactRef,
    run: DispatchScenarioExactRef,
    composition: DispatchScenarioComposition,
    stages: tuple[DispatchScenarioStage, ...],
) -> str:
    identities = [
        f"{graph.resource_type}:{graph.resource_id}:{graph.revision}:{graph.content_hash}",
        f"{run.resource_type}:{run.resource_id}:{run.revision}:{run.content_hash}",
        f"logic:{composition.logic_revision_ref.resource_id}:{composition.logic_revision_ref.revision}:{composition.logic_revision_ref.content_hash}",
    ]
    identities.extend(
        f"skill:{ref.resource_id}:{ref.revision}:{ref.content_hash}"
        for ref in composition.atomic_skill_refs
    )
    identities.extend(
        f"role:{item.role_ref.resource_id}:{item.assignee_ref.resource_id}:{item.skill_binding_ref.resource_id}:{item.skill_binding_ref.revision}:{item.skill_binding_ref.content_hash}"
        for item in composition.role_bindings
    )
    for stage in stages:
        identities.extend(
            f"{stage.stage_id}:{ref.resource_type}:{ref.resource_id}:{ref.revision}:{ref.content_hash}"
            for ref in stage.exact_refs
        )
    return sha256("|".join(identities).encode()).hexdigest()


class EcommerceWorkshopDispatchScenario:
    def __init__(self, *, reader: DispatchScenarioCanonicalReader | None = None) -> None:
        self._reader = reader

    def read(self, *, scope: TenantScope, cutoff: datetime) -> DispatchScenarioContribution:
        if cutoff.utcoffset() is None:
            raise ValueError("dispatch scenario cutoff requires timezone")
        observation = self._reader.read_scenario(scope, cutoff=cutoff) if self._reader is not None else None
        if observation is None:
            return self._blocked(cutoff, "TASK_GRAPH_EXACT_ROOT_REQUIRED", "aip.task-graph-authority")
        if observation.scope != scope or observation.cutoff != cutoff:
            return self._blocked(cutoff, "DISPATCH_SCENARIO_SCOPE_OR_CUTOFF_DRIFT", "workshop.dispatch-scenario-reader")
        expected_hash = dispatch_binding_hash(
            observation.root_task_graph_ref,
            observation.root_task_run_ref,
            observation.composition,
            observation.stages,
        )
        if observation.dispatch_binding_hash != expected_hash:
            return self._blocked(cutoff, "DISPATCH_SCENARIO_BINDING_DRIFT", "workshop.dispatch-scenario-binding")
        root_stage = observation.stages[0]
        if (
            root_stage.stage_id != DispatchScenarioStageId.TASK_GRAPH
            or root_stage.status != "ready"
            or observation.root_task_graph_ref not in root_stage.exact_refs
            or observation.root_task_run_ref not in root_stage.exact_refs
        ):
            return self._blocked(cutoff, "TASK_GRAPH_ROOT_STAGE_DRIFT", "aip.task-graph-authority")
        blockers = [stage.blockers[0] for stage in observation.stages if stage.status != "ready"]
        blockers.extend(
            axis.blocker
            for axis in observation.outcome_axes
            if axis.status != "ready" and axis.blocker is not None
        )
        if not blockers:
            return self._blocked(
                cutoff,
                "DISPATCH_SCENARIO_OPERATIONAL_AUTHORIZATION_REQUIRED",
                "workshop.dispatch-scenario-operational-gate",
            )
        return DispatchScenarioContribution(
            rootTaskGraphRef=observation.root_task_graph_ref,
            rootTaskRunRef=observation.root_task_run_ref,
            dispatchBindingHash=observation.dispatch_binding_hash,
            composition=observation.composition,
            evaluatedAt=cutoff,
            stages=list(observation.stages),
            ledger=observation.ledger,
            outcomeAxes=list(observation.outcome_axes),
            blockers=blockers,
            commands=DispatchScenarioCommands(),
        )

    @staticmethod
    def _blocked(cutoff: datetime, code: str, dependency: str) -> DispatchScenarioContribution:
        blocker = DispatchScenarioBlocker(
            code=code,
            dependency=dependency,
            requiredAction="provide tenant-bound exact TaskGraph/TaskRun, Skill/Logic/role bindings, decisions and owner timeline at one cutoff",
        )
        stages = [
            DispatchScenarioStage(
                stageId=stage,
                status="blocked",
                contribution="等待 exact authority；不制造派发、交接、决定或 owner 事实",
                blockers=[blocker],
            )
            for stage in DispatchScenarioStageId
        ]
        axes = [
            DispatchScenarioOutcomeAxis(axisId=axis, status="blocked", blocker=blocker)
            for axis in DispatchScenarioOutcomeAxisId
        ]
        return DispatchScenarioContribution(
            evaluatedAt=cutoff,
            stages=stages,
            ledger=DispatchScenarioDecisionLedger(
                tasksExpected=0,
                tasksObserved=0,
                handoffsExpected=0,
                handoffsObserved=0,
                decisionsExpected=0,
                decisionsRecorded=0,
                accepted=0,
                rejected=0,
                requestMore=0,
                returned=0,
                takeoverRequested=0,
                takeoverDecided=0,
                activeOwnerCount=0,
            ),
            outcomeAxes=axes,
            blockers=[blocker],
        )


__all__ = [
    "DispatchScenarioCanonicalReader",
    "DispatchScenarioObservation",
    "EcommerceWorkshopDispatchScenario",
    "dispatch_binding_hash",
]
