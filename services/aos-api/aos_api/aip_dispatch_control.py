"""W3-08 canonical dispatch-intent and task-priority contracts.

Dispatch confirmation records user authorization and a server-owned canonical
command target.  It never duplicates downstream Handoff/Responsibility state.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_responsibility_assignment import RuntimeAuthorityRef


class DispatchCommandKind(StrEnum):
    MODULE_HANDOFF = "module_handoff"
    RESPONSIBILITY_SUCCESSOR = "responsibility_successor"
    RUNTIME_TAKEOVER = "runtime_takeover"


class DispatchIntentStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    CONFIRMED = "confirmed"
    STALE = "stale"


class DispatchBlocker(AipContractModel):
    code: str = Field(min_length=1, max_length=120)
    dependency: str = Field(min_length=1, max_length=200)
    required_action: str = Field(min_length=1, max_length=500)


class DispatchCommandTarget(AipContractModel):
    command_kind: DispatchCommandKind
    route_identity: str = Field(min_length=1, max_length=160)
    route_path: str = Field(pattern=r"^/v1/aip/[a-z0-9_./{}-]+$")
    required_permission: str = Field(min_length=1, max_length=160)


class CreateDispatchIntentRequest(AipContractModel):
    task_ref: RuntimeAuthorityRef
    task_run_ref: RuntimeAuthorityRef | None = None
    step_run_ref: RuntimeAuthorityRef | None = None
    responsibility_plan_ref: ExactRevisionRef | None = None
    command_kind: DispatchCommandKind
    source_identity: str = Field(min_length=1, max_length=200)
    target_identity: str = Field(min_length=1, max_length=200)
    source_slot_id: str | None = Field(default=None, max_length=160)
    target_slot_id: str | None = Field(default=None, max_length=160)
    expected_fence: int | None = Field(default=None, ge=0)
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,119}$")
    policy_ref: ExactRevisionRef
    impact: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _exact_command_shape(self) -> "CreateDispatchIntentRequest":
        if self.task_ref.resource_type != "Task":
            raise ValueError("taskRef must reference Task")
        if self.source_identity == self.target_identity:
            raise ValueError("dispatch target must differ from source")
        if self.task_run_ref and self.task_run_ref.resource_type != "TaskRun":
            raise ValueError("taskRunRef must reference TaskRun")
        if self.step_run_ref and self.step_run_ref.resource_type != "StepRun":
            raise ValueError("stepRunRef must reference StepRun")
        if self.responsibility_plan_ref and self.responsibility_plan_ref.resource_type != "ResponsibilityPlanRevision":
            raise ValueError("responsibilityPlanRef must reference ResponsibilityPlanRevision")
        if self.command_kind is DispatchCommandKind.MODULE_HANDOFF:
            if not self.task_run_ref or not self.responsibility_plan_ref or not self.source_slot_id or not self.target_slot_id:
                raise ValueError("module handoff requires run, responsibility plan and both slots")
        elif self.command_kind is DispatchCommandKind.RESPONSIBILITY_SUCCESSOR:
            if not self.responsibility_plan_ref or not self.source_slot_id:
                raise ValueError("responsibility successor requires responsibility plan and source slot")
            if self.step_run_ref or self.expected_fence is not None:
                raise ValueError("pre-run successor cannot carry runtime fence")
        elif not self.task_run_ref or not self.step_run_ref or self.expected_fence is None:
            raise ValueError("runtime takeover requires run, step and expected fence")
        return self


class DispatchIntentRevision(AipContractModel):
    tenant: TenantContext
    intent_id: str
    revision: int = Field(ge=1)
    task_ref: RuntimeAuthorityRef
    task_run_ref: RuntimeAuthorityRef | None = None
    step_run_ref: RuntimeAuthorityRef | None = None
    responsibility_plan_ref: ExactRevisionRef | None = None
    command: DispatchCommandTarget
    source_identity: str
    target_identity: str
    source_slot_id: str | None = None
    target_slot_id: str | None = None
    expected_fence: int | None = None
    reason_code: str
    policy_ref: ExactRevisionRef
    diff: dict[str, Any]
    impact: dict[str, Any]
    readiness: DispatchIntentStatus
    blockers: list[DispatchBlocker] = Field(default_factory=list)
    maker: str
    created_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _readiness_matches_blockers(self) -> "DispatchIntentRevision":
        if (self.readiness is DispatchIntentStatus.READY) != (not self.blockers):
            raise ValueError("dispatch readiness/blockers drifted")
        return self


class ConfirmDispatchIntentRequest(AipContractModel):
    expected_revision: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class DispatchConfirmationReceipt(AipContractModel):
    tenant: TenantContext
    confirmation_id: str
    intent_id: str
    intent_revision: int
    intent_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    command: DispatchCommandTarget
    invocation_state: str = Field(pattern=r"^canonical_command_required$")
    checker: str
    created_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class DecideTaskPriorityRequest(AipContractModel):
    task_ref: RuntimeAuthorityRef
    old_priority: int = Field(ge=0, le=100)
    new_priority: int = Field(ge=0, le=100)
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,119}$")
    policy_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _priority_change_is_real(self) -> "DecideTaskPriorityRequest":
        if self.task_ref.resource_type != "Task":
            raise ValueError("taskRef must reference Task")
        if self.old_priority == self.new_priority:
            raise ValueError("new priority must differ from old priority")
        return self


class TaskPriorityDecisionRevision(AipContractModel):
    tenant: TenantContext
    decision_id: str
    revision: int = Field(ge=1)
    task_ref_before: RuntimeAuthorityRef
    task_ref_after: RuntimeAuthorityRef
    old_priority: int
    new_priority: int
    reason_code: str
    policy_ref: ExactRevisionRef
    actor: str
    created_at: datetime
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class DispatchControlObservation(AipContractModel):
    tenant: TenantContext
    task_ref: RuntimeAuthorityRef
    dispatch_intents: list[DispatchIntentRevision] = Field(default_factory=list)
    confirmations: list[DispatchConfirmationReceipt] = Field(default_factory=list)
    priority_decisions: list[TaskPriorityDecisionRevision] = Field(default_factory=list)
    evaluated_at: datetime

    @model_validator(mode="after")
    def _all_items_belong_to_task(self) -> "DispatchControlObservation":
        if self.task_ref.resource_type != "Task":
            raise ValueError("observation taskRef must reference Task")
        if any(item.task_ref.resource_id != self.task_ref.resource_id for item in self.dispatch_intents):
            raise ValueError("dispatch intent task membership drifted")
        if any(item.task_ref_after.resource_id != self.task_ref.resource_id for item in self.priority_decisions):
            raise ValueError("priority decision task membership drifted")
        intent_ids = {item.intent_id for item in self.dispatch_intents}
        if any(item.intent_id not in intent_ids for item in self.confirmations):
            raise ValueError("confirmation references an unknown dispatch intent")
        return self
