"""Strict GET-only W8-05 FULL video production and recovery contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


FULL_VIDEO_SCENARIO_SCHEMA_VERSION = "aos.ecommerce-workshop.full-video-scenario/v1"


class FullVideoStageId(StrEnum):
    BRIEF_PROFILE = "brief_profile"
    COMPILE_START = "compile_start"
    SCRIPT_ART = "script_art"
    STORYBOARD_CAPTURE = "storyboard_capture"
    POST_REVIEW = "post_review"
    PUBLISH_DELIVERY = "publish_delivery"
    SETTLEMENT_EFFECT = "settlement_effect"


class FullVideoResponsibilityId(StrEnum):
    PRODUCER = "media.producer"
    DIRECTOR = "media.director"
    SCREENWRITER = "media.screenwriter"
    ART = "media.art"
    STORYBOARD = "media.storyboard"
    CAPTURE = "media.capture"
    POST = "media.post"
    REVIEW = "media.review"


class FullVideoFaultId(StrEnum):
    CRASH_BEFORE_SUBMIT = "crash_before_submit"
    CRASH_AFTER_SUBMIT_BEFORE_RECEIPT = "crash_after_submit_before_receipt"
    LEASE_FENCE_LOSS = "lease_fence_loss"
    WEBHOOK_ORDERING = "webhook_ordering"
    TIMEOUT_CANCEL_LATE_RESULT = "timeout_cancel_late_result"
    CHECKPOINT_DRIFT = "checkpoint_drift"
    CAPACITY_BUDGET_RACE = "capacity_budget_race"
    RESTART_PARTITION = "restart_partition"
    MALICIOUS_ARTIFACT = "malicious_artifact"


class FullVideoExactRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=120)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class FullVideoBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=180)
    required_action: str = Field(min_length=1, max_length=500)


class FullVideoRoleBinding(AipContractModel):
    role_ref: FullVideoExactRef
    assignee_ref: FullVideoExactRef
    skill_binding_ref: FullVideoExactRef

    @model_validator(mode="after")
    def _exact_layers(self) -> "FullVideoRoleBinding":
        if self.role_ref.resource_type != "AgentTemplate":
            raise ValueError("FULL video role must be AgentTemplate")
        if self.assignee_ref.resource_type != "AgentInstance":
            raise ValueError("FULL video assignee must be AgentInstance")
        if self.skill_binding_ref.resource_type != "SkillBinding":
            raise ValueError("FULL video binding must be SkillBinding")
        return self


class FullVideoComposition(AipContractModel):
    atomic_skill_refs: list[FullVideoExactRef] = Field(min_length=1, max_length=40)
    logic_revision_ref: FullVideoExactRef
    role_bindings: list[FullVideoRoleBinding] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _distinct_layers(self) -> "FullVideoComposition":
        if any(ref.resource_type != "SkillRevision" for ref in self.atomic_skill_refs):
            raise ValueError("FULL video atomic skills must be SkillRevision")
        if self.logic_revision_ref.resource_type != "LogicRevision":
            raise ValueError("FULL video logic must be LogicRevision")
        skill_ids = [(ref.resource_id, ref.revision, ref.content_hash) for ref in self.atomic_skill_refs]
        binding_ids = [item.skill_binding_ref.resource_id for item in self.role_bindings]
        if len(skill_ids) != len(set(skill_ids)) or len(binding_ids) != len(set(binding_ids)):
            raise ValueError("FULL video composition identities must be unique")
        return self


class FullVideoResponsibility(AipContractModel):
    responsibility_id: FullVideoResponsibilityId
    label: str = Field(min_length=1, max_length=100)
    status: Literal["assigned", "blocked", "unknown"]
    assignee_ref: FullVideoExactRef | None = None
    skill_binding_ref: FullVideoExactRef | None = None
    independent_review_required: bool = False
    blocker: FullVideoBlocker | None = None

    @model_validator(mode="after")
    def _honest_assignment(self) -> "FullVideoResponsibility":
        if self.status == "assigned":
            if self.assignee_ref is None or self.skill_binding_ref is None or self.blocker is not None:
                raise ValueError("assigned FULL responsibility requires exact assignee and binding")
            if self.assignee_ref.resource_type != "AgentInstance" or self.skill_binding_ref.resource_type != "SkillBinding":
                raise ValueError("FULL responsibility exact types drifted")
        elif self.assignee_ref is not None or self.skill_binding_ref is not None or self.blocker is None:
            raise ValueError("non-assigned FULL responsibility must fail closed")
        return self


class FullVideoStage(AipContractModel):
    stage_id: FullVideoStageId
    status: Literal["ready", "blocked", "unknown"]
    exact_refs: list[FullVideoExactRef] = Field(default_factory=list, max_length=50)
    contribution: str = Field(min_length=1, max_length=500)
    blocker: FullVideoBlocker | None = None

    @model_validator(mode="after")
    def _honest_stage(self) -> "FullVideoStage":
        identities = [(ref.resource_type, ref.resource_id, ref.revision, ref.content_hash) for ref in self.exact_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("FULL video stage refs must be unique")
        if self.status == "ready" and (not self.exact_refs or self.blocker is not None):
            raise ValueError("ready FULL video stage requires exact refs")
        if self.status != "ready" and (self.exact_refs or self.blocker is None):
            raise ValueError("non-ready FULL video stage requires blocker only")
        return self


class FullVideoFaultRecovery(AipContractModel):
    fault_id: FullVideoFaultId
    status: Literal["ready", "blocked", "unknown"]
    recovery_decision: str = Field(min_length=1, max_length=500)
    authority_refs: list[FullVideoExactRef] = Field(default_factory=list, max_length=30)
    blocker: FullVideoBlocker | None = None
    automatic_retry_allowed: Literal[False] = False

    @model_validator(mode="after")
    def _honest_recovery(self) -> "FullVideoFaultRecovery":
        if self.status == "ready" and (not self.authority_refs or self.blocker is not None):
            raise ValueError("ready fault recovery requires durable authority")
        if self.status != "ready" and (self.authority_refs or self.blocker is None):
            raise ValueError("non-ready fault recovery requires blocker only")
        return self


class FullVideoLedger(AipContractModel):
    responsibilities_expected: Literal[8] = 8
    responsibilities_observed: int = Field(ge=0, le=8)
    stages_expected: Literal[7] = 7
    stages_observed: int = Field(ge=0, le=7)
    attempts_expected: int = Field(ge=0)
    attempts_observed: int = Field(ge=0)
    artifacts_expected: int = Field(ge=0)
    artifacts_observed: int = Field(ge=0)
    media_gates_expected: Literal[4] = 4
    media_gates_observed: int = Field(ge=0, le=4)
    fault_cases_expected: Literal[9] = 9
    fault_cases_observed: int = Field(ge=0, le=9)
    usage_buckets_expected: int = Field(ge=0)
    usage_buckets_observed: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves(self) -> "FullVideoLedger":
        pairs = (
            (self.attempts_observed, self.attempts_expected),
            (self.artifacts_observed, self.artifacts_expected),
            (self.usage_buckets_observed, self.usage_buckets_expected),
        )
        if any(observed > expected for observed, expected in pairs):
            raise ValueError("FULL video observed counts cannot exceed expected counts")
        return self


class FullVideoCommands(AipContractModel):
    prepare: Literal[False] = False
    start: Literal[False] = False
    resume: Literal[False] = False
    takeover: Literal[False] = False
    cancel: Literal[False] = False
    reconcile: Literal[False] = False
    publish: Literal[False] = False
    settle: Literal[False] = False


class FullVideoScenarioContribution(AipContractModel):
    schema_version: Literal[FULL_VIDEO_SCENARIO_SCHEMA_VERSION] = FULL_VIDEO_SCENARIO_SCHEMA_VERSION
    status: Literal["blocked"] = "blocked"
    root_brief_ref: FullVideoExactRef | None = None
    task_run_ref: FullVideoExactRef | None = None
    full_production_binding_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    composition: FullVideoComposition | None = None
    evaluated_at: datetime
    responsibilities: list[FullVideoResponsibility] = Field(min_length=8, max_length=8)
    stages: list[FullVideoStage] = Field(min_length=7, max_length=7)
    fault_recovery: list[FullVideoFaultRecovery] = Field(min_length=9, max_length=9)
    ledger: FullVideoLedger
    blockers: list[FullVideoBlocker] = Field(min_length=1, max_length=100)
    commands: FullVideoCommands = Field(default_factory=FullVideoCommands)
    external_effects_allowed: Literal[False] = False
    release_allowed: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("FULL video scenario evaluation requires timezone")
        return value

    @model_validator(mode="after")
    def _canonical_fail_closed(self) -> "FullVideoScenarioContribution":
        if [item.responsibility_id for item in self.responsibilities] != list(FullVideoResponsibilityId):
            raise ValueError("FULL video responsibilities require canonical eight-slot order")
        if [item.stage_id for item in self.stages] != list(FullVideoStageId):
            raise ValueError("FULL video stages require canonical seven-stage order")
        if [item.fault_id for item in self.fault_recovery] != list(FullVideoFaultId):
            raise ValueError("FULL video faults require canonical nine-case order")
        roots = (self.root_brief_ref, self.task_run_ref, self.full_production_binding_hash, self.composition)
        if any(item is None for item in roots) != all(item is None for item in roots):
            raise ValueError("FULL video roots, binding and composition must appear together")
        if self.root_brief_ref is not None and self.root_brief_ref.resource_type != "MediaProductionBriefRevision":
            raise ValueError("FULL video root must be MediaProductionBriefRevision")
        if self.task_run_ref is not None and self.task_run_ref.resource_type != "TaskRun":
            raise ValueError("FULL video run must be TaskRun")
        if self.ledger.responsibilities_observed != sum(item.status == "assigned" for item in self.responsibilities):
            raise ValueError("FULL video responsibility ledger drifted")
        if self.ledger.stages_observed != sum(item.status == "ready" for item in self.stages):
            raise ValueError("FULL video stage ledger drifted")
        if self.ledger.fault_cases_observed != sum(item.status == "ready" for item in self.fault_recovery):
            raise ValueError("FULL video fault ledger drifted")
        if all(item.status == "ready" for item in self.stages) and all(item.status == "ready" for item in self.fault_recovery):
            raise ValueError("W8-05 cannot claim operational readiness under no-command contract")
        return self


__all__ = [name for name in globals() if name.startswith("FULL_VIDEO") or name.startswith("FullVideo")]
