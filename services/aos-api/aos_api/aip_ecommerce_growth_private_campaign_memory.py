"""Fail-closed G3/G4 private-domain campaign and governed-memory composition.

This SolutionPack module only compiles review drafts from exact authorities. It
does not resolve contact details, send messages, assign experiments, change
budget/price/inventory, write memory or call a Provider/Tool/Action.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_ecommerce_growth_core_agents import (
    CustomerLiteReadProjection,
    SourceReadinessGateSnapshot,
    SourceReadinessStatus,
)
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef


PRIVATE_LOGIC_IDS = tuple(f"P{i:02d}" for i in range(1, 6))
CAMPAIGN_LOGIC_IDS = tuple(f"A{i:02d}" for i in range(1, 7))
PRIVATE_CAMPAIGN_LOGIC_IDS = PRIVATE_LOGIC_IDS + CAMPAIGN_LOGIC_IDS

_UNSAFE_TEXT = re.compile(
    r"(?:\b1[3-9]\d{9}\b|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"(?:openid|open_id|mobile|phone|address|身份证|手机号|收货地址|api[_ -]?key|secret)\s*[:=：]?|"
    r"ignore\s+(?:all\s+)?previous|reveal\s+(?:the\s+)?system\s+prompt|"
    r"jailbreak|忽略(?:以上|之前)|泄露系统提示词)",
    re.IGNORECASE,
)


def _exact(value: ExactRevisionRef, kind: str, label: str) -> None:
    if value.resource_type != kind:
        raise ValueError(f"{label} must reference {kind}")


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _digest(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()


class ContactDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    UNKNOWN = "unknown"


class ExperimentState(StrEnum):
    FROZEN = "frozen"
    DRAFT = "draft"
    CHANGED = "changed"


class ContaminationState(StrEnum):
    CLEAN = "clean"
    CONTAMINATED = "contaminated"
    UNKNOWN = "unknown"


class AttributionState(StrEnum):
    OBSERVED = "observed"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class MemoryLayer(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class MemoryScope(StrEnum):
    AGENT_PRIVATE = "agent_private"
    TEAM_SHARED = "team_shared"


class G3G4State(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"


class LogicStage(AipContractModel):
    order: int = Field(ge=1, le=11)
    logic_id: str = Field(pattern=r"^(?:P0[1-5]|A0[1-6])$")
    logic_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _canonical(self) -> "LogicStage":
        _exact(self.logic_ref, "LogicGraphRevision", "logicRef")
        if self.logic_ref.resource_id != f"ecommerce.logic.{self.logic_id}":
            raise ValueError("logicRef must bind canonical ecommerce Logic ID")
        return self


class ContactPolicyGateSnapshot(AipContractModel):
    policy_ref: ExactRevisionRef
    consent_ref: ExactRevisionRef
    purpose: Literal["marketing"]
    channel: Literal["wechat", "sms", "email", "platform_message"]
    consent: ContactDecision
    channel_allowed: ContactDecision
    opt_out: ContactDecision
    suppression: ContactDecision
    quiet_hours: ContactDecision
    frequency_cap: ContactDecision
    cooldown: ContactDecision
    checked_at: datetime
    fresh_until: datetime

    @model_validator(mode="after")
    def _gate(self) -> "ContactPolicyGateSnapshot":
        _exact(self.policy_ref, "ContactPolicyRevision", "policyRef")
        _exact(self.consent_ref, "ConsentEventRevision", "consentRef")
        _aware(self.checked_at, "checkedAt")
        _aware(self.fresh_until, "freshUntil")
        if self.fresh_until <= self.checked_at:
            raise ValueError("freshUntil must follow checkedAt")
        return self


class CampaignGuardrailSnapshot(AipContractModel):
    campaign_plan_ref: ExactRevisionRef
    budget_ref: ExactRevisionRef
    cost_ref: ExactRevisionRef
    price_ref: ExactRevisionRef
    inventory_ref: ExactRevisionRef
    fulfillment_ref: ExactRevisionRef
    capacity_ref: ExactRevisionRef
    budget_limit: float = Field(ge=0)
    budget_requested: float = Field(ge=0)
    margin_floor_rate: float = Field(ge=-1, le=1)
    projected_margin_rate: float = Field(ge=-1, le=1)
    price_ready: ContactDecision
    inventory_ready: ContactDecision
    fulfillment_ready: ContactDecision
    capacity_ready: ContactDecision
    cutoff_at: datetime
    fresh_until: datetime

    @model_validator(mode="after")
    def _refs(self) -> "CampaignGuardrailSnapshot":
        for value, kind, label in (
            (self.campaign_plan_ref, "CampaignPlanRevision", "campaignPlanRef"),
            (self.budget_ref, "BudgetEnvelopeRevision", "budgetRef"),
            (self.cost_ref, "CostSnapshotRevision", "costRef"),
            (self.price_ref, "PriceSnapshotRevision", "priceRef"),
            (self.inventory_ref, "InventorySnapshotRevision", "inventoryRef"),
            (self.fulfillment_ref, "FulfillmentSnapshotRevision", "fulfillmentRef"),
            (self.capacity_ref, "CapacitySnapshotRevision", "capacityRef"),
        ):
            _exact(value, kind, label)
        _aware(self.cutoff_at, "cutoffAt")
        _aware(self.fresh_until, "freshUntil")
        if self.fresh_until <= self.cutoff_at:
            raise ValueError("freshUntil must follow cutoffAt")
        return self


class ExperimentGateSnapshot(AipContractModel):
    experiment_ref: ExactRevisionRef
    hypothesis_ref: ExactRevisionRef
    assignment_ref: ExactRevisionRef
    metric_definition_ref: ExactRevisionRef
    window_ref: ExactRevisionRef
    stop_policy_ref: ExactRevisionRef
    state: ExperimentState
    contamination: ContaminationState
    sample_size: int = Field(ge=0)
    minimum_sample_size: int = Field(ge=1)
    confidence_score: float = Field(ge=0, le=1)
    minimum_confidence_score: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _refs(self) -> "ExperimentGateSnapshot":
        for value, kind, label in (
            (self.experiment_ref, "ExperimentRevision", "experimentRef"),
            (self.hypothesis_ref, "ExperimentHypothesisRevision", "hypothesisRef"),
            (self.assignment_ref, "ExperimentAssignmentRevision", "assignmentRef"),
            (self.metric_definition_ref, "MetricDefinitionRevision", "metricDefinitionRef"),
            (self.window_ref, "ExperimentWindowRevision", "windowRef"),
            (self.stop_policy_ref, "StopPolicyRevision", "stopPolicyRef"),
        ):
            _exact(value, kind, label)
        return self


class AttributionGateSnapshot(AipContractModel):
    effect_review_ref: ExactRevisionRef
    reconciliation_ref: ExactRevisionRef
    state: AttributionState
    uncertainty_summary: str = Field(min_length=1, max_length=600)
    cutoff_at: datetime

    @field_validator("uncertainty_summary")
    @classmethod
    def _safe_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if _UNSAFE_TEXT.search(cleaned):
            raise ValueError("uncertainty summary contains unsafe content")
        return cleaned

    @model_validator(mode="after")
    def _refs(self) -> "AttributionGateSnapshot":
        _exact(self.effect_review_ref, "EffectReviewRevision", "effectReviewRef")
        _exact(self.reconciliation_ref, "ReconciliationRevision", "reconciliationRef")
        _aware(self.cutoff_at, "cutoffAt")
        return self


class MemoryCandidatePolicySnapshot(AipContractModel):
    task_ref: ExactRevisionRef
    artifact_ref: ExactRevisionRef
    outcome_ref: ExactRevisionRef
    evidence_ref: ExactRevisionRef
    eval_ref: ExactRevisionRef
    governance_policy_ref: ExactRevisionRef
    layer: MemoryLayer
    scope: MemoryScope = MemoryScope.AGENT_PRIVATE
    recipients: list[str] = Field(default_factory=list, max_length=12)
    purpose: str = Field(min_length=1, max_length=160)
    markings: list[str] = Field(min_length=1, max_length=16)
    sharing_approval_ref: ExactRevisionRef | None = None
    pii_clear: bool
    secret_clear: bool
    counterexamples: list[str] = Field(min_length=1, max_length=12)
    applicability: list[str] = Field(min_length=1, max_length=24)

    @field_validator("purpose")
    @classmethod
    def _safe_purpose(cls, value: str) -> str:
        cleaned = value.strip()
        if _UNSAFE_TEXT.search(cleaned):
            raise ValueError("memory purpose contains unsafe content")
        return cleaned

    @field_validator("recipients", "markings", "counterexamples", "applicability")
    @classmethod
    def _unique_non_blank(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("memory lists must contain unique non-blank values")
        return cleaned

    @model_validator(mode="after")
    def _refs(self) -> "MemoryCandidatePolicySnapshot":
        for value, kind, label in (
            (self.task_ref, "TaskRevision", "taskRef"),
            (self.artifact_ref, "ArtifactRevision", "artifactRef"),
            (self.outcome_ref, "OutcomeRevision", "outcomeRef"),
            (self.evidence_ref, "EvidenceRevision", "evidenceRef"),
            (self.eval_ref, "EvalReportRevision", "evalRef"),
            (self.governance_policy_ref, "MemoryGovernancePolicyRevision", "governancePolicyRef"),
        ):
            _exact(value, kind, label)
        if self.scope is MemoryScope.TEAM_SHARED:
            if not self.recipients or self.sharing_approval_ref is None:
                raise ValueError("team_shared memory requires recipients and approval")
            _exact(self.sharing_approval_ref, "MemorySharingApprovalRevision", "sharingApprovalRef")
        elif self.recipients or self.sharing_approval_ref is not None:
            raise ValueError("agent_private memory cannot carry sharing configuration")
        return self


class PrivateCampaignMemoryInput(AipContractModel):
    source_readiness: SourceReadinessGateSnapshot
    customer: CustomerLiteReadProjection
    contact_policy: ContactPolicyGateSnapshot
    campaign: CampaignGuardrailSnapshot
    experiment: ExperimentGateSnapshot
    attribution: AttributionGateSnapshot
    memory: MemoryCandidatePolicySnapshot
    logic_stages: list[LogicStage] = Field(min_length=11, max_length=11)
    aggregate_summary: str = Field(min_length=1, max_length=1000)
    requested_at: datetime

    @field_validator("aggregate_summary")
    @classmethod
    def _safe_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if _UNSAFE_TEXT.search(cleaned):
            raise ValueError("aggregate summary contains unsafe or identifying content")
        return cleaned

    @model_validator(mode="after")
    def _composition(self) -> "PrivateCampaignMemoryInput":
        actual = [(item.order, item.logic_id) for item in self.logic_stages]
        expected = list(enumerate(PRIVATE_CAMPAIGN_LOGIC_IDS, start=1))
        if actual != expected:
            raise ValueError("logicStages must contain ordered P01-P05 and A01-A06")
        _aware(self.requested_at, "requestedAt")
        return self


class SegmentDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    customer_projection_ref: ExactRevisionRef
    segment_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    direct_identifier_included: Literal[False] = False


class TouchPlanDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    contact_policy_ref: ExactRevisionRef
    consent_ref: ExactRevisionRef
    channel: str
    contact_resolution_authorized: Literal[False] = False
    external_send_authorized: Literal[False] = False


class CampaignExperimentDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    campaign_plan_ref: ExactRevisionRef
    experiment_ref: ExactRevisionRef
    assignment_ref: ExactRevisionRef
    attribution_state: AttributionState
    uncertainty_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    production_assignment_authorized: Literal[False] = False
    budget_write_authorized: Literal[False] = False


class MemoryCandidateDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    layer: MemoryLayer
    scope: MemoryScope
    source_refs: list[ExactRevisionRef] = Field(min_length=5, max_length=5)
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    recipients: list[str] = Field(default_factory=list, max_length=12)
    auto_submit_authorized: Literal[False] = False
    auto_promote_authorized: Literal[False] = False
    memory_write_authorized: Literal[False] = False


class ProceduralWikiProposalDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    source_memory_candidate_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    target: Literal["versioned_wiki_playbook"] = "versioned_wiki_playbook"
    wiki_write_authorized: Literal[False] = False


class G3G4Compilation(AipContractModel):
    tenant: TenantContext
    state: G3G4State
    blockers: list[ContractBlocker]
    segment_draft: SegmentDraft | None = None
    touch_plan_draft: TouchPlanDraft | None = None
    campaign_experiment_draft: CampaignExperimentDraft | None = None
    memory_candidate_draft: MemoryCandidateDraft | None = None
    procedural_wiki_proposal_draft: ProceduralWikiProposalDraft | None = None
    external_action_authorized: Literal[False] = False
    memory_write_authorized: Literal[False] = False
    production_written: Literal[False] = False

    @model_validator(mode="after")
    def _honest(self) -> "G3G4Compilation":
        drafts = (
            self.segment_draft,
            self.touch_plan_draft,
            self.campaign_experiment_draft,
            self.memory_candidate_draft,
            self.procedural_wiki_proposal_draft,
        )
        if self.state is G3G4State.READY_FOR_REVIEW:
            if self.blockers or any(item is None for item in drafts):
                raise ValueError("ready compilation requires all drafts and no blockers")
        elif any(item is not None for item in drafts):
            raise ValueError("blocked compilation cannot contain drafts")
        return self


def _block(code: str, message: str, ref: ExactRevisionRef | None = None) -> ContractBlocker:
    return ContractBlocker(code=code, message=message, resource_ref=ref)


def _blockers(value: PrivateCampaignMemoryInput) -> list[ContractBlocker]:
    blockers: list[ContractBlocker] = []
    if value.source_readiness.status is not SourceReadinessStatus.READY:
        blockers.append(_block("G3G4_SOURCE_READINESS_NOT_READY", "SourceReadiness is not 12/12 READY", value.source_readiness.evidence_pack_ref))
    if value.source_readiness.fresh_until <= value.requested_at:
        blockers.append(_block("G3G4_SOURCE_READINESS_STALE", "SourceReadiness evidence is stale", value.source_readiness.evidence_pack_ref))
    if value.customer.fresh_until <= value.requested_at:
        blockers.append(_block("G3G4_CUSTOMER_STALE", "CustomerLite projection is stale", value.customer.projection_ref))
    if value.customer.deletion_state.value != "active":
        blockers.append(_block("G3G4_CUSTOMER_NOT_ACTIVE", "CustomerLite is deleted, invalidated or pending deletion", value.customer.projection_ref))
    customer_marketing_consents = [
        item
        for item in value.customer.consents
        if item.purpose.value == "marketing" and item.status.value == "granted"
    ]
    if not customer_marketing_consents:
        blockers.append(_block("G3G4_CUSTOMER_MARKETING_CONSENT_MISSING", "CustomerLite has no granted marketing consent", value.customer.projection_ref))
    elif not any(
        value.contact_policy.consent_ref == item.consent_ref
        for item in customer_marketing_consents
    ):
        blockers.append(_block("G3G4_CONSENT_REF_MISMATCH", "ContactPolicy consent does not match CustomerLite", value.contact_policy.consent_ref))
    if value.contact_policy.fresh_until <= value.requested_at:
        blockers.append(_block("G3G4_CONTACT_POLICY_STALE", "ContactPolicy decision is stale", value.contact_policy.policy_ref))
    checks = (
        (value.contact_policy.consent, ContactDecision.ALLOW, "CONSENT_NOT_GRANTED"),
        (value.contact_policy.channel_allowed, ContactDecision.ALLOW, "CHANNEL_NOT_ALLOWED"),
        (value.contact_policy.opt_out, ContactDecision.BLOCK, "OPT_OUT_OR_UNKNOWN"),
        (value.contact_policy.suppression, ContactDecision.BLOCK, "SUPPRESSED_OR_UNKNOWN"),
        (value.contact_policy.quiet_hours, ContactDecision.BLOCK, "QUIET_HOURS_OR_UNKNOWN"),
        (value.contact_policy.frequency_cap, ContactDecision.ALLOW, "FREQUENCY_CAP_BLOCKED"),
        (value.contact_policy.cooldown, ContactDecision.ALLOW, "COOLDOWN_BLOCKED"),
    )
    for actual, expected, suffix in checks:
        if actual is not expected:
            blockers.append(_block(f"G3G4_{suffix}", "contact eligibility gate failed closed", value.contact_policy.policy_ref))
    if value.campaign.fresh_until <= value.requested_at:
        blockers.append(_block("G3G4_CAMPAIGN_FACTS_STALE", "campaign facts are stale", value.campaign.campaign_plan_ref))
    if value.campaign.cutoff_at != value.source_readiness.cutoff_at or value.attribution.cutoff_at != value.source_readiness.cutoff_at:
        blockers.append(_block("G3G4_CUTOFF_MISMATCH", "campaign and attribution must share SourceReadiness cutoff", value.source_readiness.evidence_pack_ref))
    if value.campaign.budget_requested > value.campaign.budget_limit:
        blockers.append(_block("G3G4_BUDGET_EXCEEDED", "requested budget exceeds approved envelope", value.campaign.budget_ref))
    if value.campaign.projected_margin_rate < value.campaign.margin_floor_rate:
        blockers.append(_block("G3G4_MARGIN_BELOW_FLOOR", "projected margin is below approved floor", value.campaign.cost_ref))
    for decision, suffix, ref in (
        (value.campaign.price_ready, "PRICE_NOT_READY", value.campaign.price_ref),
        (value.campaign.inventory_ready, "INVENTORY_NOT_READY", value.campaign.inventory_ref),
        (value.campaign.fulfillment_ready, "FULFILLMENT_NOT_READY", value.campaign.fulfillment_ref),
        (value.campaign.capacity_ready, "CAPACITY_NOT_READY", value.campaign.capacity_ref),
    ):
        if decision is not ContactDecision.ALLOW:
            blockers.append(_block(f"G3G4_{suffix}", "campaign guardrail is blocked or unknown", ref))
    if value.experiment.state is not ExperimentState.FROZEN:
        blockers.append(_block("G3G4_EXPERIMENT_NOT_FROZEN", "experiment contract is not frozen", value.experiment.experiment_ref))
    if value.experiment.contamination is not ContaminationState.CLEAN:
        blockers.append(_block("G3G4_EXPERIMENT_CONTAMINATED", "experiment contamination is not clean", value.experiment.assignment_ref))
    if value.experiment.sample_size < value.experiment.minimum_sample_size:
        blockers.append(_block("G3G4_SAMPLE_INSUFFICIENT", "experiment sample size is insufficient", value.experiment.experiment_ref))
    if value.experiment.confidence_score < value.experiment.minimum_confidence_score:
        blockers.append(_block("G3G4_CONFIDENCE_INSUFFICIENT", "experiment confidence is insufficient", value.experiment.experiment_ref))
    if value.attribution.state is AttributionState.UNKNOWN:
        blockers.append(_block("G3G4_ATTRIBUTION_UNKNOWN", "unknown attribution cannot support a memory candidate", value.attribution.effect_review_ref))
    if not value.memory.pii_clear or not value.memory.secret_clear:
        blockers.append(_block("G3G4_MEMORY_GOVERNANCE_NOT_CLEAR", "memory candidate failed PII or Secret inspection", value.memory.evidence_ref))
    if "PII_MINIMIZED" not in value.memory.markings:
        blockers.append(_block("G3G4_MEMORY_MARKING_MISSING", "memory candidate requires PII_MINIMIZED marking", value.memory.evidence_ref))
    return blockers


def compile_private_campaign_memory(
    tenant: TenantContext,
    value: PrivateCampaignMemoryInput,
) -> G3G4Compilation:
    """Compile review-only G3/G4 drafts with no external or persistent effects."""

    blockers = _blockers(value)
    if blockers:
        return G3G4Compilation(tenant=tenant, state=G3G4State.BLOCKED, blockers=blockers)
    segment_digest = _digest(value.customer.projection_ref.content_hash, value.aggregate_summary)
    memory_digest = _digest(
        value.memory.artifact_ref.content_hash,
        value.memory.outcome_ref.content_hash,
        value.memory.evidence_ref.content_hash,
        value.attribution.effect_review_ref.content_hash,
    )
    return G3G4Compilation(
        tenant=tenant,
        state=G3G4State.READY_FOR_REVIEW,
        blockers=[],
        segment_draft=SegmentDraft(
            customer_projection_ref=value.customer.projection_ref,
            segment_digest=segment_digest,
        ),
        touch_plan_draft=TouchPlanDraft(
            contact_policy_ref=value.contact_policy.policy_ref,
            consent_ref=value.contact_policy.consent_ref,
            channel=value.contact_policy.channel,
        ),
        campaign_experiment_draft=CampaignExperimentDraft(
            campaign_plan_ref=value.campaign.campaign_plan_ref,
            experiment_ref=value.experiment.experiment_ref,
            assignment_ref=value.experiment.assignment_ref,
            attribution_state=value.attribution.state,
            uncertainty_hash=_digest(value.attribution.uncertainty_summary),
        ),
        memory_candidate_draft=MemoryCandidateDraft(
            layer=value.memory.layer,
            scope=value.memory.scope,
            source_refs=[
                value.memory.task_ref,
                value.memory.artifact_ref,
                value.memory.outcome_ref,
                value.memory.evidence_ref,
                value.memory.eval_ref,
            ],
            payload_digest=memory_digest,
            recipients=value.memory.recipients,
        ),
        procedural_wiki_proposal_draft=ProceduralWikiProposalDraft(
            source_memory_candidate_digest=memory_digest,
        ),
    )


__all__ = [
    "AttributionGateSnapshot",
    "CampaignGuardrailSnapshot",
    "ContactPolicyGateSnapshot",
    "ExperimentGateSnapshot",
    "G3G4Compilation",
    "G3G4State",
    "LogicStage",
    "MemoryCandidatePolicySnapshot",
    "PrivateCampaignMemoryInput",
    "PRIVATE_CAMPAIGN_LOGIC_IDS",
    "compile_private_campaign_memory",
]
