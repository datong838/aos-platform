"""Strict GET-only W8-04 EffectReview to governed knowledge contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


LEARNING_SCENARIO_SCHEMA_VERSION = "aos.ecommerce-workshop.learning-scenario/v1"


class LearningScenarioStageId(StrEnum):
    EFFECT_REVIEW = "effect_review"
    MATURITY = "maturity"
    MEMORY_CANDIDATE = "memory_candidate"
    GOVERNANCE = "governance"
    PROMOTION = "promotion"
    KNOWLEDGE_QUERY = "knowledge_query"
    REVOCATION_IMPACT = "revocation_impact"


class LearningScenarioOutcomeAxisId(StrEnum):
    EFFECT_MATURE = "effect_mature"
    CANDIDATE_GOVERNED = "candidate_governed"
    KNOWLEDGE_PROMOTED = "knowledge_promoted"
    FUTURE_QUERY_AUTHORIZED = "future_query_authorized"
    REVOCATION_IMPACT_RECORDED = "revocation_impact_recorded"


class LearningScenarioExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class LearningScenarioBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class LearningScenarioRoleBinding(AipContractModel):
    role_ref: LearningScenarioExactRef
    assignee_ref: LearningScenarioExactRef
    skill_binding_ref: LearningScenarioExactRef

    @model_validator(mode="after")
    def _exact_role_layers(self) -> "LearningScenarioRoleBinding":
        if self.role_ref.resource_type != "AgentTemplate":
            raise ValueError("learning scenario role must be AgentTemplate")
        if self.assignee_ref.resource_type != "AgentInstance":
            raise ValueError("learning scenario assignee must be AgentInstance")
        if self.skill_binding_ref.resource_type != "SkillBinding":
            raise ValueError("learning scenario binding must be SkillBinding")
        return self


class LearningScenarioComposition(AipContractModel):
    atomic_skill_refs: list[LearningScenarioExactRef] = Field(min_length=1, max_length=30)
    logic_revision_ref: LearningScenarioExactRef
    role_bindings: list[LearningScenarioRoleBinding] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def _distinct_layers(self) -> "LearningScenarioComposition":
        if any(ref.resource_type != "SkillRevision" for ref in self.atomic_skill_refs):
            raise ValueError("learning scenario atomic skills must be SkillRevision")
        if self.logic_revision_ref.resource_type != "LogicRevision":
            raise ValueError("learning scenario logic must be LogicRevision")
        skills = [(ref.resource_id, ref.revision, ref.content_hash) for ref in self.atomic_skill_refs]
        bindings = [item.skill_binding_ref.resource_id for item in self.role_bindings]
        if len(skills) != len(set(skills)) or len(bindings) != len(set(bindings)):
            raise ValueError("learning scenario composition identities must be unique")
        return self


class LearningScenarioStage(AipContractModel):
    stage_id: LearningScenarioStageId
    status: Literal["ready", "blocked", "unknown"]
    exact_refs: list[LearningScenarioExactRef] = Field(default_factory=list, max_length=40)
    contribution: str = Field(min_length=1, max_length=500)
    blockers: list[LearningScenarioBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_stage(self) -> "LearningScenarioStage":
        identities = [(ref.resource_type, ref.resource_id, ref.revision, ref.content_hash) for ref in self.exact_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("learning stage refs must be unique")
        if self.status == "ready" and (not self.exact_refs or self.blockers):
            raise ValueError("ready learning stage requires exact refs and no blockers")
        if self.status != "ready" and (self.exact_refs or not self.blockers):
            raise ValueError("non-ready learning stage requires blockers and no trusted refs")
        return self


class LearningScenarioLedger(AipContractModel):
    reviews_expected: int = Field(ge=0)
    reviews_observed: int = Field(ge=0)
    candidates_expected: int = Field(ge=0)
    candidates_observed: int = Field(ge=0)
    promotions_expected: int = Field(ge=0)
    promotions_observed: int = Field(ge=0)
    citations_expected: int = Field(ge=0)
    citations_observed: int = Field(ge=0)
    historical_exposures: int = Field(ge=0)
    retained_exposures: int = Field(ge=0)
    impact_refs_expected: int = Field(ge=0)
    impact_refs_observed: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves(self) -> "LearningScenarioLedger":
        pairs = (
            (self.reviews_observed, self.reviews_expected),
            (self.candidates_observed, self.candidates_expected),
            (self.promotions_observed, self.promotions_expected),
            (self.citations_observed, self.citations_expected),
            (self.impact_refs_observed, self.impact_refs_expected),
        )
        if any(observed > expected for observed, expected in pairs):
            raise ValueError("learning observed counts cannot exceed expected counts")
        if self.retained_exposures != self.historical_exposures:
            raise ValueError("revocation must retain every historical exposure")
        return self


class LearningScenarioOutcomeAxis(AipContractModel):
    axis_id: LearningScenarioOutcomeAxisId
    status: Literal["ready", "blocked", "unknown"]
    exact_ref: LearningScenarioExactRef | None = None
    blocker: LearningScenarioBlocker | None = None

    @model_validator(mode="after")
    def _honest_axis(self) -> "LearningScenarioOutcomeAxis":
        if self.status == "ready" and (self.exact_ref is None or self.blocker is not None):
            raise ValueError("ready learning axis requires exact ref")
        if self.status != "ready" and (self.exact_ref is not None or self.blocker is None):
            raise ValueError("non-ready learning axis requires one blocker")
        return self


class LearningScenarioCommands(AipContractModel):
    submit_candidate: Literal[False] = False
    approve_candidate: Literal[False] = False
    promote_candidate: Literal[False] = False
    publish_wiki: Literal[False] = False
    revoke_knowledge: Literal[False] = False


class LearningScenarioContribution(AipContractModel):
    schema_version: Literal[LEARNING_SCENARIO_SCHEMA_VERSION] = LEARNING_SCENARIO_SCHEMA_VERSION
    status: Literal["blocked"] = "blocked"
    root_effect_review_ref: LearningScenarioExactRef | None = None
    maturity_policy_ref: LearningScenarioExactRef | None = None
    learning_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    composition: LearningScenarioComposition | None = None
    evaluated_at: datetime
    stages: list[LearningScenarioStage] = Field(min_length=7, max_length=7)
    ledger: LearningScenarioLedger
    outcome_axes: list[LearningScenarioOutcomeAxis] = Field(min_length=5, max_length=5)
    blockers: list[LearningScenarioBlocker] = Field(min_length=1, max_length=50)
    commands: LearningScenarioCommands = Field(default_factory=LearningScenarioCommands)
    external_effects_allowed: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("learning scenario evaluation requires timezone")
        return value

    @model_validator(mode="after")
    def _canonical_and_fail_closed(self) -> "LearningScenarioContribution":
        if [stage.stage_id for stage in self.stages] != list(LearningScenarioStageId):
            raise ValueError("learning scenario stages require canonical order")
        if [axis.axis_id for axis in self.outcome_axes] != list(LearningScenarioOutcomeAxisId):
            raise ValueError("learning scenario axes require canonical order")
        roots = (self.root_effect_review_ref, self.maturity_policy_ref, self.learning_binding_hash, self.composition)
        if any(item is None for item in roots) != all(item is None for item in roots):
            raise ValueError("learning roots, binding and composition must appear together")
        if self.root_effect_review_ref is not None and self.root_effect_review_ref.resource_type != "EffectReviewRevision":
            raise ValueError("learning root must be EffectReviewRevision")
        if self.maturity_policy_ref is not None and self.maturity_policy_ref.resource_type != "EffectMaturityPolicyRevision":
            raise ValueError("learning maturity policy must be exact")
        if self.root_effect_review_ref is not None and self.stages[0].status == "ready":
            if self.root_effect_review_ref not in self.stages[0].exact_refs:
                raise ValueError("learning root must be included in effect_review stage")
        if not any(stage.status != "ready" for stage in self.stages) and not any(axis.status != "ready" for axis in self.outcome_axes):
            raise ValueError("W8-04 cannot claim operational ready under the no-command contract")
        return self


__all__ = [name for name in globals() if name.startswith("LEARNING_SCENARIO") or name.startswith("LearningScenario")]
