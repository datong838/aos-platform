"""AIP v1 shared public contracts.

This module freezes cross-wave DTOs only.  Importing it does not register
routes, allocate stores, or imply that Task/Run persistence is available.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aos_api.public_contracts import TaskStatus


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


class AipContractModel(BaseModel):
    """Strict base model with canonical camelCase JSON aliases."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class ResourceRef(AipContractModel):
    resource_type: str
    resource_id: str
    revision: str | None = None
    authority: str

    @field_validator("resource_type", "resource_id", "authority")
    @classmethod
    def _required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("resource reference fields must not be empty")
        return cleaned


class TenantContext(AipContractModel):
    """Response/evidence context; request values never authorize access."""

    org_id: str
    project_id: str


class PageInfo(AipContractModel):
    limit: int = Field(ge=1, le=500)
    next_cursor: str | None = None
    has_more: bool = False


class EvidenceRef(AipContractModel):
    evidence_id: str
    evidence_type: str
    content_hash: str
    created_at: datetime


class ArtifactRef(AipContractModel):
    artifact_id: str
    artifact_type: str
    revision: str | None = None
    content_hash: str | None = None


class ActorRef(AipContractModel):
    actor_type: str
    actor_id: str


class TaskRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class StepRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


class ActionRiskLevel(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class ActionProposalStatus(StrEnum):
    PROPOSED = "proposed"
    DRAFTED = "drafted"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    LEASED = "leased"
    EXECUTING = "executing"
    APPLIED = "applied"
    FAILED = "failed"
    UNKNOWN = "unknown"
    RECONCILED = "reconciled"
    COMPENSATED = "compensated"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ActionReceiptStatus(StrEnum):
    ACCEPTED = "accepted"
    APPLIED = "applied"
    FAILED = "failed"
    UNKNOWN = "unknown"
    RECONCILED = "reconciled"


TERMINAL_TASK_RUN_STATUSES = frozenset(
    {TaskRunStatus.SUCCEEDED, TaskRunStatus.FAILED, TaskRunStatus.CANCELLED, TaskRunStatus.UNKNOWN}
)
TERMINAL_STEP_RUN_STATUSES = frozenset(
    {StepRunStatus.SUCCEEDED, StepRunStatus.FAILED, StepRunStatus.SKIPPED, StepRunStatus.UNKNOWN}
)


class TaskContract(AipContractModel):
    id: str
    type: str
    title: str
    status: TaskStatus
    priority: int = Field(ge=0, le=100)
    created_by: ActorRef
    created_at: datetime
    current_plan_revision_id: str | None = None
    version: int = Field(ge=1)


class PlanStep(AipContractModel):
    step_key: str
    title: str
    capability_ref: ResourceRef | None = None
    input_refs: list[ResourceRef] = Field(default_factory=list)


class PlanRevision(AipContractModel):
    id: str
    task_id: str
    revision: int = Field(ge=1)
    content_hash: str
    steps: list[PlanStep]
    created_at: datetime


class TaskRun(AipContractModel):
    id: str
    task_id: str
    plan_revision_id: str
    status: TaskRunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_checkpoint_id: str | None = None


class RunError(AipContractModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None


class StepRun(AipContractModel):
    id: str
    run_id: str
    step_key: str
    attempt: int = Field(ge=1)
    status: StepRunStatus
    input_refs: list[ResourceRef] = Field(default_factory=list)
    output_refs: list[ResourceRef] = Field(default_factory=list)
    error: RunError | None = None


class Checkpoint(AipContractModel):
    id: str
    run_id: str
    sequence: int = Field(ge=1)
    state_hash: str
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    created_at: datetime


class Artifact(AipContractModel):
    id: str
    type: str
    uri: str | None = None
    ref: ResourceRef | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Evidence(AipContractModel):
    id: str
    type: str
    subject_ref: ResourceRef
    content_hash: str
    source: str
    freshness_at: datetime
    created_at: datetime

    @field_validator("content_hash")
    @classmethod
    def _content_hash(cls, value: str) -> str:
        normalized = value.lower().strip()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("content_hash must be a sha256 hex digest")
        return normalized


class ActionTypeRevisionRef(AipContractModel):
    action_type_id: str
    revision_hash: str
    object_type: str

    @field_validator("revision_hash")
    @classmethod
    def _revision_hash(cls, value: str) -> str:
        normalized = value.lower().strip()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("revision_hash must be a sha256 hex digest")
        return normalized


class ActionProposal(AipContractModel):
    id: str
    action_type: ActionTypeRevisionRef
    task_id: str | None = None
    run_id: str | None = None
    object_ref: ResourceRef | None = None
    purpose: str
    risk_level: ActionRiskLevel
    payload: dict[str, Any]
    proposal_hash: str
    status: ActionProposalStatus
    expires_at: datetime
    version: int = Field(ge=1)
    created_by: ActorRef
    created_at: datetime
    updated_at: datetime


class DraftSnapshot(AipContractModel):
    id: str
    proposal_id: str
    proposal_version: int = Field(ge=1)
    proposal_hash: str
    diff: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[ResourceRef] = Field(default_factory=list)
    status: str
    created_at: datetime


class ApprovalEvent(AipContractModel):
    id: str
    proposal_id: str
    proposal_version: int = Field(ge=1)
    proposal_hash: str
    decision: ApprovalDecision
    actor: ActorRef
    reason: str = ""
    expires_at: datetime | None = None
    created_at: datetime


class ExecutionLease(AipContractModel):
    id: str
    proposal_id: str
    proposal_hash: str
    attempt: int = Field(ge=1)
    expires_at: datetime
    created_at: datetime


class ActionReceipt(AipContractModel):
    id: str
    proposal_id: str
    lease_id: str
    status: ActionReceiptStatus
    provider_request_id: str | None = None
    evidence_refs: list[ResourceRef] = Field(default_factory=list)
    created_at: datetime


AIP_ERROR_STATUS: dict[str, int] = {
    "AIP_INVALID_ARGUMENT": 400,
    "AUTH_REQUIRED": 401,
    "AIP_SCOPE_FORBIDDEN": 403,
    "AIP_RESOURCE_NOT_FOUND": 404,
    "AIP_VERSION_CONFLICT": 409,
    "AIP_IDEMPOTENCY_CONFLICT": 409,
    "AIP_INVALID_TRANSITION": 422,
    "AIP_BUDGET_EXCEEDED": 429,
    "AIP_CAPABILITY_NOT_ACTIVE": 501,
    "AIP_DEPENDENCY_UNAVAILABLE": 503,
    "AIP_OUTCOME_UNKNOWN": 504,
}


AIP_CONTRACT_MODELS = (
    ResourceRef,
    TenantContext,
    PageInfo,
    EvidenceRef,
    ArtifactRef,
    ActorRef,
    TaskContract,
    PlanRevision,
    TaskRun,
    StepRun,
    Checkpoint,
    Artifact,
    Evidence,
    ActionTypeRevisionRef,
    ActionProposal,
    DraftSnapshot,
    ApprovalEvent,
    ExecutionLease,
    ActionReceipt,
)
