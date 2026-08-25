"""Strict read-only contracts for the ecommerce Task Cockpit core slice."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import (
    AipContractModel,
    ResourceRef,
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
    blockers: list[TaskCockpitBlocker] = Field(min_length=1, max_length=20)
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
    lease_owner: str | None = Field(default=None, max_length=200)
    lease_expires_at: datetime | None = None
    fence: int | None = Field(default=None, ge=1)
    assignment_lease_id: str | None = Field(default=None, max_length=240)
    input_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_request_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    safe_point: bool
    reconcile_required: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", "lease_expires_at")
    @classmethod
    def _aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value


class TaskCockpitCheckpointSummary(AipContractModel):
    checkpoint_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1)
    schema_version: int = Field(ge=1)
    step_key: str | None = Field(default=None, max_length=200)
    state_hash: str = Field(min_length=1, max_length=200)
    artifact_count: int = Field(ge=0)
    attempt: int | None = Field(default=None, ge=1)
    plan_revision_id: str | None = Field(default=None, max_length=200)
    input_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_request_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    dependency_snapshot_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    resume_readiness: Literal["checkpoint_exact", "legacy_unverified"]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _exact_checkpoint_is_complete(self) -> TaskCockpitCheckpointSummary:
        exact = all(
            value is not None
            for value in (
                self.attempt,
                self.plan_revision_id,
                self.input_hash,
                self.provider_request_fingerprint,
                self.dependency_snapshot_hash,
            )
        )
        if (self.resume_readiness == "checkpoint_exact") != exact:
            raise ValueError("Checkpoint resume readiness drifted")
        return self


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


class TaskCockpitSkillContributionReadiness(AipContractModel):
    status: Literal[
        "available", "degraded", "disabled", "blocked", "unknown", "stale"
    ]
    freshness: Literal["fresh", "stale", "unverified"]
    reason_codes: list[str] = Field(default_factory=list, max_length=128)
    binding_status: Literal["provisioning", "active", "suspended", "revoked"]
    last_verified_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("last_verified_at", "expires_at")
    @classmethod
    def _aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _freshness_is_honest(self) -> TaskCockpitSkillContributionReadiness:
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("Skill contribution reason codes must be unique")
        if self.freshness == "fresh" and (
            self.last_verified_at is None or self.expires_at is None
        ):
            raise ValueError("fresh readiness requires an exact verification window")
        if self.status == "available" and (
            self.freshness != "fresh" or self.binding_status != "active"
        ):
            raise ValueError("available readiness requires fresh active Binding evidence")
        if self.status == "stale" and self.freshness != "stale":
            raise ValueError("stale readiness must expose stale freshness")
        return self


class TaskCockpitSkillRunProjection(AipContractModel):
    status: Literal[
        "queued", "running", "paused", "succeeded", "failed", "cancelled", "unknown"
    ]
    started_at: datetime | None = None
    updated_at: datetime
    waiting_for: list[str] = Field(default_factory=list, max_length=128)

    @field_validator("started_at", "updated_at")
    @classmethod
    def _aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value


class TaskCockpitSkillContribution(AipContractModel):
    contribution_id: str = Field(min_length=1, max_length=200)
    task_run_ref: ResourceRef
    agent_run_ref: ResourceRef
    module_id: Literal["ecommerce.task-cockpit"] = "ecommerce.task-cockpit"
    role_ref: ExactRevisionRef
    assignee_ref: ExactRevisionRef
    skill_revision_ref: ExactRevisionRef
    binding_ref: ResourceRef
    logic_revision_ref: ExactRevisionRef
    display_name: str = Field(min_length=1, max_length=240)
    purpose: str = Field(min_length=1, max_length=500)
    responsibility: str = Field(min_length=1, max_length=160)
    readiness: TaskCockpitSkillContributionReadiness
    run_projection: TaskCockpitSkillRunProjection
    input_refs: list[ResourceRef] = Field(default_factory=list, max_length=200)
    output_artifact_refs: list[ResourceRef] = Field(default_factory=list, max_length=200)
    assumptions: list[str] = Field(default_factory=list, max_length=64)
    uncertainties: list[str] = Field(default_factory=list, max_length=64)
    conflicts: list[str] = Field(default_factory=list, max_length=64)
    missing_inputs: list[str] = Field(default_factory=list, max_length=64)
    allowed_commands: list[str] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def _canonical_refs_and_read_only(self) -> TaskCockpitSkillContribution:
        expected = {
            "task_run_ref": "TaskRun",
            "agent_run_ref": "AgentRun",
            "binding_ref": "SkillBinding",
            "role_ref": "AgentTemplate",
            "assignee_ref": "AgentInstance",
            "skill_revision_ref": "SkillTemplate",
            "logic_revision_ref": "LogicRevision",
        }
        for field_name, resource_type in expected.items():
            if getattr(self, field_name).resource_type != resource_type:
                raise ValueError(f"{field_name} must reference {resource_type}")
        if self.allowed_commands:
            raise ValueError("S2.5 Skill contribution pilot is strictly read-only")
        for field_name in (
            "assumptions",
            "uncertainties",
            "conflicts",
            "missing_inputs",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)) or any(not item.strip() for item in values):
                raise ValueError(f"{field_name} must contain unique non-blank values")
        return self


class TaskCockpitSkillContributionEnvelope(AipContractModel):
    schema_version: Literal[TASK_COCKPIT_SCHEMA_VERSION] = TASK_COCKPIT_SCHEMA_VERSION
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    evaluated_at: datetime
    projection_status: Literal["ready", "blocked"]
    blocker_codes: list[str] = Field(default_factory=list, max_length=128)
    items: list[TaskCockpitSkillContribution] = Field(default_factory=list, max_length=200)

    @field_validator("evaluated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _status_matches_items(self) -> TaskCockpitSkillContributionEnvelope:
        if len(self.blocker_codes) != len(set(self.blocker_codes)):
            raise ValueError("Skill contribution blockers must be unique")
        if self.projection_status == "ready" and self.blocker_codes:
            raise ValueError("ready Skill contribution projection cannot have blockers")
        if self.projection_status == "blocked" and not self.blocker_codes:
            raise ValueError("blocked Skill contribution projection requires blockers")
        identities = [item.contribution_id for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("Skill contribution identities must be unique")
        if any(item.task_run_ref.resource_id != self.run_id for item in self.items):
            raise ValueError("Skill contribution TaskRun reference drifted")
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


class TaskCockpitAssigneeResolutionReceipt(AipContractModel):
    receipt_id: str = Field(min_length=1, max_length=200)
    subject_id: str = Field(min_length=1, max_length=240)
    kind: Literal[
        "agent_instance",
        "human_principal",
        "tool_binding",
        "provider_capability_binding",
    ]
    resource_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    status: Literal["resolved", "blocked"]
    blocker_codes: list[str] = Field(default_factory=list, max_length=128)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime | None = None
    required_capability_count: int = Field(ge=0)
    binding_count: int = Field(ge=0)
    snapshot_status: Literal["exact_fresh", "legacy_unverified", "blocked", "stale"]
    created_at: datetime

    @field_validator("created_at", "expires_at")
    @classmethod
    def _resolution_time_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _status_matches_blockers(self) -> TaskCockpitAssigneeResolutionReceipt:
        if len(self.blocker_codes) != len(set(self.blocker_codes)):
            raise ValueError("assignee resolution blocker codes must be unique")
        if (self.status == "resolved") == bool(self.blocker_codes):
            raise ValueError("assignee resolution status and blockers drifted")
        if self.snapshot_status == "exact_fresh" and (
            self.status != "resolved"
            or self.snapshot_hash is None
            or self.expires_at is None
        ):
            raise ValueError("fresh assignee snapshot evidence is incomplete")
        if self.snapshot_status == "blocked" and self.status != "blocked":
            raise ValueError("blocked assignee snapshot status drifted")
        if self.snapshot_status in {"legacy_unverified", "stale"} and self.status != "resolved":
            raise ValueError("non-current assignee snapshot must preserve a resolved receipt")
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
    operational_readiness: Literal[
        "unverified", "resolved_at_observation", "blocked_at_observation"
    ] = "unverified"
    resolution_receipts: list[TaskCockpitAssigneeResolutionReceipt] = Field(
        default_factory=list, max_length=128
    )

    @model_validator(mode="after")
    def _resolution_timeline_is_exact(self) -> TaskCockpitStructuralAssignee:
        expected = (self.kind, self.resource_id, self.version)
        if any(
            (item.kind, item.resource_id, item.version) != expected
            for item in self.resolution_receipts
        ):
            raise ValueError("assignee resolution exact reference drifted")
        ordered = sorted(
            self.resolution_receipts,
            key=lambda item: (item.created_at, item.receipt_id),
        )
        if ordered != self.resolution_receipts:
            raise ValueError("assignee resolution timeline must be canonical")
        if len({item.receipt_id for item in ordered}) != len(ordered):
            raise ValueError("assignee resolution receipt identities must be unique")
        if not ordered:
            if self.operational_readiness != "unverified":
                raise ValueError("missing receipt must remain unverified")
            return self
        latest_at = ordered[-1].created_at
        latest_statuses = {
            item.snapshot_status for item in ordered if item.created_at == latest_at
        }
        if len(latest_statuses) != 1:
            raise ValueError("assignee resolution latest observation conflicts")
        expected_readiness = (
            "resolved_at_observation"
            if ordered[-1].snapshot_status == "exact_fresh"
            else "blocked_at_observation"
        )
        if self.operational_readiness != expected_readiness:
            raise ValueError("assignee operational readiness mapping drifted")
        return self


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
        for slot in self.slots:
            expected_subject = (
                f"responsibility-plan:{self.responsibility_plan_ref.resource_id}"
                f"@{self.responsibility_plan_ref.revision}/slot:{slot.slot_id}"
            )
            if any(
                receipt.subject_id != expected_subject
                for receipt in slot.assignee.resolution_receipts
            ):
                raise ValueError("assignee resolution subject identity drifted")
        handoff_ids = [item.handoff_id for item in self.handoffs]
        if len(handoff_ids) != len(set(handoff_ids)):
            raise ValueError("handoff identities must be unique")
        return self


class TaskCockpitApprovalNavigationTarget(AipContractModel):
    route_identity: Literal["aip.task-plan", "aip.action-drafts"]
    route_path: str = Field(pattern=r"^/aip/(studio|drafts)\?")
    target_ref: ExactRevisionRef
    command_readiness: Literal[
        "read_only_fact", "destination_reauthorization_required"
    ]
    required_permission: str = Field(min_length=1, max_length=160)
    blocker_codes: list[str] = Field(default_factory=list, max_length=32)
    return_focus_token: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _navigation_kind_matches_target(self) -> TaskCockpitApprovalNavigationTarget:
        expected = {
            "aip.task-plan": "PlanRevision",
            "aip.action-drafts": "ActionProposalRevision",
        }[self.route_identity]
        if self.target_ref.resource_type != expected:
            raise ValueError("approval navigation target type drifted")
        if len(self.blocker_codes) != len(set(self.blocker_codes)):
            raise ValueError("approval navigation blocker codes must be unique")
        return self


class TaskCockpitPlanApproval(AipContractModel):
    plan_ref: ExactRevisionRef
    approval_status: Literal["draft", "approved", "superseded", "rejected"]
    approved_by: str | None = Field(default=None, max_length=200)
    approved_at: datetime | None = None
    navigation: TaskCockpitApprovalNavigationTarget

    @field_validator("approved_at")
    @classmethod
    def _plan_approval_time_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _plan_approval_is_consistent(self) -> TaskCockpitPlanApproval:
        if self.plan_ref.resource_type != "PlanRevision":
            raise ValueError("planRef must reference PlanRevision")
        decided = self.approval_status == "approved"
        if decided != (self.approved_by is not None and self.approved_at is not None):
            raise ValueError("approved Plan requires exact actor and timestamp")
        if self.navigation.target_ref != self.plan_ref:
            raise ValueError("Plan approval navigation target drifted")
        return self


class TaskCockpitApprovalDecision(AipContractModel):
    approval_event_id: str = Field(min_length=1, max_length=200)
    proposal_version: int = Field(ge=1)
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["approved", "rejected"]
    actor_id: str = Field(min_length=1, max_length=200)
    expires_at: datetime | None = None
    created_at: datetime

    @field_validator("expires_at", "created_at")
    @classmethod
    def _approval_decision_time_is_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value


class TaskCockpitActionApproval(AipContractModel):
    proposal_ref: ExactRevisionRef
    action_type_id: str = Field(min_length=1, max_length=200)
    status: Literal[
        "proposed", "drafted", "approved", "rejected", "expired", "leased",
        "executing", "applied", "failed", "unknown", "reconciled", "compensated",
    ]
    expires_at: datetime
    decisions: list[TaskCockpitApprovalDecision] = Field(default_factory=list, max_length=128)
    navigation: TaskCockpitApprovalNavigationTarget

    @field_validator("expires_at")
    @classmethod
    def _proposal_expiry_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _action_approval_is_consistent(self) -> TaskCockpitActionApproval:
        if self.proposal_ref.resource_type != "ActionProposalRevision":
            raise ValueError("proposalRef must reference ActionProposalRevision")
        if self.navigation.target_ref != self.proposal_ref:
            raise ValueError("Action approval navigation target drifted")
        ids = [item.approval_event_id for item in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("approval event identities must be unique")
        if any(
            item.proposal_version != self.proposal_ref.revision
            or item.proposal_hash != self.proposal_ref.content_hash
            for item in self.decisions
        ):
            raise ValueError("ApprovalEvent exact proposal reference drifted")
        return self


class TaskCockpitReviewIssueEvent(AipContractModel):
    event_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1)
    event_type: Literal["opened", "resolved", "returned", "superseded"]
    issue_version: int = Field(ge=1)
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    payload: dict[str, Any] | None = None
    payload_readiness: Literal["exact", "legacy_unavailable"]
    actor: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _issue_event_time_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _payload_is_consistent(self) -> TaskCockpitReviewIssueEvent:
        if (self.payload_readiness == "exact") != (self.payload is not None):
            raise ValueError("ReviewIssue event payload readiness drifted")
        return self


class TaskCockpitReviewImpactDecision(AipContractModel):
    step_key: str = Field(min_length=1, max_length=160)
    action: Literal["invalidate", "reuse"]
    reason: str = Field(min_length=1, max_length=500)


class TaskCockpitReviewReturnLineage(AipContractModel):
    decision_id: str = Field(min_length=1, max_length=200)
    issue_version: int = Field(ge=1)
    run_id: str = Field(min_length=1, max_length=200)
    step_key: str = Field(min_length=1, max_length=200)
    step_run_id: str = Field(min_length=1, max_length=200)
    attempt: int = Field(ge=1)
    decision_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    impact_decisions: list[TaskCockpitReviewImpactDecision] = Field(default_factory=list, max_length=500)
    impact_readiness: Literal["exact", "legacy_unavailable"]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _return_time_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _impact_is_consistent(self) -> TaskCockpitReviewReturnLineage:
        if (self.impact_readiness == "exact") != bool(self.impact_decisions):
            raise ValueError("ReviewIssue return impact readiness drifted")
        return self


class TaskCockpitReviewIssue(AipContractModel):
    issue_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    status: Literal["open", "resolved", "returned", "superseded"]
    severity: Literal["info", "warning", "error", "critical"]
    rule_ref: ExactRevisionRef
    artifact_id: str = Field(min_length=1, max_length=200)
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    eval_report_ref: ExactRevisionRef
    return_stage: str = Field(min_length=1, max_length=160)
    evidence_count: int = Field(ge=0)
    lineage_readiness: Literal["attempt_exact", "attempt_unresolved"]
    return_lineage: TaskCockpitReviewReturnLineage | None = None
    events: list[TaskCockpitReviewIssueEvent] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _review_issue_timeline_is_consistent(self) -> TaskCockpitReviewIssue:
        if self.eval_report_ref.resource_type != "EvalReportRevision":
            raise ValueError("evalReportRef must reference EvalReportRevision")
        sequences = [item.sequence for item in self.events]
        if sequences != list(range(1, len(sequences) + 1)):
            raise ValueError("ReviewIssue event sequence must be contiguous")
        if len({item.event_id for item in self.events}) != len(self.events):
            raise ValueError("ReviewIssue event identities must be unique")
        if self.events[-1].issue_version != self.version:
            raise ValueError("ReviewIssue latest event version drifted")
        exact = self.return_lineage is not None
        if exact != (self.lineage_readiness == "attempt_exact"):
            raise ValueError("ReviewIssue attempt readiness drifted")
        if self.status == "returned" and self.return_lineage is None:
            raise ValueError("returned ReviewIssue requires exact return lineage")
        if self.return_lineage is not None and self.return_lineage.step_key != self.return_stage:
            raise ValueError("ReviewIssue return stage drifted")
        return self


class TaskCockpitApprovalReviewEnvelope(AipContractModel):
    schema_version: Literal[TASK_COCKPIT_SCHEMA_VERSION] = TASK_COCKPIT_SCHEMA_VERSION
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    evaluated_at: datetime
    plan_approval: TaskCockpitPlanApproval
    action_approvals: list[TaskCockpitActionApproval] = Field(default_factory=list, max_length=200)
    review_issues: list[TaskCockpitReviewIssue] = Field(default_factory=list, max_length=200)
    action_approval_count: int = Field(ge=0)
    review_issue_count: int = Field(ge=0)
    unresolved_attempt_count: int = Field(ge=0)

    @field_validator("evaluated_at")
    @classmethod
    def _approval_review_time_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _counts_are_conserved(self) -> TaskCockpitApprovalReviewEnvelope:
        if self.action_approval_count != len(self.action_approvals):
            raise ValueError("Action approval count drifted")
        if self.review_issue_count != len(self.review_issues):
            raise ValueError("ReviewIssue count drifted")
        unresolved = sum(
            item.lineage_readiness == "attempt_unresolved" for item in self.review_issues
        )
        if self.unresolved_attempt_count != unresolved:
            raise ValueError("ReviewIssue unresolved attempt count drifted")
        if len({item.proposal_ref.resource_id for item in self.action_approvals}) != len(self.action_approvals):
            raise ValueError("Action proposal identities must be unique")
        if len({item.issue_id for item in self.review_issues}) != len(self.review_issues):
            raise ValueError("ReviewIssue identities must be unique")
        return self


class TaskCockpitActionReceipt(AipContractModel):
    receipt_id: str = Field(min_length=1, max_length=200)
    receipt_kind: Literal["initial", "reconcile"]
    status: Literal["accepted", "applied", "failed", "unknown", "reconciled"]
    lease_id: str = Field(min_length=1, max_length=200)
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_request_present: bool
    evidence_count: int = Field(ge=0)
    supersedes_receipt_id: str | None = Field(default=None, max_length=200)
    resolved_status: Literal["applied", "failed"] | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _receipt_time_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _receipt_kind_is_consistent(self) -> TaskCockpitActionReceipt:
        if self.receipt_kind == "initial":
            if self.status == "reconciled" or self.supersedes_receipt_id is not None:
                raise ValueError("initial ActionReceipt cannot be reconciled or supersede")
            if self.resolved_status is not None:
                raise ValueError("initial ActionReceipt cannot carry resolvedStatus")
        else:
            if self.status != "reconciled" or self.supersedes_receipt_id is None:
                raise ValueError("reconcile ActionReceipt must supersede an initial receipt")
            if self.resolved_status is None:
                raise ValueError("reconcile ActionReceipt requires terminal resolvedStatus")
        return self


class TaskCockpitActionExecution(AipContractModel):
    proposal_ref: ExactRevisionRef
    action_type_id: str = Field(min_length=1, max_length=200)
    proposal_status: Literal[
        "proposed", "drafted", "approved", "rejected", "expired", "leased",
        "executing", "applied", "failed", "unknown", "reconciled", "compensated",
    ]
    lease_id: str | None = Field(default=None, max_length=200)
    attempt: int | None = Field(default=None, ge=1)
    receipts: list[TaskCockpitActionReceipt] = Field(default_factory=list, max_length=2)
    reconciliation_state: Literal["not_started", "not_required", "required", "resolved"]

    @model_validator(mode="after")
    def _receipt_chain_is_consistent(self) -> TaskCockpitActionExecution:
        if self.proposal_ref.resource_type != "ActionProposalRevision":
            raise ValueError("proposalRef must reference ActionProposalRevision")
        if (self.lease_id is None) != (self.attempt is None):
            raise ValueError("Action lease identity and attempt must appear together")
        if self.receipts and self.lease_id is None:
            raise ValueError("Action receipts require an exact lease")
        if any(item.lease_id != self.lease_id for item in self.receipts):
            raise ValueError("ActionReceipt lease drifted")
        if len({item.receipt_id for item in self.receipts}) != len(self.receipts):
            raise ValueError("ActionReceipt identities must be unique")
        initial = [item for item in self.receipts if item.receipt_kind == "initial"]
        reconcile = [item for item in self.receipts if item.receipt_kind == "reconcile"]
        if len(initial) > 1 or len(reconcile) > 1:
            raise ValueError("ActionReceipt chain allows at most one initial and one reconcile")
        if reconcile:
            if not initial or initial[0].status != "unknown":
                raise ValueError("reconcile requires an initial unknown ActionReceipt")
            if reconcile[0].supersedes_receipt_id != initial[0].receipt_id:
                raise ValueError("reconcile supersedes identity drifted")
            if reconcile[0].request_fingerprint != initial[0].request_fingerprint:
                raise ValueError("reconcile request fingerprint drifted")
        expected = "not_started"
        if initial:
            if initial[0].status != "unknown":
                expected = "not_required"
            elif reconcile:
                expected = "resolved"
            else:
                expected = "required"
        if self.reconciliation_state != expected:
            raise ValueError("Action reconciliation state drifted")
        return self


class TaskCockpitActionReceiptEnvelope(AipContractModel):
    schema_version: Literal[TASK_COCKPIT_SCHEMA_VERSION] = TASK_COCKPIT_SCHEMA_VERSION
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    evaluated_at: datetime
    executions: list[TaskCockpitActionExecution] = Field(default_factory=list, max_length=200)
    proposal_count: int = Field(ge=0)
    receipt_count: int = Field(ge=0)
    unknown_receipt_count: int = Field(ge=0)
    reconcile_required_count: int = Field(ge=0)
    reconciled_receipt_count: int = Field(ge=0)

    @field_validator("evaluated_at")
    @classmethod
    def _action_time_is_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Task Cockpit timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _action_counts_are_conserved(self) -> TaskCockpitActionReceiptEnvelope:
        receipts = [receipt for item in self.executions for receipt in item.receipts]
        if self.proposal_count != len(self.executions) or self.receipt_count != len(receipts):
            raise ValueError("Action proposal or receipt count drifted")
        if self.unknown_receipt_count != sum(
            item.receipt_kind == "initial" and item.status == "unknown" for item in receipts
        ):
            raise ValueError("Action unknown receipt count drifted")
        if self.reconcile_required_count != sum(
            item.reconciliation_state == "required" for item in self.executions
        ):
            raise ValueError("Action reconcile-required count drifted")
        if self.reconciled_receipt_count != sum(
            item.receipt_kind == "reconcile" for item in receipts
        ):
            raise ValueError("Action reconciled receipt count drifted")
        if len({item.proposal_ref.resource_id for item in self.executions}) != len(self.executions):
            raise ValueError("Action proposal identities must be unique")
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
    "TaskCockpitActionExecution",
    "TaskCockpitActionReceipt",
    "TaskCockpitApprovalReviewEnvelope",
    "TaskCockpitActionReceiptEnvelope",
    "TaskCockpitAssigneeResolutionReceipt",
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
