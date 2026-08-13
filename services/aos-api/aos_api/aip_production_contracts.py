"""Strict W2 production contract DTOs."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext


class BriefLifecycle(StrEnum):
    DRAFT = "draft"
    FROZEN = "frozen"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"


class Coverage(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class Freshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ContractReadiness(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    STALE = "stale"
    UNKNOWN = "unknown"


class AssigneeKind(StrEnum):
    AGENT_INSTANCE = "agent_instance"
    HUMAN_PRINCIPAL = "human_principal"
    TOOL_BINDING = "tool_binding"
    PROVIDER_CAPABILITY_BINDING = "provider_capability_binding"


class ExactRevisionRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class AssigneeRef(AipContractModel):
    kind: AssigneeKind
    resource_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)


class ResponsibilitySlot(AipContractModel):
    slot_id: str = Field(min_length=1, max_length=160)
    responsibility_type: str = Field(min_length=1, max_length=160)
    required_capability_ids: list[str] = Field(min_length=1)
    input_schema_ref: ResourceRef
    output_schema_ref: ResourceRef
    gate_refs: list[ExactRevisionRef] = Field(default_factory=list)
    return_stage: str = Field(min_length=1, max_length=160)
    assignee: AssigneeRef

    @field_validator("required_capability_ids")
    @classmethod
    def _capabilities_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not value.strip() for value in values):
            raise ValueError("required capability IDs must be unique and non-blank")
        return values


class MergeDecision(AipContractModel):
    source_slot_ids: list[str] = Field(min_length=1)
    target_slot_id: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=1000)
    merged_responsibility_types: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _protected_responsibilities_are_independent(self) -> MergeDecision:
        protected = {
            "independent_review",
            "hard_compliance",
            "external_publication_approval",
            "receipt_reconciliation",
        }
        if protected.intersection(self.merged_responsibility_types):
            raise ValueError("protected responsibility cannot be merged")
        if len(self.source_slot_ids) != len(set(self.source_slot_ids)):
            raise ValueError("source slot IDs must be unique")
        return self


class CreateEvalContractRequest(AipContractModel):
    suite_ref: ExactRevisionRef
    publication_ref: ExactRevisionRef | None = None
    release_gate_ref: ExactRevisionRef | None = None
    artifact_schema_ref: ResourceRef
    severity_thresholds: dict[str, float] = Field(min_length=1)
    gate_policy: dict[str, Any]
    return_mapping: dict[str, str]
    override_policy: dict[str, Any]

    @model_validator(mode="after")
    def _eval_contract_integrity(self) -> CreateEvalContractRequest:
        if self.suite_ref.resource_type != "EvalSuiteRevision":
            raise ValueError("suiteRef must reference EvalSuiteRevision")
        if any(not name.strip() or value < 0 or value > 1 for name, value in self.severity_thresholds.items()):
            raise ValueError("severity thresholds must be named values between 0 and 1")
        if self.publication_ref and self.publication_ref.resource_type != "PublicationEvent":
            raise ValueError("publicationRef must reference PublicationEvent")
        if self.release_gate_ref and self.release_gate_ref.resource_type != "ReleaseGateDecision":
            raise ValueError("releaseGateRef must reference ReleaseGateDecision")
        return self


class CreateResponsibilityPlanRequest(AipContractModel):
    profile: str = Field(min_length=1, max_length=80)
    template_ref: ExactRevisionRef
    slots: list[ResponsibilitySlot] = Field(min_length=1)
    merge_decisions: list[MergeDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def _slot_ids_are_unique(self) -> CreateResponsibilityPlanRequest:
        slot_ids = [slot.slot_id for slot in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("slot IDs must be unique")
        if self.template_ref.resource_type != "ResponsibilityTemplateRevision":
            raise ValueError("templateRef must reference ResponsibilityTemplateRevision")
        return self


class CreateBriefRequest(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    brief_type: str = Field(min_length=1, max_length=160)
    schema_ref: ResourceRef
    spec: dict[str, Any]


class ReviseBriefRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    brief_type: str = Field(min_length=1, max_length=160)
    schema_ref: ResourceRef
    spec: dict[str, Any]


class TaskBriefRevision(AipContractModel):
    tenant: TenantContext
    brief_id: str
    task_id: str
    revision: int
    version: int
    brief_type: str
    schema_ref: ResourceRef
    spec: dict[str, Any]
    content_hash: str
    lifecycle: BriefLifecycle
    created_by: str
    created_at: datetime


class TaskBriefListResponse(AipContractModel):
    tenant: TenantContext
    items: list[TaskBriefRevision]
    count: int = Field(ge=0)


class CreateEvidenceBundleRequest(AipContractModel):
    brief_ref: ExactRevisionRef
    subject_refs: list[ResourceRef] = Field(default_factory=list)
    cutoff_at: datetime
    item_refs: list[ExactRevisionRef] = Field(min_length=1)
    coverage: Coverage
    missing: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    uncertainties: list[dict[str, Any]] = Field(default_factory=list)
    freshness: Freshness
    marking: list[str] = Field(default_factory=list)
    license_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("marking")
    @classmethod
    def _marking_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not value.strip() for value in values):
            raise ValueError("marking must be unique and non-blank")
        return values


class EvidenceBundleRevision(AipContractModel):
    tenant: TenantContext
    bundle_id: str
    revision: int
    brief_ref: ExactRevisionRef
    subject_refs: list[ResourceRef]
    cutoff_at: datetime
    item_refs: list[ExactRevisionRef]
    coverage: Coverage
    missing: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    uncertainties: list[dict[str, Any]]
    freshness: Freshness
    marking: list[str]
    license_summary: dict[str, Any]
    content_hash: str
    lifecycle: BriefLifecycle
    created_by: str
    created_at: datetime


class EvidenceBundleListResponse(AipContractModel):
    tenant: TenantContext
    items: list[EvidenceBundleRevision]
    count: int = Field(ge=0)
