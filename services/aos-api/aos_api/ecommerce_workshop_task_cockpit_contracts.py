"""Strict read-only contracts for the ecommerce Task Cockpit core slice."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import (
    AipContractModel,
    StepRunStatus,
    TaskRunStatus,
    TenantContext,
)
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.public_contracts import TaskStatus


TASK_COCKPIT_SCHEMA_VERSION = "aos.ecommerce-workshop.task-cockpit/v1"


class TaskCockpitReadiness(StrEnum):
    DEGRADED = "degraded"


class TaskCockpitStateConsistency(StrEnum):
    CURRENT_STATE_PER_PAGE = "current_state_per_page"


class TaskCockpitBlockerSeverity(StrEnum):
    WARNING = "warning"
    BLOCKING = "blocking"


class TaskCockpitBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    severity: TaskCockpitBlockerSeverity
    dependency: str = Field(min_length=1, max_length=160)
    required_action: str = Field(min_length=1, max_length=500)


class TaskCockpitRunSummary(AipContractModel):
    run_id: str = Field(min_length=1, max_length=200)
    plan_revision_id: str = Field(min_length=1, max_length=200)
    status: TaskRunStatus
    version: int = Field(ge=1)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("started_at", "finished_at", "created_at", "updated_at")
    @classmethod
    def _aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value


class TaskCockpitTaskSummary(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    task_type: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    status: TaskStatus
    priority: int = Field(ge=0, le=100)
    version: int = Field(ge=1)
    current_plan_revision_id: str | None = Field(default=None, max_length=200)
    created_at: datetime
    updated_at: datetime
    run: TaskCockpitRunSummary | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value


class TaskCockpitPageInfo(AipContractModel):
    limit: int = Field(ge=1, le=100)
    count: int = Field(ge=0, le=100)
    has_more: bool
    next_cursor: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def _cursor_matches_more(self) -> TaskCockpitPageInfo:
        if self.has_more != (self.next_cursor is not None):
            raise ValueError("hasMore and nextCursor must agree")
        return self


class TaskCockpitCoreEnvelope(AipContractModel):
    schema_version: Literal[TASK_COCKPIT_SCHEMA_VERSION] = TASK_COCKPIT_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    task_cutoff: datetime
    state_consistency: Literal[TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE] = (
        TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE
    )
    readiness: Literal[TaskCockpitReadiness.DEGRADED] = TaskCockpitReadiness.DEGRADED
    blockers: list[TaskCockpitBlocker] = Field(min_length=3, max_length=20)
    items: list[TaskCockpitTaskSummary] = Field(max_length=100)
    page: TaskCockpitPageInfo

    @field_validator("evaluated_at", "task_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _canonical_page(self) -> TaskCockpitCoreEnvelope:
        if self.page.count != len(self.items):
            raise ValueError("page count must equal item count")
        identities = [item.task_id for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("Task Cockpit task identities must be unique")
        return self


class TaskCockpitStepSummary(AipContractModel):
    step_run_id: str = Field(min_length=1, max_length=200)
    step_key: str = Field(min_length=1, max_length=200)
    attempt: int = Field(ge=1)
    status: StepRunStatus
    token_count: int = Field(ge=0)
    cost_amount: Decimal = Field(ge=0)
    has_input_refs: bool
    has_output_refs: bool
    has_error: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value


class TaskCockpitCheckpointSummary(AipContractModel):
    checkpoint_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1)
    schema_version: int = Field(ge=1)
    step_key: str | None = Field(default=None, max_length=200)
    state_hash: str = Field(min_length=1, max_length=200)
    artifact_count: int = Field(ge=0)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value


class TaskCockpitStepPageEnvelope(AipContractModel):
    schema_version: Literal[TASK_COCKPIT_SCHEMA_VERSION] = TASK_COCKPIT_SCHEMA_VERSION
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    evaluated_at: datetime
    membership_cutoff: datetime
    state_consistency: Literal[TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE] = (
        TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE
    )
    items: list[TaskCockpitStepSummary] = Field(max_length=100)
    page: TaskCockpitPageInfo

    @field_validator("evaluated_at", "membership_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _canonical_page(self) -> TaskCockpitStepPageEnvelope:
        if self.page.count != len(self.items):
            raise ValueError("page count must equal item count")
        identities = [item.step_run_id for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("Task Cockpit StepRun identities must be unique")
        return self


class TaskCockpitCheckpointPageEnvelope(AipContractModel):
    schema_version: Literal[TASK_COCKPIT_SCHEMA_VERSION] = TASK_COCKPIT_SCHEMA_VERSION
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    evaluated_at: datetime
    membership_cutoff: datetime
    state_consistency: Literal[TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE] = (
        TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE
    )
    items: list[TaskCockpitCheckpointSummary] = Field(max_length=100)
    page: TaskCockpitPageInfo

    @field_validator("evaluated_at", "membership_cutoff")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _canonical_page(self) -> TaskCockpitCheckpointPageEnvelope:
        if self.page.count != len(self.items):
            raise ValueError("page count must equal item count")
        identities = [item.checkpoint_id for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("Task Cockpit Checkpoint identities must be unique")
        return self


class TaskCockpitStageCompilationItem(AipContractModel):
    stage_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    depends_on: list[str] = Field(default_factory=list, max_length=200)
    required_slot_ids: list[str] = Field(min_length=1, max_length=200)
    applicability_result: Literal["applicable", "not_applicable"]
    evaluated_profile: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def _unique_refs(self) -> TaskCockpitStageCompilationItem:
        for label, values in (
            ("dependsOn", self.depends_on),
            ("requiredSlotIds", self.required_slot_ids),
        ):
            if len(values) != len(set(values)) or any(not item.strip() for item in values):
                raise ValueError(f"{label} must contain unique non-blank values")
        if self.stage_id in self.depends_on:
            raise ValueError("stage cannot depend on itself")
        return self


class TaskCockpitProductionContextEnvelope(AipContractModel):
    schema_version: Literal[TASK_COCKPIT_SCHEMA_VERSION] = TASK_COCKPIT_SCHEMA_VERSION
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    evaluated_at: datetime
    plan_ref: ExactRevisionRef
    stage_template_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    compiler_version: Literal["w2c.v1"]
    stages: list[TaskCockpitStageCompilationItem] = Field(min_length=1, max_length=200)
    applicable_stage_ids: list[str] = Field(default_factory=list, max_length=200)
    not_applicable_stage_ids: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("evaluated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _exact_stage_partition(self) -> TaskCockpitProductionContextEnvelope:
        if self.plan_ref.resource_type != "PlanRevision":
            raise ValueError("planRef must reference PlanRevision")
        if self.stage_template_ref.resource_type != "StageTemplateRevision":
            raise ValueError("stageTemplateRef must reference StageTemplateRevision")
        if self.responsibility_plan_ref.resource_type != "ResponsibilityPlanRevision":
            raise ValueError("responsibilityPlanRef must reference ResponsibilityPlanRevision")
        stage_ids = [item.stage_id for item in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("stage compilation identities must be unique")
        applicable = self.applicable_stage_ids
        not_applicable = self.not_applicable_stage_ids
        if len(applicable) != len(set(applicable)) or len(not_applicable) != len(set(not_applicable)):
            raise ValueError("stage applicability identities must be unique")
        if set(applicable) & set(not_applicable) or set(stage_ids) != set(applicable) | set(not_applicable):
            raise ValueError("stage applicability must partition the exact compilation")
        for item in self.stages:
            expected = "applicable" if item.stage_id in applicable else "not_applicable"
            if item.applicability_result != expected:
                raise ValueError("stage applicability result drifted")
        return self


class TaskCockpitStructuralAssignee(AipContractModel):
    kind: Literal[
        "agent_instance",
        "human_principal",
        "tool_binding",
        "provider_capability_binding",
    ]
    resource_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    operational_readiness: Literal["unverified"] = "unverified"


class TaskCockpitResponsibilitySlot(AipContractModel):
    slot_id: str = Field(min_length=1, max_length=160)
    responsibility_type: str = Field(min_length=1, max_length=160)
    required_capability_ids: list[str] = Field(min_length=1, max_length=128)
    return_stage: str = Field(min_length=1, max_length=160)
    assignee: TaskCockpitStructuralAssignee

    @model_validator(mode="after")
    def _unique_capabilities(self) -> TaskCockpitResponsibilitySlot:
        if len(self.required_capability_ids) != len(set(self.required_capability_ids)):
            raise ValueError("required capability identities must be unique")
        return self


class TaskCockpitHandoffDecision(AipContractModel):
    decision_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    decision: Literal["accepted", "rejected", "request_more", "returned"]
    reason_code: str | None = Field(default=None, max_length=120)
    gap_codes: list[str] = Field(default_factory=list, max_length=128)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _decision_time_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value


class TaskCockpitHandoffSummary(AipContractModel):
    handoff_id: str = Field(min_length=1, max_length=200)
    status: Literal["issued", "consumed", "expired", "revoked"]
    version: int = Field(ge=1)
    sender_instance_ref: ExactRevisionRef
    receiver_instance_ref: ExactRevisionRef
    expires_at: datetime
    consumed_at: datetime | None = None
    created_at: datetime
    decisions: list[TaskCockpitHandoffDecision] = Field(default_factory=list, max_length=128)

    @field_validator("expires_at", "consumed_at", "created_at")
    @classmethod
    def _handoff_time_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _decision_timeline_is_canonical(self) -> TaskCockpitHandoffSummary:
        revisions = [item.revision for item in self.decisions]
        if revisions != list(range(1, len(revisions) + 1)):
            raise ValueError("handoff decision revisions must be contiguous")
        identities = [item.decision_id for item in self.decisions]
        if len(identities) != len(set(identities)):
            raise ValueError("handoff decision identities must be unique")
        return self


class TaskCockpitResponsibilityHandoffEnvelope(AipContractModel):
    schema_version: Literal[TASK_COCKPIT_SCHEMA_VERSION] = TASK_COCKPIT_SCHEMA_VERSION
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    evaluated_at: datetime
    responsibility_plan_ref: ExactRevisionRef
    profile: str = Field(min_length=1, max_length=80)
    lifecycle: Literal["draft", "frozen", "withdrawn", "superseded"]
    compilation_readiness: Literal["ready_at_compile"] = "ready_at_compile"
    compiled_required_slot_ids: list[str] = Field(min_length=1, max_length=200)
    slots: list[TaskCockpitResponsibilitySlot] = Field(min_length=1, max_length=200)
    handoffs: list[TaskCockpitHandoffSummary] = Field(default_factory=list, max_length=200)

    @field_validator("evaluated_at")
    @classmethod
    def _responsibility_time_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _canonical_responsibility_and_handoffs(self) -> TaskCockpitResponsibilityHandoffEnvelope:
        if self.responsibility_plan_ref.resource_type != "ResponsibilityPlanRevision":
            raise ValueError("responsibilityPlanRef must reference ResponsibilityPlanRevision")
        slot_ids = [item.slot_id for item in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("responsibility slot identities must be unique")
        required = self.compiled_required_slot_ids
        if len(required) != len(set(required)) or not set(required).issubset(slot_ids):
            raise ValueError("compiled required slots must be unique and covered")
        handoff_ids = [item.handoff_id for item in self.handoffs]
        if len(handoff_ids) != len(set(handoff_ids)):
            raise ValueError("handoff identities must be unique")
        return self


__all__ = [
    "TASK_COCKPIT_SCHEMA_VERSION",
    "TaskCockpitBlocker",
    "TaskCockpitBlockerSeverity",
    "TaskCockpitCheckpointPageEnvelope",
    "TaskCockpitCheckpointSummary",
    "TaskCockpitCoreEnvelope",
    "TaskCockpitPageInfo",
    "TaskCockpitProductionContextEnvelope",
    "TaskCockpitResponsibilityHandoffEnvelope",
    "TaskCockpitResponsibilitySlot",
    "TaskCockpitStructuralAssignee",
    "TaskCockpitHandoffDecision",
    "TaskCockpitHandoffSummary",
    "TaskCockpitReadiness",
    "TaskCockpitRunSummary",
    "TaskCockpitStateConsistency",
    "TaskCockpitStepPageEnvelope",
    "TaskCockpitStepSummary",
    "TaskCockpitStageCompilationItem",
    "TaskCockpitTaskSummary",
]
