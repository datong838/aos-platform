"""Strict contracts for the ecommerce Workshop prepare aggregate."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef


class EvidenceBuildReadiness(StrEnum):
    QUEUED = "queued"
    BLOCKED = "blocked"
    SATISFIED = "satisfied"
    UNKNOWN = "unknown"


class RecommendationCoverage(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class PrepareBriefInput(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    brief_type: str = Field(min_length=1, max_length=160)
    schema_ref: ResourceRef
    spec: dict[str, Any]
    existing_brief_ref: ExactRevisionRef | None = None
    expected_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _revision_pair(self) -> "PrepareBriefInput":
        if (self.existing_brief_ref is None) != (self.expected_version is None):
            raise ValueError("existingBriefRef and expectedVersion must be supplied together")
        if self.existing_brief_ref is not None:
            if self.existing_brief_ref.resource_type != "TaskBriefRevision":
                raise ValueError("existingBriefRef must reference TaskBriefRevision")
        return self


class EcommerceWorkshopPrepareRequest(AipContractModel):
    command: Literal["prepare"] = "prepare"
    brief: PrepareBriefInput
    subject_refs: list[ResourceRef] = Field(default_factory=list)
    canonical_evidence_refs: list[ExactRevisionRef] = Field(default_factory=list)
    cutoff_at: datetime
    purpose: str = Field(min_length=1, max_length=200)
    marking: list[str] = Field(default_factory=list)
    production_profile_ref: ExactRevisionRef
    output_requirements: dict[str, Any] = Field(default_factory=dict)
    workload: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    due_at: datetime | None = None

    @field_validator("marking")
    @classmethod
    def _unique_markings(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("marking values must be unique and non-blank")
        return cleaned

    @field_validator("canonical_evidence_refs")
    @classmethod
    def _evidence_refs(cls, values: list[ExactRevisionRef]) -> list[ExactRevisionRef]:
        if any(value.resource_type != "Evidence" for value in values):
            raise ValueError("canonicalEvidenceRefs must reference Evidence")
        identities = [(value.resource_id, value.revision) for value in values]
        if len(identities) != len(set(identities)):
            raise ValueError("canonicalEvidenceRefs must be unique")
        return values

    @field_validator("production_profile_ref")
    @classmethod
    def _profile_ref(cls, value: ExactRevisionRef) -> ExactRevisionRef:
        if value.resource_type != "ProductionProfileRevision":
            raise ValueError("productionProfileRef must reference ProductionProfileRevision")
        if not value.resource_id.startswith("bundle://"):
            raise ValueError("productionProfileRef must be a Bundle artifact exact ref")
        return value


class BriefDiffChange(AipContractModel):
    field: str
    before: Any = None
    after: Any = None
    impact: str


class EvidenceBuildRequestRevision(AipContractModel):
    request_id: str
    revision: Literal[1] = 1
    brief_ref: ExactRevisionRef
    production_profile_ref: ExactRevisionRef
    required_fact_ids: list[str]
    subject_refs: list[ResourceRef]
    canonical_evidence_refs: list[ExactRevisionRef]
    cutoff_at: datetime
    purpose: str
    marking: list[str]
    readiness: EvidenceBuildReadiness
    missing_fact_ids: list[str]
    blockers: list[ContractBlocker]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResponsibilitySlotRecommendation(AipContractModel):
    slot_id: str
    responsibility_type: str
    atomic_skill_ids: list[str]
    protected: bool
    merge_allowed: bool
    return_stage: str
    candidate_assignee_refs: list[ExactRevisionRef] = Field(default_factory=list)
    readiness: Literal["ready", "blocked", "unknown"]
    blockers: list[ContractBlocker] = Field(default_factory=list)


class ResponsibilityRecommendationRevision(AipContractModel):
    recommendation_id: str
    revision: Literal[1] = 1
    brief_ref: ExactRevisionRef
    production_profile_ref: ExactRevisionRef
    slots: list[ResponsibilitySlotRecommendation]
    coverage: RecommendationCoverage
    uncovered_slot_ids: list[str]
    blockers: list[ContractBlocker]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class PrepareSideEffectCounters(AipContractModel):
    provider_invocation_count: Literal[0] = 0
    provider_fee: Literal[0] = 0
    task_run_created_count: Literal[0] = 0
    agent_run_created_count: Literal[0] = 0
    action_or_handoff_created_count: Literal[0] = 0
    approval_or_execution_lease_created_count: Literal[0] = 0
    external_business_mutation_count: Literal[0] = 0


class PreparationReceipt(AipContractModel):
    preparation_id: str
    revision: Literal[1] = 1
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay: bool
    input_counts: dict[str, int]
    output_counts: dict[str, int]
    side_effects: PrepareSideEffectCounters
    next_allowed_commands: list[str]
    created_at: datetime


class EcommerceWorkshopPrepareResponse(AipContractModel):
    tenant: TenantContext
    module_id: str
    draft_brief_ref: ExactRevisionRef
    brief_diff: list[BriefDiffChange]
    evidence_build_request: EvidenceBuildRequestRevision
    responsibility_recommendation: ResponsibilityRecommendationRevision
    receipt: PreparationReceipt
