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


class StageApplicabilityKind(StrEnum):
    ALWAYS = "always"
    PROFILE_IN = "profile_in"


class ArtifactRelationType(StrEnum):
    FAMILY_MEMBER = "family_member"
    VARIANT_OF = "variant_of"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"


class ReviewSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ReviewIssueStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    RETURNED = "returned"
    SUPERSEDED = "superseded"


class ExactRevisionRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ContractBlocker(AipContractModel):
    code: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)
    resource_ref: ExactRevisionRef | None = None


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


class ReviseEvalContractRequest(CreateEvalContractRequest):
    expected_version: int = Field(ge=1)


class EvalContractRevision(CreateEvalContractRequest):
    tenant: TenantContext
    contract_id: str
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle: BriefLifecycle
    readiness: ContractReadiness
    blockers: list[ContractBlocker]
    created_by: str
    created_at: datetime


class EvalContractListResponse(AipContractModel):
    tenant: TenantContext
    items: list[EvalContractRevision]
    count: int = Field(ge=0)


class ReviseResponsibilityPlanRequest(CreateResponsibilityPlanRequest):
    expected_version: int = Field(ge=1)


class ResponsibilityPlanRevision(CreateResponsibilityPlanRequest):
    tenant: TenantContext
    plan_id: str
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    coverage: Coverage
    uncovered_slots: list[str]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle: BriefLifecycle
    readiness: ContractReadiness
    blockers: list[ContractBlocker]
    created_by: str
    created_at: datetime


class ResponsibilityPlanListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ResponsibilityPlanRevision]
    count: int = Field(ge=0)


class StageApplicability(AipContractModel):
    kind: StageApplicabilityKind
    profiles: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _controlled_predicate(self) -> StageApplicability:
        if self.kind is StageApplicabilityKind.ALWAYS and self.profiles:
            raise ValueError("always applicability cannot declare profiles")
        if self.kind is StageApplicabilityKind.PROFILE_IN:
            if not self.profiles or any(not item.strip() for item in self.profiles):
                raise ValueError("profile_in applicability requires non-blank profiles")
            if len(self.profiles) != len(set(self.profiles)):
                raise ValueError("applicability profiles must be unique")
        return self


class StageDefinition(AipContractModel):
    stage_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    depends_on: list[str] = Field(default_factory=list)
    applicability: StageApplicability
    required_slot_ids: list[str] = Field(min_length=1)
    input_schema_ref: ResourceRef
    output_schema_ref: ResourceRef
    gate_refs: list[ExactRevisionRef] = Field(default_factory=list)
    checkpoint_policy: dict[str, Any] = Field(default_factory=dict)
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    compensation_policy: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _stage_lists_are_unique(self) -> StageDefinition:
        for label, values in (
            ("dependsOn", self.depends_on),
            ("requiredSlotIds", self.required_slot_ids),
        ):
            if len(values) != len(set(values)) or any(not item.strip() for item in values):
                raise ValueError(f"{label} must be unique and non-blank")
        if self.stage_id in self.depends_on:
            raise ValueError("stage cannot depend on itself")
        return self


class CreateStageTemplateRequest(AipContractModel):
    profile: str = Field(min_length=1, max_length=80)
    source_bundle_ref: ExactRevisionRef
    stages: list[StageDefinition] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _stage_ids_are_unique(self) -> CreateStageTemplateRequest:
        stage_ids = [stage.stage_id for stage in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("stage IDs must be unique")
        return self


class ReviseStageTemplateRequest(CreateStageTemplateRequest):
    expected_version: int = Field(ge=1)


class StageTemplateRevision(CreateStageTemplateRequest):
    tenant: TenantContext
    template_id: str
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle: BriefLifecycle
    sealed_by: str | None = None
    sealed_at: datetime | None = None
    seal_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    readiness: ContractReadiness
    blockers: list[ContractBlocker]
    created_by: str
    created_at: datetime

    @model_validator(mode="after")
    def _frozen_revision_has_seal(self) -> StageTemplateRevision:
        sealed = self.sealed_by is not None and self.sealed_at is not None and self.seal_hash is not None
        if (self.lifecycle is BriefLifecycle.FROZEN) is not sealed:
            raise ValueError("only frozen StageTemplate revisions carry a complete seal")
        return self


class StageTemplateListResponse(AipContractModel):
    tenant: TenantContext
    items: list[StageTemplateRevision]
    count: int = Field(ge=0)


class CompileStageTemplateRequest(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    expected_task_version: int = Field(ge=1)
    template_revision: int = Field(ge=1)
    template_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    responsibility_plan_ref: ExactRevisionRef
    profile: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def _responsibility_ref_type(self) -> CompileStageTemplateRequest:
        if self.responsibility_plan_ref.resource_type != "ResponsibilityPlanRevision":
            raise ValueError("responsibilityPlanRef must reference ResponsibilityPlanRevision")
        return self


class StageCompilationResult(AipContractModel):
    tenant: TenantContext
    task_id: str
    template_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    plan_ref: ExactRevisionRef
    compiler_version: str
    applicable_stage_ids: list[str]
    not_applicable_stage_ids: list[str]
    created_at: datetime


class ExactArtifactRef(AipContractModel):
    artifact_id: str = Field(min_length=1, max_length=200)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CreateArtifactRelationRequest(AipContractModel):
    relation_type: ArtifactRelationType
    from_artifact: ExactArtifactRef
    to_artifact: ExactArtifactRef
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _not_self_relation(self) -> CreateArtifactRelationRequest:
        if self.from_artifact.artifact_id == self.to_artifact.artifact_id:
            raise ValueError("artifact relation cannot reference the same artifact")
        return self


class ArtifactRelation(CreateArtifactRelationRequest):
    tenant: TenantContext
    relation_id: str
    created_by: str
    created_at: datetime


class ArtifactRelationListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ArtifactRelation]
    count: int = Field(ge=0)


class CreateReviewIssueRequest(AipContractModel):
    rule_ref: ExactRevisionRef
    severity: ReviewSeverity
    artifact_ref: ExactArtifactRef
    eval_report_ref: ExactRevisionRef
    location: dict[str, Any]
    evidence_refs: list[ExactRevisionRef] = Field(default_factory=list)
    suggested_fix: str = Field(min_length=1, max_length=4000)
    return_stage: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def _review_refs(self) -> CreateReviewIssueRequest:
        if self.eval_report_ref.resource_type != "EvalReportRevision":
            raise ValueError("evalReportRef must reference EvalReportRevision")
        if any(ref.resource_type != "Evidence" for ref in self.evidence_refs):
            raise ValueError("evidenceRefs must reference Evidence")
        return self


class ReviewIssue(CreateReviewIssueRequest):
    tenant: TenantContext
    issue_id: str
    status: ReviewIssueStatus
    version: int = Field(ge=1)
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime


class ReviewIssueListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ReviewIssue]
    count: int = Field(ge=0)


class ResolveReviewIssueRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)
    resolution_refs: list[ExactRevisionRef] = Field(default_factory=list)


class ReturnReviewIssueRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    run_id: str = Field(min_length=1, max_length=200)
    target_stage: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2000)
    attempt_idempotency_key: str = Field(min_length=1, max_length=160)


class ReturnDecision(AipContractModel):
    tenant: TenantContext
    decision_id: str
    issue_id: str
    issue_version: int = Field(ge=1)
    run_id: str
    step_key: str
    step_run_id: str
    attempt: int = Field(ge=1)
    attempt_idempotency_key: str
    reason: str
    decision_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str
    created_at: datetime


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
