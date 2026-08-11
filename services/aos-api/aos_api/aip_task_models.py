"""AIP-1 HTTP/store models built on the frozen AIP-0 contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from aos_api.aip_contracts import (
    ActorRef,
    AipContractModel,
    PlanRevision,
    PlanStep,
    ResourceRef,
    TaskContract,
    TaskRun,
)


class CreateTaskRequest(AipContractModel):
    type: str = "generic"
    title: str
    description: str = ""
    priority: int = Field(default=50, ge=0, le=100)
    goal: dict[str, Any] = Field(default_factory=dict)
    selection_ref: ResourceRef | None = None
    policy_revision: str | None = None

    @field_validator("type", "title")
    @classmethod
    def _required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field must not be empty")
        return cleaned


class TaskSnapshot(TaskContract):
    description: str = ""
    goal: dict[str, Any] = Field(default_factory=dict)
    selection_ref: ResourceRef | None = None
    policy_revision: str | None = None
    updated_at: datetime


class TaskListResponse(AipContractModel):
    items: list[TaskSnapshot] = Field(default_factory=list)
    count: int


class CreatePlanRevisionRequest(AipContractModel):
    expected_task_version: int = Field(ge=1)
    steps: list[PlanStep] = Field(min_length=1, max_length=500)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    risk: dict[str, Any] = Field(default_factory=dict)


class PlanRevisionSnapshot(PlanRevision):
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    risk: dict[str, Any] = Field(default_factory=dict)
    approval_status: Literal["draft", "approved", "superseded", "rejected"]
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_by: ActorRef


class ApprovePlanRevisionRequest(AipContractModel):
    expected_task_version: int = Field(ge=1)
    expected_content_hash: str

    @field_validator("expected_content_hash")
    @classmethod
    def _hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
            raise ValueError("expected_content_hash must be a sha256 digest")
        return normalized


class CreateTaskRunRequest(AipContractModel):
    plan_revision_id: str
    expected_task_version: int = Field(ge=1)
    logic_graph_id: str | None = None
    logic_revision: int | None = Field(default=None, ge=1)


class TaskRunSnapshot(TaskRun):
    logic_graph_id: str | None = None
    logic_revision: int | None = None
    version: int = Field(ge=1)
    created_by: ActorRef
    created_at: datetime
    updated_at: datetime


class TaskTimeline(AipContractModel):
    task: TaskSnapshot
    plan: PlanRevisionSnapshot
    run: TaskRunSnapshot
    steps: list[dict[str, Any]] = Field(default_factory=list)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class RunControlRequest(AipContractModel):
    expected_run_version: int = Field(ge=1)
    expected_task_version: int = Field(ge=1)
    reason: str = ""


class RunControlResult(AipContractModel):
    task: TaskSnapshot
    run: TaskRunSnapshot


class ClaimStepRequest(AipContractModel):
    step_key: str
    worker_id: str
    lease_seconds: int = Field(default=30, ge=5, le=300)

    @field_validator("step_key", "worker_id")
    @classmethod
    def _claim_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("claim fields must not be empty")
        return cleaned


class StepLease(AipContractModel):
    step_run_id: str
    run_id: str
    step_key: str
    attempt: int
    worker_id: str
    lease_expires_at: datetime
