"""AIP-1 HTTP/store models built on the frozen AIP-0 contracts."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

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

    @model_validator(mode="after")
    def _validate_workshop_business_task(self) -> "CreateTaskRequest":
        if self.type != "ecommerce.workshop.business_task":
            return self
        if len(self.title) < 4 or len(self.title) > 120:
            raise ValueError("workshop business task title must contain 4 to 120 characters")
        if not re.search(r"[\u3400-\u9fff]", self.title):
            raise ValueError("workshop business task title must use Chinese business language")
        if re.search(
            r"(?:^|\s)(?:R\d+(?:-[0-9A-Z]+)?|W\d+(?:-[0-9A-Z]+)?|BI-W\d+|AOS-\d+)"
            r"|\b(?:Skill|Provider|AgentRun|Receipt)\b|(?:开发|代码|技术方案)",
            self.title,
            re.IGNORECASE,
        ):
            raise ValueError("workshop business task title must not contain development work")
        assignment = self.goal.get("workshopAssignment")
        if not isinstance(assignment, dict):
            raise ValueError("goal.workshopAssignment is required for workshop business tasks")
        allowed_roles = {
            "customer_service": "客服专员",
            "private_domain_manager": "私域管家",
            "shopping_advisor": "导购顾问",
            "data_advisor": "数据参谋",
            "content_officer": "内容官",
            "campaign_planner": "活动策划师",
        }
        role_key = assignment.get("roleKey")
        if allowed_roles.get(role_key) != assignment.get("colleagueName") or assignment.get("status") != "requested":
            raise ValueError("goal.workshopAssignment must identify a requested workshop colleague")
        return self


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
    dependency_snapshot_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    pause_requested_at: datetime | None = None
    pause_reason: str | None = None
    version: int = Field(ge=1)
    created_by: ActorRef
    created_at: datetime
    updated_at: datetime


class TaskRunListResponse(AipContractModel):
    items: list[TaskRunSnapshot] = Field(default_factory=list)
    count: int


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
    fence: int = Field(ge=1)
    assignment_lease_id: str
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    lease_expires_at: datetime
