"""Strict GET-only W8-03 cross-domain dispatch scenario contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


DISPATCH_SCENARIO_SCHEMA_VERSION = "aos.ecommerce-workshop.dispatch-scenario/v1"


class DispatchScenarioStageId(StrEnum):
    TASK_GRAPH = "task_graph"
    DISPATCH_INTENT = "dispatch_intent"
    HANDOFF = "handoff"
    RECEIVER_DECISION = "receiver_decision"
    REQUEST_MORE_OR_RETURN = "request_more_or_return"
    TAKEOVER = "takeover"
    OWNER_TIMELINE = "owner_timeline"


class DispatchScenarioOutcomeAxisId(StrEnum):
    DISPATCH_DECISION = "dispatch_decision_recorded"
    RECEIVER_REAUTHORIZATION = "receiver_reauthorized"
    SINGLE_ACTIVE_OWNER = "single_active_owner"
    TAKEOVER_DECISION = "takeover_decided"
    EXECUTION_RECONCILIATION = "execution_reconciled"


class DispatchScenarioExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class DispatchScenarioBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class DispatchScenarioRoleBinding(AipContractModel):
    role_ref: DispatchScenarioExactRef
    assignee_ref: DispatchScenarioExactRef
    skill_binding_ref: DispatchScenarioExactRef

    @model_validator(mode="after")
    def _layer_types_are_exact(self) -> "DispatchScenarioRoleBinding":
        if self.role_ref.resource_type != "AgentTemplate":
            raise ValueError("dispatch scenario role must be AgentTemplate")
        if self.assignee_ref.resource_type != "AgentInstance":
            raise ValueError("dispatch scenario assignee must be AgentInstance")
        if self.skill_binding_ref.resource_type != "SkillBinding":
            raise ValueError("dispatch scenario binding must be SkillBinding")
        return self


class DispatchScenarioComposition(AipContractModel):
    atomic_skill_refs: list[DispatchScenarioExactRef] = Field(min_length=1, max_length=30)
    logic_revision_ref: DispatchScenarioExactRef
    role_bindings: list[DispatchScenarioRoleBinding] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def _skill_logic_role_layers_are_distinct(self) -> "DispatchScenarioComposition":
        if any(ref.resource_type != "SkillRevision" for ref in self.atomic_skill_refs):
            raise ValueError("dispatch scenario atomic skills must be SkillRevision")
        if self.logic_revision_ref.resource_type != "LogicRevision":
            raise ValueError("dispatch scenario logic must be LogicRevision")
        skill_ids = [(ref.resource_id, ref.revision, ref.content_hash) for ref in self.atomic_skill_refs]
        binding_ids = [item.skill_binding_ref.resource_id for item in self.role_bindings]
        if len(skill_ids) != len(set(skill_ids)) or len(binding_ids) != len(set(binding_ids)):
            raise ValueError("dispatch scenario composition identities must be unique")
        return self


class DispatchScenarioStage(AipContractModel):
    stage_id: DispatchScenarioStageId
    status: Literal["ready", "blocked", "unknown"]
    exact_refs: list[DispatchScenarioExactRef] = Field(default_factory=list, max_length=40)
    contribution: str = Field(min_length=1, max_length=500)
    blockers: list[DispatchScenarioBlocker] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _honest_stage(self) -> "DispatchScenarioStage":
        identities = [
            (ref.resource_type, ref.resource_id, ref.revision, ref.content_hash)
            for ref in self.exact_refs
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("dispatch scenario stage exact refs must be unique")
        if self.status == "ready" and (not self.exact_refs or self.blockers):
            raise ValueError("ready dispatch stage requires exact refs and no blockers")
        if self.status != "ready" and (self.exact_refs or not self.blockers):
            raise ValueError("non-ready dispatch stage requires blockers and no trusted refs")
        return self


class DispatchScenarioDecisionLedger(AipContractModel):
    tasks_expected: int = Field(ge=0)
    tasks_observed: int = Field(ge=0)
    handoffs_expected: int = Field(ge=0)
    handoffs_observed: int = Field(ge=0)
    decisions_expected: int = Field(ge=0)
    decisions_recorded: int = Field(ge=0)
    accepted: int = Field(ge=0)
    rejected: int = Field(ge=0)
    request_more: int = Field(ge=0)
    returned: int = Field(ge=0)
    takeover_requested: int = Field(ge=0)
    takeover_decided: int = Field(ge=0)
    active_owner_count: int = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _conserves(self) -> "DispatchScenarioDecisionLedger":
        if self.tasks_observed > self.tasks_expected or self.handoffs_observed > self.handoffs_expected:
            raise ValueError("dispatch observed counts cannot exceed expected counts")
        if self.decisions_recorded > self.decisions_expected:
            raise ValueError("dispatch decisions cannot exceed expected decisions")
        if self.decisions_recorded != self.accepted + self.rejected + self.request_more + self.returned:
            raise ValueError("dispatch decision categories must conserve recorded decisions")
        if self.takeover_decided > self.takeover_requested:
            raise ValueError("takeover decisions cannot exceed requests")
        return self


class DispatchScenarioOutcomeAxis(AipContractModel):
    axis_id: DispatchScenarioOutcomeAxisId
    status: Literal["ready", "blocked", "unknown"]
    exact_ref: DispatchScenarioExactRef | None = None
    blocker: DispatchScenarioBlocker | None = None

    @model_validator(mode="after")
    def _honest_axis(self) -> "DispatchScenarioOutcomeAxis":
        if self.status == "ready" and (self.exact_ref is None or self.blocker is not None):
            raise ValueError("ready dispatch outcome axis requires exact ref")
        if self.status != "ready" and (self.exact_ref is not None or self.blocker is None):
            raise ValueError("non-ready dispatch outcome axis requires one blocker")
        return self


class DispatchScenarioCommands(AipContractModel):
    dispatch: Literal[False] = False
    decide_handoff: Literal[False] = False
    request_takeover: Literal[False] = False
    approve_takeover: Literal[False] = False
    mutate_owner: Literal[False] = False


class DispatchScenarioContribution(AipContractModel):
    schema_version: Literal[DISPATCH_SCENARIO_SCHEMA_VERSION] = DISPATCH_SCENARIO_SCHEMA_VERSION
    status: Literal["blocked"] = "blocked"
    root_task_graph_ref: DispatchScenarioExactRef | None = None
    root_task_run_ref: DispatchScenarioExactRef | None = None
    dispatch_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    composition: DispatchScenarioComposition | None = None
    evaluated_at: datetime
    stages: list[DispatchScenarioStage] = Field(min_length=7, max_length=7)
    ledger: DispatchScenarioDecisionLedger
    outcome_axes: list[DispatchScenarioOutcomeAxis] = Field(min_length=5, max_length=5)
    blockers: list[DispatchScenarioBlocker] = Field(min_length=1, max_length=50)
    commands: DispatchScenarioCommands = Field(default_factory=DispatchScenarioCommands)
    external_effects_allowed: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("dispatch scenario evaluation requires timezone")
        return value

    @model_validator(mode="after")
    def _canonical_and_fail_closed(self) -> "DispatchScenarioContribution":
        if [stage.stage_id for stage in self.stages] != list(DispatchScenarioStageId):
            raise ValueError("dispatch scenario stages require canonical order")
        if [axis.axis_id for axis in self.outcome_axes] != list(DispatchScenarioOutcomeAxisId):
            raise ValueError("dispatch scenario outcome axes require canonical order")
        roots = (self.root_task_graph_ref, self.root_task_run_ref, self.dispatch_binding_hash, self.composition)
        if any(item is None for item in roots) != all(item is None for item in roots):
            raise ValueError("dispatch scenario roots, binding and composition must appear together")
        if self.root_task_graph_ref is not None and self.root_task_graph_ref.resource_type != "TaskGraphRevision":
            raise ValueError("dispatch scenario graph root must be TaskGraphRevision")
        if self.root_task_run_ref is not None and self.root_task_run_ref.resource_type != "TaskRun":
            raise ValueError("dispatch scenario run root must be TaskRun")
        root_stage = self.stages[0]
        if self.root_task_graph_ref is not None and root_stage.status == "ready":
            if self.root_task_graph_ref not in root_stage.exact_refs or self.root_task_run_ref not in root_stage.exact_refs:
                raise ValueError("dispatch scenario roots must be included in task_graph stage")
        if not any(stage.status != "ready" for stage in self.stages) and not any(
            axis.status != "ready" for axis in self.outcome_axes
        ):
            raise ValueError("W8-03 cannot claim operational ready under the no-command contract")
        return self


__all__ = [name for name in globals() if name.startswith("DISPATCH_SCENARIO") or name.startswith("DispatchScenario")]
