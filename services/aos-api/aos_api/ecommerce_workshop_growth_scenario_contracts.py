"""Strict GET-only W8-01 GrowthPlan-rooted scenario contribution contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


GROWTH_SCENARIO_SCHEMA_VERSION = "aos.ecommerce-workshop.growth-scenario/v1"


class GrowthScenarioStageId(StrEnum):
    INSIGHT = "insight"
    GROWTH_PLAN = "growth_plan"
    CONTENT = "content"
    CREATOR = "creator"
    MEDIA = "media"
    PUBLICATION = "publication"
    EFFECT_REVIEW = "effect_review"
    MEMORY_CANDIDATE = "memory_candidate"


class GrowthScenarioOutcomeAxisId(StrEnum):
    PROVIDER = "provider_applied"
    USAGE = "usage_settled"
    EFFECT = "effect_mature"
    MEMORY = "memory_governed"


class GrowthScenarioExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class GrowthScenarioBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class GrowthScenarioStage(AipContractModel):
    stage_id: GrowthScenarioStageId
    status: Literal["ready", "blocked", "unknown"]
    exact_refs: list[GrowthScenarioExactRef] = Field(default_factory=list, max_length=40)
    contribution: str = Field(min_length=1, max_length=500)
    blockers: list[GrowthScenarioBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_stage(self) -> "GrowthScenarioStage":
        identities = [(ref.resource_type, ref.resource_id, ref.revision, ref.content_hash) for ref in self.exact_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("growth scenario stage exact refs must be unique")
        if self.status == "ready" and (not self.exact_refs or self.blockers):
            raise ValueError("ready growth scenario stage requires exact refs and no blockers")
        if self.status != "ready" and (self.exact_refs or not self.blockers):
            raise ValueError("non-ready growth scenario stage requires blockers and no trusted refs")
        return self


class GrowthScenarioConservationLedger(AipContractModel):
    tasks_expected: int = Field(ge=0)
    tasks_observed: int = Field(ge=0)
    handoffs_expected: int = Field(ge=0)
    handoffs_observed: int = Field(ge=0)
    outcomes_expected: int = Field(ge=0)
    outcomes_ready: int = Field(ge=0)
    outcomes_blocked: int = Field(ge=0)
    outcomes_unknown: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves(self) -> "GrowthScenarioConservationLedger":
        if self.tasks_observed > self.tasks_expected or self.handoffs_observed > self.handoffs_expected:
            raise ValueError("growth scenario observed counts cannot exceed expected counts")
        if self.outcomes_expected != self.outcomes_ready + self.outcomes_blocked + self.outcomes_unknown:
            raise ValueError("growth scenario outcomes must conserve denominator")
        return self


class GrowthScenarioOutcomeAxis(AipContractModel):
    axis_id: GrowthScenarioOutcomeAxisId
    status: Literal["ready", "blocked", "unknown"]
    exact_ref: GrowthScenarioExactRef | None = None
    blocker: GrowthScenarioBlocker | None = None

    @model_validator(mode="after")
    def _honest_axis(self) -> "GrowthScenarioOutcomeAxis":
        if self.status == "ready" and (self.exact_ref is None or self.blocker is not None):
            raise ValueError("ready growth outcome axis requires exact ref")
        if self.status != "ready" and (self.exact_ref is not None or self.blocker is None):
            raise ValueError("non-ready growth outcome axis requires one blocker")
        return self


class GrowthScenarioCommands(AipContractModel):
    materialize: Literal[False] = False
    dispatch: Literal[False] = False
    publish: Literal[False] = False
    promote_memory: Literal[False] = False


class GrowthScenarioContribution(AipContractModel):
    schema_version: Literal[GROWTH_SCENARIO_SCHEMA_VERSION] = GROWTH_SCENARIO_SCHEMA_VERSION
    status: Literal["blocked"] = "blocked"
    root_plan_ref: GrowthScenarioExactRef | None = None
    scenario_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    evaluated_at: datetime
    stages: list[GrowthScenarioStage] = Field(min_length=8, max_length=8)
    ledger: GrowthScenarioConservationLedger
    outcome_axes: list[GrowthScenarioOutcomeAxis] = Field(min_length=4, max_length=4)
    blockers: list[GrowthScenarioBlocker] = Field(min_length=1, max_length=40)
    commands: GrowthScenarioCommands = Field(default_factory=GrowthScenarioCommands)
    external_effects_allowed: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("growth scenario evaluation requires timezone")
        return value

    @model_validator(mode="after")
    def _canonical_and_fail_closed(self) -> "GrowthScenarioContribution":
        if [stage.stage_id for stage in self.stages] != list(GrowthScenarioStageId):
            raise ValueError("growth scenario stages require canonical order")
        if [axis.axis_id for axis in self.outcome_axes] != list(GrowthScenarioOutcomeAxisId):
            raise ValueError("growth scenario outcome axes require canonical order")
        if (self.root_plan_ref is None) != (self.scenario_binding_hash is None):
            raise ValueError("growth scenario root and binding hash must appear together")
        if self.root_plan_ref is not None and self.root_plan_ref.resource_type != "GrowthPlanRevision":
            raise ValueError("growth scenario root must be GrowthPlanRevision")
        growth_plan_stage = self.stages[list(GrowthScenarioStageId).index(GrowthScenarioStageId.GROWTH_PLAN)]
        if self.root_plan_ref is not None and growth_plan_stage.status == "ready" and self.root_plan_ref not in growth_plan_stage.exact_refs:
            raise ValueError("growth scenario root must be included in the ready growth_plan stage")
        if not any(stage.status != "ready" for stage in self.stages) and not any(axis.status != "ready" for axis in self.outcome_axes):
            raise ValueError("W8-01 cannot claim operational ready under the no-effect contract")
        return self


__all__ = [name for name in globals() if name.startswith("GROWTH_SCENARIO") or name.startswith("GrowthScenario")]
