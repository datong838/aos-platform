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


__all__ = [
    "TASK_COCKPIT_SCHEMA_VERSION",
    "TaskCockpitBlocker",
    "TaskCockpitBlockerSeverity",
    "TaskCockpitCheckpointPageEnvelope",
    "TaskCockpitCheckpointSummary",
    "TaskCockpitCoreEnvelope",
    "TaskCockpitPageInfo",
    "TaskCockpitReadiness",
    "TaskCockpitRunSummary",
    "TaskCockpitStateConsistency",
    "TaskCockpitStepPageEnvelope",
    "TaskCockpitStepSummary",
    "TaskCockpitTaskSummary",
]
