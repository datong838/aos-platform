"""Compose the W8-02 exact-binding remedy scenario without business writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from aos_api.ecommerce_workshop_remedy_scenario_contracts import RemedyScenarioBlocker, RemedyScenarioCommands, RemedyScenarioConservationLedger, RemedyScenarioContribution, RemedyScenarioExactRef, RemedyScenarioOutcomeAxis, RemedyScenarioOutcomeAxisId, RemedyScenarioStage, RemedyScenarioStageId
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class RemedyScenarioObservation:
    scope: TenantScope
    cutoff: datetime
    root_case_ref: RemedyScenarioExactRef
    remedy_binding_hash: str
    stages: tuple[RemedyScenarioStage, ...]
    ledger: RemedyScenarioConservationLedger
    outcome_axes: tuple[RemedyScenarioOutcomeAxis, ...]


class RemedyScenarioCanonicalReader(Protocol):
    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> RemedyScenarioObservation | None: ...


def remedy_binding_hash(root: RemedyScenarioExactRef, stages: tuple[RemedyScenarioStage, ...]) -> str:
    identities = [f"{root.resource_type}:{root.resource_id}:{root.revision}:{root.content_hash}"]
    for stage in stages:
        identities.extend(f"{stage.stage_id}:{ref.resource_type}:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in stage.exact_refs)
    return sha256("|".join(identities).encode()).hexdigest()


class EcommerceWorkshopRemedyScenario:
    def __init__(self, *, reader: RemedyScenarioCanonicalReader | None = None) -> None:
        self._reader = reader

    def read(self, *, scope: TenantScope, cutoff: datetime) -> RemedyScenarioContribution:
        if cutoff.utcoffset() is None:
            raise ValueError("remedy scenario cutoff requires timezone")
        observation = self._reader.read_scenario(scope, cutoff=cutoff) if self._reader is not None else None
        if observation is None:
            return self._blocked(cutoff, "PRICE_CASE_EXACT_ROOT_REQUIRED", "workshop.price-case-authority")
        if observation.scope != scope or observation.cutoff != cutoff:
            return self._blocked(cutoff, "REMEDY_SCENARIO_SCOPE_OR_CUTOFF_DRIFT", "workshop.remedy-scenario-reader")
        if observation.remedy_binding_hash != remedy_binding_hash(observation.root_case_ref, observation.stages):
            return self._blocked(cutoff, "REMEDY_SCENARIO_BINDING_DRIFT", "workshop.remedy-scenario-binding")
        price_case_stage = observation.stages[list(RemedyScenarioStageId).index(RemedyScenarioStageId.PRICE_CASE)]
        if price_case_stage.status != "ready" or observation.root_case_ref not in price_case_stage.exact_refs:
            return self._blocked(cutoff, "PRICE_CASE_ROOT_STAGE_DRIFT", "workshop.price-case-authority")
        blockers = [stage.blockers[0] for stage in observation.stages if stage.status != "ready"]
        blockers.extend(axis.blocker for axis in observation.outcome_axes if axis.status != "ready" and axis.blocker is not None)
        if not blockers:
            return self._blocked(cutoff, "REMEDY_SCENARIO_OPERATIONAL_AUTHORIZATION_REQUIRED", "workshop.remedy-operational-gate")
        return RemedyScenarioContribution(rootCaseRef=observation.root_case_ref, remedyBindingHash=observation.remedy_binding_hash, evaluatedAt=cutoff, stages=list(observation.stages), ledger=observation.ledger, outcomeAxes=list(observation.outcome_axes), blockers=blockers, commands=RemedyScenarioCommands())

    @staticmethod
    def _blocked(cutoff: datetime, code: str, dependency: str) -> RemedyScenarioContribution:
        blocker = RemedyScenarioBlocker(code=code, dependency=dependency, requiredAction="provide tenant-bound exact refs at one cutoff and binding hash")
        stages = [RemedyScenarioStage(stageId=stage, status="blocked", contribution="等待 exact authority；不展开订单、客户、联系方式或动作正文", blockers=[blocker]) for stage in RemedyScenarioStageId]
        axes = [RemedyScenarioOutcomeAxis(axisId=axis, status="blocked", blocker=blocker) for axis in RemedyScenarioOutcomeAxisId]
        return RemedyScenarioContribution(evaluatedAt=cutoff, stages=stages, ledger=RemedyScenarioConservationLedger(affectedOrdersExpected=0, affectedOrdersObserved=0, eligibleCustomersExpected=0, eligibleCustomersObserved=0, actionsExpected=5, actionsReady=0, actionsBlocked=5, actionsUnknown=0), outcomeAxes=axes, blockers=[blocker])


__all__ = ["EcommerceWorkshopRemedyScenario", "RemedyScenarioCanonicalReader", "RemedyScenarioObservation", "remedy_binding_hash"]
