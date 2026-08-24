"""Responsibility successor and runtime takeover contracts (W3-07).

Structural coverage, observed readiness, pre-run reassignment and runtime
ownership are intentionally separate authorities.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import AssigneeRef, ExactRevisionRef


class RuntimeAuthorityRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)


class AssignmentBlocker(AipContractModel):
    code: str = Field(min_length=1, max_length=120)
    dependency: str = Field(min_length=1, max_length=200)
    required_action: str = Field(min_length=1, max_length=500)


class CreateResponsibilitySuccessorRequest(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    source_plan_ref: ExactRevisionRef
    expected_source_version: int = Field(ge=1)
    slot_id: str = Field(min_length=1, max_length=160)
    target_assignee: AssigneeRef
    resolution_receipt_id: str = Field(min_length=1, max_length=200)
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,119}$")

    @model_validator(mode="after")
    def _source_is_responsibility_plan(self) -> CreateResponsibilitySuccessorRequest:
        if self.source_plan_ref.resource_type != "ResponsibilityPlanRevision":
            raise ValueError("sourcePlanRef must reference ResponsibilityPlanRevision")
        return self


class ResponsibilitySuccessorReceipt(AipContractModel):
    tenant: TenantContext
    successor_id: str
    task_id: str
    source_plan_ref: ExactRevisionRef
    successor_plan_ref: ExactRevisionRef
    slot_id: str
    source_assignee: AssigneeRef
    target_assignee: AssigneeRef
    resolution_receipt_id: str
    reason_code: str
    actor: str
    created_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class TakeoverSafetyState(StrEnum):
    SAFE_CHECKPOINT = "safe_checkpoint"
    ACTIVE_LEASE = "active_lease"
    PROVIDER_OUTCOME_UNKNOWN = "provider_outcome_unknown"
    STEP_TERMINAL = "step_terminal"


class CreateTakeoverRequest(AipContractModel):
    task_run_ref: RuntimeAuthorityRef
    step_run_ref: RuntimeAuthorityRef
    attempt: int = Field(ge=1)
    source_owner: AssigneeRef
    target_owner: AssigneeRef
    resolution_receipt_id: str = Field(min_length=1, max_length=200)
    expected_fence: int = Field(ge=0)
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,119}$")

    @model_validator(mode="after")
    def _runtime_refs_are_exact(self) -> CreateTakeoverRequest:
        if self.task_run_ref.resource_type != "TaskRun":
            raise ValueError("taskRunRef must reference TaskRun")
        if self.step_run_ref.resource_type != "StepRun":
            raise ValueError("stepRunRef must reference StepRun")
        if self.source_owner == self.target_owner:
            raise ValueError("takeover target must differ from source owner")
        return self


class TakeoverRequestStatus(StrEnum):
    PENDING = "pending"
    BLOCKED = "blocked"


class TakeoverRequestReceipt(AipContractModel):
    tenant: TenantContext
    request_id: str
    task_run_ref: RuntimeAuthorityRef
    step_run_ref: RuntimeAuthorityRef
    attempt: int
    source_owner: AssigneeRef
    target_owner: AssigneeRef
    resolution_receipt_id: str
    expected_fence: int
    reason_code: str
    safety_state: TakeoverSafetyState
    status: TakeoverRequestStatus
    blockers: list[AssignmentBlocker] = Field(default_factory=list)
    maker: str
    created_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _status_matches_blockers(self) -> TakeoverRequestReceipt:
        if (self.status is TakeoverRequestStatus.PENDING) != (not self.blockers):
            raise ValueError("takeover request status/blockers drifted")
        return self


class TakeoverDecisionValue(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class DecideTakeoverRequest(AipContractModel):
    expected_version: int = Field(ge=0)
    decision: TakeoverDecisionValue
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,119}$")
    lease_expires_at: datetime | None = None

    @model_validator(mode="after")
    def _approved_requires_lease_expiry(self) -> DecideTakeoverRequest:
        if (self.decision is TakeoverDecisionValue.APPROVED) != (
            self.lease_expires_at is not None
        ):
            raise ValueError("approved takeover requires leaseExpiresAt only")
        return self


class ExecutionAssignmentLease(AipContractModel):
    lease_id: str
    task_run_ref: RuntimeAuthorityRef
    step_run_ref: RuntimeAuthorityRef
    attempt: int = Field(ge=1)
    owner: AssigneeRef
    fence: int = Field(ge=1)
    expires_at: datetime


class TakeoverDecisionReceipt(AipContractModel):
    tenant: TenantContext
    decision_id: str
    request_id: str
    revision: int = Field(ge=1)
    decision: TakeoverDecisionValue
    reason_code: str
    checker: str
    assignment_lease: ExecutionAssignmentLease | None = None
    created_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _approval_matches_lease(self) -> TakeoverDecisionReceipt:
        if (self.decision is TakeoverDecisionValue.APPROVED) != (
            self.assignment_lease is not None
        ):
            raise ValueError("takeover decision/lease drifted")
        return self


class AssertAssignmentFenceRequest(AipContractModel):
    step_run_ref: RuntimeAuthorityRef
    attempt: int = Field(ge=1)
    owner: AssigneeRef
    fence: int = Field(ge=1)


class AssignmentFenceObservation(AipContractModel):
    tenant: TenantContext
    allowed: bool
    lease: ExecutionAssignmentLease | None = None
    blockers: list[AssignmentBlocker] = Field(default_factory=list)
    evaluated_at: datetime

    @model_validator(mode="after")
    def _allowed_matches_lease(self) -> AssignmentFenceObservation:
        if self.allowed != (self.lease is not None and not self.blockers):
            raise ValueError("assignment fence observation drifted")
        return self


class ResponsibilityAssignmentObservation(AipContractModel):
    tenant: TenantContext
    run_ref: RuntimeAuthorityRef
    takeover_requests: list[TakeoverRequestReceipt] = Field(default_factory=list)
    takeover_decisions: list[TakeoverDecisionReceipt] = Field(default_factory=list)
    assignment_leases: list[ExecutionAssignmentLease] = Field(default_factory=list)
    evaluated_at: datetime

    @model_validator(mode="after")
    def _run_is_exact_and_membership_is_unique(
        self,
    ) -> ResponsibilityAssignmentObservation:
        if self.run_ref.resource_type != "TaskRun":
            raise ValueError("runRef must reference TaskRun")
        if any(item.task_run_ref != self.run_ref for item in self.takeover_requests):
            raise ValueError("takeover request runRef drifted")
        if any(item.task_run_ref != self.run_ref for item in self.assignment_leases):
            raise ValueError("assignment lease runRef drifted")
        if len({item.request_id for item in self.takeover_requests}) != len(
            self.takeover_requests
        ):
            raise ValueError("duplicate takeover request")
        if len({item.decision_id for item in self.takeover_decisions}) != len(
            self.takeover_decisions
        ):
            raise ValueError("duplicate takeover decision")
        return self


__all__ = [
    "AssertAssignmentFenceRequest",
    "AssignmentBlocker",
    "AssignmentFenceObservation",
    "CreateResponsibilitySuccessorRequest",
    "CreateTakeoverRequest",
    "DecideTakeoverRequest",
    "ExecutionAssignmentLease",
    "ResponsibilitySuccessorReceipt",
    "ResponsibilityAssignmentObservation",
    "RuntimeAuthorityRef",
    "TakeoverDecisionReceipt",
    "TakeoverDecisionValue",
    "TakeoverRequestReceipt",
    "TakeoverRequestStatus",
    "TakeoverSafetyState",
]
