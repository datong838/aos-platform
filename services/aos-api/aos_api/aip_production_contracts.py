"""Strict W2 production contract DTOs."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
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


class DisclosureLevel(StrEnum):
    L1 = "l1"
    L2 = "l2"
    L3 = "l3"


class DisclosurePurpose(StrEnum):
    SUMMARY = "summary"
    PREVIEW = "preview"
    EXCERPT = "excerpt"
    REVIEW = "review"
    SOURCE = "source"
    AUDIT = "audit"


class DisclosureStatus(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    STALE = "stale"
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


class ReviewImpactAction(StrEnum):
    INVALIDATE = "invalidate"
    REUSE = "reuse"


class ImpactQuality(StrEnum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class ProductionStartDecisionStatus(StrEnum):
    STARTED = "started"
    BLOCKED = "blocked"
    STALE = "stale"
    UNKNOWN = "unknown"


class ExactRevisionRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceExactRevisionRef(ExactRevisionRef):
    resource_type: Literal["Evidence"] = "Evidence"


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
    assignee_resolution_receipt_id: str | None = Field(
        default=None, min_length=1, max_length=240
    )

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
    profile_recommendation_ref: ExactRevisionRef | None = None
    profile_confirmation_id: str | None = Field(default=None, min_length=1, max_length=200)
    merge_policy_ref: ExactRevisionRef | None = None
    merge_decision_receipt_ids: list[str] = Field(default_factory=list, max_length=128)

    @model_validator(mode="after")
    def _slot_ids_are_unique(self) -> CreateResponsibilityPlanRequest:
        slot_ids = [slot.slot_id for slot in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("slot IDs must be unique")
        if self.template_ref.resource_type != "ResponsibilityTemplateRevision":
            raise ValueError("templateRef must reference ResponsibilityTemplateRevision")
        governed = self.profile in {"LITE", "STANDARD", "FULL"}
        governance = (
            self.profile_recommendation_ref,
            self.profile_confirmation_id,
            self.merge_policy_ref,
        )
        if governed and any(item is None for item in governance):
            raise ValueError("governed profile requires recommendation, confirmation and merge policy")
        if not governed and any(item is not None for item in governance):
            raise ValueError("legacy profile cannot attach W6-02 governance")
        if self.profile_recommendation_ref and self.profile_recommendation_ref.resource_type != "ProfileRecommendationRevision":
            raise ValueError("profileRecommendationRef must reference ProfileRecommendationRevision")
        if self.merge_policy_ref and self.merge_policy_ref.resource_type != "MergePolicyRevision":
            raise ValueError("mergePolicyRef must reference MergePolicyRevision")
        if len(self.merge_decision_receipt_ids) != len(set(self.merge_decision_receipt_ids)):
            raise ValueError("merge decision receipt IDs must be unique")
        if len(self.merge_decisions) != len(self.merge_decision_receipt_ids):
            raise ValueError("each merge decision requires one canonical receipt")
        seen_merge_slots: set[str] = set()
        for decision in self.merge_decisions:
            group = {*decision.source_slot_ids, decision.target_slot_id}
            if seen_merge_slots.intersection(group):
                raise ValueError("merge decisions cannot overlap or form a cycle")
            seen_merge_slots.update(group)
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


class EvalContractDiffChange(AipContractModel):
    field: str
    label: str
    before: Any
    after: Any
    impact: str


class EvalContractDiff(AipContractModel):
    tenant: TenantContext
    contract_id: str
    from_revision: int = Field(ge=1)
    to_revision: int = Field(ge=1)
    from_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    to_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    changes: list[EvalContractDiffChange]
    change_count: int = Field(ge=0)
    summary: str


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
    production_context_ref: ExactRevisionRef
    profile: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def _responsibility_ref_type(self) -> CompileStageTemplateRequest:
        if self.responsibility_plan_ref.resource_type != "ResponsibilityPlanRevision":
            raise ValueError("responsibilityPlanRef must reference ResponsibilityPlanRevision")
        if self.production_context_ref.resource_type != "ProductionContextRevision":
            raise ValueError("productionContextRef must reference ProductionContextRevision")
        return self


class StageCompilationResult(AipContractModel):
    tenant: TenantContext
    task_id: str
    template_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    production_context_ref: ExactRevisionRef
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


class RegisterReviewRuleRevisionRequest(AipContractModel):
    rule_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    spec: dict[str, Any]


class ReviewRuleRevision(AipContractModel):
    tenant: TenantContext
    rule_id: str
    revision: int = Field(ge=1)
    spec: dict[str, Any]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class ReviewRuleRevisionListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ReviewRuleRevision]
    count: int = Field(ge=0)


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


class ReviewImpactDecision(AipContractModel):
    step_key: str = Field(min_length=1, max_length=160)
    action: ReviewImpactAction
    reason: str = Field(min_length=1, max_length=500)


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
    impact_decisions: list[ReviewImpactDecision] = Field(default_factory=list, max_length=500)
    impact_readiness: Literal["exact", "legacy_unavailable"]

    @model_validator(mode="after")
    def _impact_is_consistent(self) -> ReturnDecision:
        if (self.impact_readiness == "exact") != bool(self.impact_decisions):
            raise ValueError("return impact readiness drifted")
        return self
    decision_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str
    created_at: datetime


class ReturnDecisionListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ReturnDecision]
    count: int = Field(ge=0)


class MutableAuthorityRef(AipContractModel):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)


class ExternalActionPreviewBinding(AipContractModel):
    """Exact W5 dependencies that must move as one external-Action envelope."""

    purpose: str = Field(min_length=1, max_length=500)
    action_type_ref: ExactRevisionRef
    capability_ref: ExactRevisionRef
    capability_binding_ref: ExactRevisionRef
    account_ref: ExactRevisionRef
    adapter_capability_ref: ExactRevisionRef
    risk_policy_ref: ExactRevisionRef
    action_budget_policy_ref: ExactRevisionRef
    kill_policy_ref: ExactRevisionRef
    dry_validation_receipt_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _external_ref_types(self) -> "ExternalActionPreviewBinding":
        expected = {
            "action_type_ref": "ActionTypeRevision",
            "capability_ref": "CapabilityRevision",
            "capability_binding_ref": "CapabilityBindingRevision",
            "account_ref": "AccountBindingRevision",
            "adapter_capability_ref": "AdapterCapabilityRevision",
            "risk_policy_ref": "RiskPolicyRevision",
            "action_budget_policy_ref": "ActionBudgetPolicyRevision",
            "kill_policy_ref": "KillPolicyRevision",
            "dry_validation_receipt_ref": "DryValidationReceiptRevision",
        }
        for field_name, resource_type in expected.items():
            if getattr(self, field_name).resource_type != resource_type:
                raise ValueError(f"{field_name} must reference {resource_type}")
        return self


class ActionProposalExactRef(AipContractModel):
    proposal_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ImpactDimension(AipContractModel):
    quality: ImpactQuality
    value: Any | None = None
    source_refs: list[ResourceRef] = Field(default_factory=list)
    cutoff_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _quality_matches_evidence(self) -> ImpactDimension:
        if self.quality is ImpactQuality.UNKNOWN:
            if self.value is not None:
                raise ValueError("unknown impact dimension cannot carry a value")
            return self
        if self.value is None:
            raise ValueError("measured or estimated impact dimension requires a value")
        if not self.source_refs:
            raise ValueError("measured or estimated impact dimension requires sourceRefs")
        if self.cutoff_at is None or self.cutoff_at.tzinfo is None:
            raise ValueError("measured or estimated impact dimension requires an aware cutoffAt")
        return self


class ImpactAssessment(AipContractModel):
    object_scope: ImpactDimension
    channel_scope: ImpactDimension
    cost: ImpactDimension
    budget: ImpactDimension
    risks: ImpactDimension
    reversibility: ImpactDimension
    approval_chain: ImpactDimension
    rate_capacity_kill: ImpactDimension


class CreateImpactPreviewRequest(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    plan_ref: ExactRevisionRef
    production_context_ref: ExactRevisionRef | None = None
    brief_ref: ExactRevisionRef
    evidence_bundle_ref: ExactRevisionRef
    eval_contract_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    stage_template_ref: ExactRevisionRef
    model_route_ref: ExactRevisionRef | None = None
    runtime_policy_ref: ExactRevisionRef | None = None
    binding_refs: list[MutableAuthorityRef] = Field(default_factory=list, max_length=256)
    capability_ref: ExactRevisionRef | None = None
    account_ref: MutableAuthorityRef | None = None
    external_action_binding: ExternalActionPreviewBinding | None = None
    impact: ImpactAssessment
    expires_at: datetime

    @model_validator(mode="after")
    def _exact_dependency_kinds(self) -> CreateImpactPreviewRequest:
        expected = (
            (self.plan_ref, "PlanRevision", "planRef"),
            (self.brief_ref, "TaskBriefRevision", "briefRef"),
            (self.evidence_bundle_ref, "EvidenceBundleRevision", "evidenceBundleRef"),
            (self.eval_contract_ref, "EvalContractRevision", "evalContractRef"),
            (
                self.responsibility_plan_ref,
                "ResponsibilityPlanRevision",
                "responsibilityPlanRef",
            ),
            (self.stage_template_ref, "StageTemplateRevision", "stageTemplateRef"),
        )
        for ref, resource_type, label in expected:
            if ref.resource_type != resource_type:
                raise ValueError(f"{label} must reference {resource_type}")
        if (
            self.production_context_ref is not None
            and self.production_context_ref.resource_type != "ProductionContextRevision"
        ):
            raise ValueError(
                "productionContextRef must reference ProductionContextRevision"
            )
        if (self.model_route_ref is None) is not (self.runtime_policy_ref is None):
            raise ValueError("modelRouteRef and runtimePolicyRef must be supplied together")
        if self.model_route_ref and self.model_route_ref.resource_type != "ModelRouteRevision":
            raise ValueError("modelRouteRef must reference ModelRouteRevision")
        if self.runtime_policy_ref and self.runtime_policy_ref.resource_type != "RuntimePolicyRevision":
            raise ValueError("runtimePolicyRef must reference RuntimePolicyRevision")
        if self.capability_ref and self.capability_ref.resource_type != "CapabilityRevision":
            raise ValueError("capabilityRef must reference CapabilityRevision")
        allowed_bindings = {"AgentInstance", "SkillBinding", "CapabilityBinding"}
        if any(ref.resource_type not in allowed_bindings for ref in self.binding_refs):
            raise ValueError("bindingRefs must reference AgentInstance, SkillBinding or CapabilityBinding")
        binding_keys = [
            (ref.resource_type, ref.resource_id, ref.version) for ref in self.binding_refs
        ]
        if len(binding_keys) != len(set(binding_keys)):
            raise ValueError("bindingRefs must be unique")
        if self.account_ref and self.account_ref.resource_type not in {
            "AccountBinding",
            "ChannelAccountBinding",
            "ShopAccountBinding",
        }:
            raise ValueError("accountRef must reference a controlled account binding")
        if self.external_action_binding is not None:
            external = self.external_action_binding
            if self.capability_ref != external.capability_ref:
                raise ValueError("externalActionBinding capabilityRef must match preview capabilityRef")
            if self.account_ref is None:
                raise ValueError("externalActionBinding requires preview accountRef")
            if (
                self.account_ref.resource_id != external.account_ref.resource_id
                or self.account_ref.version != external.account_ref.revision
            ):
                raise ValueError("externalActionBinding accountRef must match preview accountRef")
            if not any(
                ref.resource_type == "CapabilityBinding"
                and ref.resource_id == external.capability_binding_ref.resource_id
                and ref.version == external.capability_binding_ref.revision
                for ref in self.binding_refs
            ):
                raise ValueError(
                    "externalActionBinding capabilityBindingRef must match preview bindingRefs"
                )
        if self.expires_at.tzinfo is None:
            raise ValueError("expiresAt must include timezone information")
        return self


class ReviseImpactPreviewRequest(CreateImpactPreviewRequest):
    expected_version: int = Field(ge=1)


class ImpactPreviewRevision(CreateImpactPreviewRequest):
    tenant: TenantContext
    preview_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    dependency_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    action_binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle: BriefLifecycle
    readiness: ContractReadiness
    blockers: list[ContractBlocker]
    frozen_by: str | None = None
    frozen_at: datetime | None = None
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @model_validator(mode="after")
    def _frozen_revision_has_actor_and_time(self) -> ImpactPreviewRevision:
        if (self.frozen_by is None) is not (self.frozen_at is None):
            raise ValueError("frozenBy and frozenAt must be supplied together")
        frozen = self.frozen_by is not None
        if (self.lifecycle is BriefLifecycle.FROZEN) is not frozen:
            raise ValueError("only frozen ImpactPreview revisions carry frozenBy and frozenAt")
        if self.frozen_at is not None and self.frozen_at.tzinfo is None:
            raise ValueError("frozenAt must include timezone information")
        if self.readiness is ContractReadiness.READY:
            if self.blockers:
                raise ValueError("ready ImpactPreview revision cannot carry blockers")
        elif not self.blockers:
            raise ValueError("non-ready ImpactPreview revision requires blockers")
        return self


class ImpactPreviewListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ImpactPreviewRevision]
    count: int = Field(ge=0)


class ProductionStartRequest(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    expected_task_version: int = Field(ge=1)
    production_context_ref: ExactRevisionRef
    plan_ref: ExactRevisionRef
    preview_ref: ExactRevisionRef
    action_proposal_ref: ActionProposalExactRef
    logic_graph_id: str = Field(min_length=1, max_length=200)
    logic_revision: int = Field(ge=1)
    logic_graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _start_ref_kinds(self) -> ProductionStartRequest:
        if self.production_context_ref.resource_type != "ProductionContextRevision":
            raise ValueError("productionContextRef must reference ProductionContextRevision")
        if self.plan_ref.resource_type != "PlanRevision":
            raise ValueError("planRef must reference PlanRevision")
        if self.preview_ref.resource_type != "ImpactPreviewRevision":
            raise ValueError("previewRef must reference ImpactPreviewRevision")
        return self


class ProductionStartDecision(AipContractModel):
    tenant: TenantContext
    decision_id: str = Field(min_length=1, max_length=200)
    status: ProductionStartDecisionStatus
    task_id: str = Field(min_length=1, max_length=200)
    production_context_ref: ExactRevisionRef | None = None
    plan_ref: ExactRevisionRef
    preview_ref: ExactRevisionRef
    action_proposal_ref: ActionProposalExactRef
    dependency_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    blockers: list[ContractBlocker]
    task_run_ref: ResourceRef | None = None
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @model_validator(mode="after")
    def _decision_outcome_is_unambiguous(self) -> ProductionStartDecision:
        if self.status is ProductionStartDecisionStatus.STARTED:
            if self.blockers or self.task_run_ref is None:
                raise ValueError("started decision requires taskRunRef and no blockers")
            if self.task_run_ref.resource_type != "TaskRun":
                raise ValueError("taskRunRef must reference TaskRun")
            return self
        if not self.blockers or self.task_run_ref is not None:
            raise ValueError("non-started decision requires blockers and cannot carry taskRunRef")
        return self


class ProductionStartDecisionListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ProductionStartDecision]
    count: int = Field(ge=0)


class FreezeProductionContextRequest(AipContractModel):
    task_id: str = Field(min_length=1, max_length=200)
    brief_ref: ExactRevisionRef
    evidence_bundle_ref: ExactRevisionRef
    eval_contract_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    production_profile_ref: ExactRevisionRef | None = None
    profile: str = Field(default="default", min_length=1, max_length=120)
    preparation_ref: ExactRevisionRef | None = None

    @model_validator(mode="after")
    def _four_contract_kinds(self) -> FreezeProductionContextRequest:
        expected = {
            "brief_ref": "TaskBriefRevision",
            "evidence_bundle_ref": "EvidenceBundleRevision",
            "eval_contract_ref": "EvalContractRevision",
            "responsibility_plan_ref": "ResponsibilityPlanRevision",
        }
        for field, kind in expected.items():
            ref = getattr(self, field)
            if ref.resource_type != kind:
                raise ValueError(f"{field} must reference {kind}")
        if (
            self.preparation_ref is not None
            and self.preparation_ref.resource_type != "PreparationReceipt"
        ):
            raise ValueError("preparationRef must reference PreparationReceipt")
        if (
            self.production_profile_ref is not None
            and self.production_profile_ref.resource_type != "ProductionProfileRevision"
        ):
            raise ValueError(
                "productionProfileRef must reference ProductionProfileRevision"
            )
        return self


class ProductionContextRevision(AipContractModel):
    tenant: TenantContext
    context_id: str
    revision: int
    task_id: str
    brief_ref: ExactRevisionRef
    evidence_bundle_ref: ExactRevisionRef
    eval_contract_ref: ExactRevisionRef
    responsibility_plan_ref: ExactRevisionRef
    production_profile_ref: ExactRevisionRef | None = None
    preparation_ref: ExactRevisionRef | None
    profile: str
    dependency_snapshot: list[dict[str, Any]]
    dependency_snapshot_hash: str
    content_hash: str
    lifecycle: BriefLifecycle
    readiness: ContractReadiness
    blockers: list[ContractBlocker]
    created_by: str
    created_at: datetime


class ProductionContextListResponse(AipContractModel):
    tenant: TenantContext
    items: list[ProductionContextRevision]
    count: int = Field(ge=0)


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
    """Legacy create surface — W-L9: coverage fields forbidden; use BuildEvidenceBundleRequest."""

    brief_ref: ExactRevisionRef
    subject_refs: list[ResourceRef] = Field(default_factory=list)
    cutoff_at: datetime
    item_refs: list[ExactRevisionRef] = Field(min_length=1)
    required_fact_ids: list[str] = Field(min_length=1)
    marking: list[str] = Field(default_factory=list)
    license_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("required_fact_ids", "marking")
    @classmethod
    def _nonblank_unique(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("values must be non-blank")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("values must be unique")
        return cleaned


class BuildEvidenceBundleRequest(CreateEvidenceBundleRequest):
    """W-L9 canonical EvidenceBundle Build Job input (server-owned coverage)."""


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
    revoked: bool = False
    revoke_reason: str | None = None


class EvidenceBundleListResponse(AipContractModel):
    tenant: TenantContext
    items: list[EvidenceBundleRevision]
    count: int = Field(ge=0)


class RevokeEvidenceBundleRequest(AipContractModel):
    expected_revision: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=500)


class RevokeEvidenceRequest(AipContractModel):
    expected_revision: int = Field(default=1, ge=1, le=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=500)


class EvidenceRevocation(AipContractModel):
    tenant: TenantContext
    event_id: str
    evidence_ref: ExactRevisionRef
    reason: str
    actor: str
    occurred_at: datetime


class ResolveEvidenceDisclosureRequest(AipContractModel):
    evidence_ref: EvidenceExactRevisionRef
    purpose: DisclosurePurpose
    requested_level: DisclosureLevel
    task_id: str | None = Field(default=None, max_length=200)
    subject_ref: ResourceRef | None = None

class EvidenceDisclosureDecision(AipContractModel):
    tenant: TenantContext
    decision_id: str
    evidence_ref: ExactRevisionRef
    purpose: str
    requested_level: DisclosureLevel
    granted_level: DisclosureLevel | None
    status: DisclosureStatus
    reasons: list[str]
    citation: dict[str, Any]
    display_payload: dict[str, Any]
    redaction_receipt: dict[str, Any]
    decision_hash: str
    expires_at: datetime | None
    created_by: str
    created_at: datetime
