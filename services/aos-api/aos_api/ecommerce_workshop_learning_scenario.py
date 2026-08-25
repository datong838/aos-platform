"""Compose W8-04 learning-governance contribution without changing knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from aos_api.ecommerce_workshop_learning_scenario_contracts import (
    LearningScenarioBlocker,
    LearningScenarioCommands,
    LearningScenarioComposition,
    LearningScenarioContribution,
    LearningScenarioExactRef,
    LearningScenarioLedger,
    LearningScenarioOutcomeAxis,
    LearningScenarioOutcomeAxisId,
    LearningScenarioStage,
    LearningScenarioStageId,
)
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class LearningScenarioObservation:
    scope: TenantScope
    cutoff: datetime
    root_effect_review_ref: LearningScenarioExactRef
    maturity_policy_ref: LearningScenarioExactRef
    learning_binding_hash: str
    composition: LearningScenarioComposition
    stages: tuple[LearningScenarioStage, ...]
    ledger: LearningScenarioLedger
    outcome_axes: tuple[LearningScenarioOutcomeAxis, ...]


class LearningScenarioCanonicalReader(Protocol):
    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> LearningScenarioObservation | None: ...


def learning_binding_hash(
    review: LearningScenarioExactRef,
    maturity_policy: LearningScenarioExactRef,
    composition: LearningScenarioComposition,
    stages: tuple[LearningScenarioStage, ...],
) -> str:
    identities = [
        f"{review.resource_type}:{review.resource_id}:{review.revision}:{review.content_hash}",
        f"{maturity_policy.resource_type}:{maturity_policy.resource_id}:{maturity_policy.revision}:{maturity_policy.content_hash}",
        f"logic:{composition.logic_revision_ref.resource_id}:{composition.logic_revision_ref.revision}:{composition.logic_revision_ref.content_hash}",
    ]
    identities.extend(f"skill:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in composition.atomic_skill_refs)
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


class EcommerceWorkshopLearningScenario:
    def __init__(self, *, reader: LearningScenarioCanonicalReader | None = None) -> None:
        self._reader = reader

    def read(self, *, scope: TenantScope, cutoff: datetime) -> LearningScenarioContribution:
        if cutoff.utcoffset() is None:
            raise ValueError("learning scenario cutoff requires timezone")
        observation = self._reader.read_scenario(scope, cutoff=cutoff) if self._reader is not None else None
        if observation is None:
            return self._blocked(cutoff, "EFFECT_REVIEW_EXACT_ROOT_REQUIRED", "aip.effect-review-authority")
        if observation.scope != scope or observation.cutoff != cutoff:
            return self._blocked(cutoff, "LEARNING_SCENARIO_SCOPE_OR_CUTOFF_DRIFT", "workshop.learning-scenario-reader")
        expected_hash = learning_binding_hash(
            observation.root_effect_review_ref,
            observation.maturity_policy_ref,
            observation.composition,
            observation.stages,
        )
        if observation.learning_binding_hash != expected_hash:
            return self._blocked(cutoff, "LEARNING_SCENARIO_BINDING_DRIFT", "workshop.learning-scenario-binding")
        root_stage = observation.stages[0]
        if (
            root_stage.stage_id != LearningScenarioStageId.EFFECT_REVIEW
            or root_stage.status != "ready"
            or observation.root_effect_review_ref not in root_stage.exact_refs
        ):
            return self._blocked(cutoff, "EFFECT_REVIEW_ROOT_STAGE_DRIFT", "aip.effect-review-authority")
        maturity_stage = observation.stages[1]
        if maturity_stage.status == "ready" and observation.maturity_policy_ref not in maturity_stage.exact_refs:
            return self._blocked(cutoff, "EFFECT_MATURITY_POLICY_STAGE_DRIFT", "aip.effect-maturity-authority")
        blockers = [stage.blockers[0] for stage in observation.stages if stage.status != "ready"]
        blockers.extend(axis.blocker for axis in observation.outcome_axes if axis.status != "ready" and axis.blocker is not None)
        if not blockers:
            return self._blocked(cutoff, "LEARNING_SCENARIO_OPERATIONAL_AUTHORIZATION_REQUIRED", "workshop.learning-scenario-operational-gate")
        return LearningScenarioContribution(
            rootEffectReviewRef=observation.root_effect_review_ref,
            maturityPolicyRef=observation.maturity_policy_ref,
            learningBindingHash=observation.learning_binding_hash,
            composition=observation.composition,
            evaluatedAt=cutoff,
            stages=list(observation.stages),
            ledger=observation.ledger,
            outcomeAxes=list(observation.outcome_axes),
            blockers=blockers,
            commands=LearningScenarioCommands(),
        )

    @staticmethod
    def _blocked(cutoff: datetime, code: str, dependency: str) -> LearningScenarioContribution:
        blocker = LearningScenarioBlocker(
            code=code,
            dependency=dependency,
            requiredAction="provide tenant-bound exact EffectReview, maturity, governance, knowledge, citation and revocation impact refs at one cutoff",
        )
        stages = [
            LearningScenarioStage(
                stageId=stage,
                status="blocked",
                contribution="等待 exact authority；不制造 Candidate、知识、Citation、Exposure 或撤销事实",
                blockers=[blocker],
            )
            for stage in LearningScenarioStageId
        ]
        axes = [LearningScenarioOutcomeAxis(axisId=axis, status="blocked", blocker=blocker) for axis in LearningScenarioOutcomeAxisId]
        return LearningScenarioContribution(
            evaluatedAt=cutoff,
            stages=stages,
            ledger=LearningScenarioLedger(
                reviewsExpected=0,
                reviewsObserved=0,
                candidatesExpected=0,
                candidatesObserved=0,
                promotionsExpected=0,
                promotionsObserved=0,
                citationsExpected=0,
                citationsObserved=0,
                historicalExposures=0,
                retainedExposures=0,
                impactRefsExpected=0,
                impactRefsObserved=0,
            ),
            outcomeAxes=axes,
            blockers=[blocker],
        )


__all__ = [
    "EcommerceWorkshopLearningScenario",
    "LearningScenarioCanonicalReader",
    "LearningScenarioObservation",
    "learning_binding_hash",
]
