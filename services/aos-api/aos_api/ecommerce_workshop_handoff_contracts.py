"""Compile-only contracts for Workshop module handoffs.

The compiler produces the canonical AIP ``IssueHandoffRequest``.  It never
issues a token or persists a second Handoff authority.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_agent_registry_contracts import IssueHandoffRequest
from aos_api.aip_contracts import AipContractModel, HandoffResourceRef, ResourceRef, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef


MODULE_ID_PATTERN = r"^ecommerce[.][a-z0-9]+(?:[.-][a-z0-9]+)*$"
RESERVED_CONTEXT_FIELDS = (
    "sourceModuleId",
    "targetModuleId",
    "sourceSlotId",
    "targetSlotId",
    "purpose",
    "requestedOutcome",
)


class ModuleHandoffCompileRequest(AipContractModel):
    handoff_id: str = Field(min_length=1, max_length=200)
    task_ref: ResourceRef
    run_ref: ResourceRef
    source_module_id: str = Field(pattern=MODULE_ID_PATTERN)
    target_module_id: str = Field(pattern=MODULE_ID_PATTERN)
    source_slot_id: str = Field(min_length=1, max_length=160)
    target_slot_id: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=240)
    requested_outcome: str = Field(min_length=1, max_length=500)
    object_refs: list[HandoffResourceRef | ResourceRef] = Field(default_factory=list, max_length=100)
    artifact_refs: list[HandoffResourceRef | ResourceRef] = Field(default_factory=list, max_length=100)
    evidence_refs: list[HandoffResourceRef | ResourceRef] = Field(default_factory=list, max_length=100)
    context: dict[str, Any] = Field(default_factory=dict)
    allowed_context_fields: list[str] = Field(default_factory=list, max_length=64)
    markings: list[str] = Field(min_length=1, max_length=32)
    expires_at: datetime
    correlation_ref: ResourceRef | None = None

    @field_validator("allowed_context_fields", "markings")
    @classmethod
    def _unique_non_blank(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("allowlist and markings must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _minimal_disclosure(self) -> ModuleHandoffCompileRequest:
        if self.task_ref.resource_type != "Task" or self.run_ref.resource_type != "TaskRun":
            raise ValueError("handoff task and run refs must be exact Task/TaskRun refs")
        if self.task_ref.revision is None or self.run_ref.revision is None:
            raise ValueError("handoff task and run refs require exact revisions")
        if self.source_module_id == self.target_module_id:
            raise ValueError("source and target module must differ")
        if self.source_slot_id == self.target_slot_id:
            raise ValueError("source and target slot must differ")
        allowed = set(self.allowed_context_fields)
        if set(self.context) - allowed:
            raise ValueError("handoff context contains fields outside the allowlist")
        if set(self.context) & set(RESERVED_CONTEXT_FIELDS):
            raise ValueError("handoff context cannot override compiler fields")
        return self


class ModuleHandoffCompileBlocker(AipContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    dependency: str = Field(min_length=1, max_length=160)
    required_action: str = Field(min_length=1, max_length=500)


class ModuleHandoffCompileSideEffects(AipContractModel):
    handoffs_issued: Literal[0] = 0
    tokens_minted: Literal[0] = 0
    decisions_created: Literal[0] = 0
    agent_runs_started: Literal[0] = 0


class ModuleHandoffCompileResponse(AipContractModel):
    schema_version: Literal["aos.ecommerce-workshop.module-handoff-compile/v1"] = (
        "aos.ecommerce-workshop.module-handoff-compile/v1"
    )
    tenant: TenantContext
    run_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    evaluated_at: datetime
    responsibility_plan_ref: ExactRevisionRef
    source_module_id: str = Field(pattern=MODULE_ID_PATTERN)
    target_module_id: str = Field(pattern=MODULE_ID_PATTERN)
    source_slot_id: str = Field(min_length=1, max_length=160)
    target_slot_id: str = Field(min_length=1, max_length=160)
    readiness: Literal["ready", "blocked"]
    blockers: list[ModuleHandoffCompileBlocker] = Field(default_factory=list, max_length=32)
    issue_command: IssueHandoffRequest | None = None
    side_effects: ModuleHandoffCompileSideEffects = Field(default_factory=ModuleHandoffCompileSideEffects)

    @model_validator(mode="after")
    def _readiness_matches_command(self) -> ModuleHandoffCompileResponse:
        if self.readiness == "ready" and (self.blockers or self.issue_command is None):
            raise ValueError("ready compilation requires one command and no blockers")
        if self.readiness == "blocked" and (not self.blockers or self.issue_command is not None):
            raise ValueError("blocked compilation requires blockers and no command")
        return self
