"""Fail-closed SC07-SC09 ecommerce scenario acceptance compiler.

Only exact references and guard snapshots are composed into review drafts.
No outreach, signature, fulfilment, price action, complaint response, refund,
Pipeline retry, Provider call, memory write or production write is performed.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_ecommerce_growth_core_agents import SourceReadinessGateSnapshot, SourceReadinessStatus
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef


SCENARIO_LOGICS: dict[str, tuple[str, ...]] = {
    "SC07": ("D02", "D03", *(f"G{i:02d}" for i in range(1, 7)), *(f"C{i:02d}" for i in range(1, 7)), *(f"A{i:02d}" for i in range(1, 7)), "S01", "S02", "P01"),
    "SC08": ("D01", "D03", "G01", "G02", "A01", "A03", "C06", "S01", "P03"),
    "SC09": (*(f"S{i:02d}" for i in range(1, 7)), "G02", "P01", "P02", "D01"),
}

SCENARIO_CHAINS: dict[str, tuple[str, ...]] = {
    "SC07": ("CreatorRecruitmentPlanRevision", "CreatorCandidateBatchRevision", "CreatorOutreachDraftRevision", "CreatorCommercialOfferRevision", "CreatorContractRevision", "CreatorFulfillmentRevision", "CreatorPerformanceReviewRevision", "CreatorRelationshipPlanRevision"),
    "SC08": ("PriceMonitoringPolicyRevision", "ProductComparableDecisionRevision", "PriceObservationEvidenceRevision", "PriceObservationEvidenceRevision", "PriceNormalizationRevision", "PriceAnomalyCandidateRevision", "CompetitorBenchmarkRevision", "PriceActionDraftRevision"),
    "SC09": ("ServiceCaseRevision", "IdentityVerificationRevision", "ComplaintClassificationRevision", "ServiceReplyDraftRevision", "EscalationDecisionRevision", "PromiseBoundaryRevision", "ResolutionReceiptRevision", "EffectReviewRevision"),
}


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _exact(value: ExactRevisionRef, kind: str, label: str) -> None:
    if value.resource_type != kind:
        raise ValueError(f"{label} must reference {kind}")


def _block(code: str, message: str, ref: ExactRevisionRef | None = None) -> ContractBlocker:
    return ContractBlocker(code=code, message=message, resource_ref=ref)


def _digest(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()


class PriceTaskType(StrEnum):
    EXACT_PRODUCT_GOVERNANCE = "exact_product_governance"
    CATEGORY_COMPETITOR_BENCHMARK = "category_competitor_benchmark"


class ProductRelation(StrEnum):
    EXACT_SKU = "exact_sku"
    SAME_PRODUCT_VARIANT = "same_product_variant"
    LIKELY_SAME = "likely_same"
    CATEGORY_COMPETITOR = "category_competitor"
    UNRELATED = "unrelated"


class R30ScenarioState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"


class CreatorLifecycleGuard(AipContractModel):
    candidate_count: int = Field(ge=0)
    unique_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    suppressed_count: int = Field(ge=0)
    expired_contact_count: int = Field(ge=0)
    authorized_channel: bool
    outreach_sent: bool
    contract_signed_claimed: bool
    signature_receipt_present: bool
    fulfillment_claimed: bool
    fulfillment_receipt_present: bool
    performance_final: bool
    observation_window_closed: bool
    relationship_contact_allowed: bool


class PriceGovernanceGuard(AipContractModel):
    task_type: PriceTaskType
    product_relation: ProductRelation
    governance_basis_present: bool
    observation_count: int = Field(ge=0)
    independent_source_count: int = Field(ge=0)
    observation_contexts_aligned: bool
    legal_conclusion_present: bool
    external_action_executed: bool
    price_changed: bool
    malicious_order_or_refund: bool


class ComplaintCaseGuard(AipContractModel):
    identity_min_verified: bool
    pii_tokenized: bool
    classification_confidence: float = Field(ge=0, le=1)
    escalation_required: bool
    escalated: bool
    promise_within_authority: bool
    external_reply_sent: bool
    refund_executed: bool
    resolution_claimed: bool
    resolution_receipt_present: bool
    aggregate_substitution: bool


class R30ScenarioInput(AipContractModel):
    scenario_id: Literal["SC07", "SC08", "SC09"]
    scenario_ref: ExactRevisionRef
    source_readiness: SourceReadinessGateSnapshot
    logic_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=32)
    chain_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=16)
    task_run_ref: ExactRevisionRef
    receipt_ref: ExactRevisionRef
    lineage_ref: ExactRevisionRef
    effect_review_ref: ExactRevisionRef
    observed_cutoff: datetime
    fresh_until: datetime
    creator_guard: CreatorLifecycleGuard | None = None
    price_guard: PriceGovernanceGuard | None = None
    complaint_guard: ComplaintCaseGuard | None = None

    @model_validator(mode="after")
    def _authority(self) -> "R30ScenarioInput":
        for value, kind, label in (
            (self.scenario_ref, "ScenarioRevision", "scenarioRef"),
            (self.task_run_ref, "TaskRunRevision", "taskRunRef"),
            (self.receipt_ref, "ReceiptRevision", "receiptRef"),
            (self.lineage_ref, "LineageRevision", "lineageRef"),
            (self.effect_review_ref, "EffectReviewRevision", "effectReviewRef"),
        ):
            _exact(value, kind, label)
        if self.scenario_ref.resource_id != f"ecommerce.{self.scenario_id}":
            raise ValueError("scenarioRef must match scenarioId")
        for item in self.logic_refs:
            _exact(item, "LogicGraphRevision", "logicRefs")
        _aware(self.observed_cutoff, "observedCutoff")
        _aware(self.fresh_until, "freshUntil")
        guards = {
            "SC07": self.creator_guard,
            "SC08": self.price_guard,
            "SC09": self.complaint_guard,
        }
        if guards[self.scenario_id] is None or sum(item is not None for item in guards.values()) != 1:
            raise ValueError("exactly the guard matching scenarioId is required")
        return self


class R30EvidencePackDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    scenario_id: Literal["SC07", "SC08", "SC09"]
    state: R30ScenarioState
    scenario_ref: ExactRevisionRef
    source_readiness_ref: ExactRevisionRef
    logic_refs: list[ExactRevisionRef]
    chain_refs: list[ExactRevisionRef]
    task_run_ref: ExactRevisionRef
    receipt_ref: ExactRevisionRef
    lineage_ref: ExactRevisionRef
    effect_review_ref: ExactRevisionRef
    replay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    blockers: list[ContractBlocker]
    external_action_authorized: Literal[False] = False
    production_written: Literal[False] = False


class R30Compilation(AipContractModel):
    tenant: TenantContext
    requested_at: datetime
    state: R30ScenarioState
    evidence_packs: list[R30EvidencePackDraft] = Field(min_length=3, max_length=3)
    pipeline_retried: Literal[False] = False
    database_written: Literal[False] = False
    provider_called: Literal[False] = False
    action_executed: Literal[False] = False
    memory_written: Literal[False] = False
    production_written: Literal[False] = False


def _common_blockers(value: R30ScenarioInput, requested_at: datetime) -> list[ContractBlocker]:
    blockers: list[ContractBlocker] = []
    readiness = value.source_readiness
    if readiness.status is not SourceReadinessStatus.READY or readiness.source_count != 12 or readiness.ready_count != 12:
        blockers.append(_block("R30_SOURCE_READINESS_NOT_READY", "SourceReadiness must be current 12/12 READY", readiness.evidence_pack_ref))
    if readiness.fresh_until <= requested_at or value.fresh_until <= requested_at:
        blockers.append(_block("R30_SOURCE_READINESS_STALE", "scenario and SourceReadiness evidence must be fresh", readiness.evidence_pack_ref))
    if value.observed_cutoff != readiness.cutoff_at:
        blockers.append(_block("R30_CUTOFF_MISMATCH", "scenario and SourceReadiness must share the exact cutoff", readiness.evidence_pack_ref))
    expected_logic_ids = tuple(f"ecommerce.logic.{item}" for item in SCENARIO_LOGICS[value.scenario_id])
    if tuple(item.resource_id for item in value.logic_refs) != expected_logic_ids:
        blockers.append(_block("R30_LOGIC_SEQUENCE_INVALID", "scenario requires the exact ordered Logic set", value.scenario_ref))
    if tuple(item.resource_type for item in value.chain_refs) != SCENARIO_CHAINS[value.scenario_id]:
        blockers.append(_block("R30_CHAIN_INVALID", "scenario authority chain is incomplete or out of order", value.scenario_ref))
    return blockers


def _scenario_blockers(value: R30ScenarioInput, requested_at: datetime) -> list[ContractBlocker]:
    blockers = _common_blockers(value, requested_at)
    checks: tuple[tuple[bool, str, str], ...]
    if value.scenario_id == "SC07":
        guard = value.creator_guard
        assert guard is not None
        checks = (
            (guard.candidate_count > 100, "SC07_DAILY_CAPACITY_EXCEEDED", "daily candidate draft capacity exceeds 100"),
            (guard.unique_count != guard.candidate_count, "SC07_UNIQUE_COUNT_MISMATCH", "candidate batch must contain unique creators"),
            (guard.duplicate_count > 0, "SC07_DUPLICATE_CANDIDATE", "duplicate creator must be suppressed"),
            (guard.suppressed_count > 0, "SC07_SUPPRESSED_CANDIDATE", "opt-out, refusal or blacklist candidate must be suppressed"),
            (guard.expired_contact_count > 0, "SC07_EXPIRED_CONTACT", "expired contact evidence cannot enter an outreach draft"),
            (not guard.authorized_channel, "SC07_CHANNEL_NOT_AUTHORIZED", "outreach channel is not authorized"),
            (guard.outreach_sent, "SC07_AUTOMATED_OUTREACH_FORBIDDEN", "compiler cannot send creator outreach"),
            (guard.contract_signed_claimed and not guard.signature_receipt_present, "SC07_SIGNATURE_RECEIPT_MISSING", "signed claim requires an independent receipt"),
            (guard.fulfillment_claimed and not guard.fulfillment_receipt_present, "SC07_FULFILLMENT_RECEIPT_MISSING", "fulfilment claim requires an independent receipt"),
            (guard.performance_final and not guard.observation_window_closed, "SC07_PERFORMANCE_WINDOW_OPEN", "performance cannot be final before its observation window closes"),
            (not guard.relationship_contact_allowed, "SC07_RELATIONSHIP_CONTACT_BLOCKED", "relationship contact is refused, opted out or outside consent"),
        )
    elif value.scenario_id == "SC08":
        guard = value.price_guard
        assert guard is not None
        governance = guard.task_type is PriceTaskType.EXACT_PRODUCT_GOVERNANCE
        checks = (
            (governance and guard.product_relation is not ProductRelation.EXACT_SKU, "SC08_COMPETITOR_CANNOT_ENTER_GOVERNANCE", "only confirmed exact SKU can enter governance"),
            (governance and not guard.governance_basis_present, "SC08_GOVERNANCE_BASIS_MISSING", "price governance requires an exact contractual or policy basis"),
            (guard.observation_count < 2, "SC08_TWO_OBSERVATIONS_REQUIRED", "price anomaly requires at least two observations"),
            (guard.independent_source_count < 2, "SC08_INDEPENDENT_EVIDENCE_MISSING", "price anomaly requires independent evidence"),
            (not guard.observation_contexts_aligned, "SC08_OBSERVATION_CONTEXT_MISMATCH", "region, account, subsidy, freight and unit-price contexts must align"),
            (guard.legal_conclusion_present, "SC08_LEGAL_CONCLUSION_FORBIDDEN", "model cannot claim dumping, illegality or malicious competition"),
            (guard.external_action_executed, "SC08_EXTERNAL_ACTION_FORBIDDEN", "notification, complaint and report remain drafts"),
            (guard.price_changed, "SC08_PRICE_CHANGE_FORBIDDEN", "price change requires an independent production contract"),
            (guard.malicious_order_or_refund, "SC08_MALICIOUS_ORDER_REFUND_FORBIDDEN", "malicious order and refund tactics are forbidden"),
        )
    else:
        guard = value.complaint_guard
        assert guard is not None
        checks = (
            (not guard.identity_min_verified, "SC09_IDENTITY_NOT_VERIFIED", "minimum identity verification is required"),
            (not guard.pii_tokenized, "SC09_RAW_PII_FORBIDDEN", "complaint evidence must use tokenized PII references"),
            ((guard.escalation_required or guard.classification_confidence < 0.8) and not guard.escalated, "SC09_ESCALATION_MISSING", "high-risk or low-confidence complaint requires human escalation"),
            (not guard.promise_within_authority, "SC09_PROMISE_OUT_OF_AUTHORITY", "reply draft exceeds the approved promise boundary"),
            (guard.external_reply_sent, "SC09_AUTOMATED_REPLY_FORBIDDEN", "compiler cannot send a complaint response"),
            (guard.refund_executed, "SC09_AUTOMATED_REFUND_FORBIDDEN", "compiler cannot execute refund or compensation"),
            (guard.resolution_claimed and not guard.resolution_receipt_present, "SC09_RESOLUTION_RECEIPT_MISSING", "resolved claim requires an independent receipt"),
            (guard.aggregate_substitution, "SC09_CANNOT_SUBSTITUTE_AGGREGATE", "single complaint cannot substitute the SC03 aggregate"),
        )
    for failed, code, message in checks:
        if failed:
            blockers.append(_block(code, message, value.scenario_ref))
    return blockers


def compile_sc07_sc09_acceptance(
    *,
    tenant: TenantContext,
    requested_at: datetime,
    scenarios: list[R30ScenarioInput],
) -> R30Compilation:
    """Compose three independent replay drafts without runtime side effects."""

    _aware(requested_at, "requestedAt")
    if sorted(item.scenario_id for item in scenarios) != ["SC07", "SC08", "SC09"]:
        raise ValueError("exactly one SC07, SC08 and SC09 input is required")
    packs: list[R30EvidencePackDraft] = []
    for value in sorted(scenarios, key=lambda item: item.scenario_id):
        blockers = _scenario_blockers(value, requested_at)
        replay_digest = _digest(
            value.scenario_ref.content_hash,
            value.source_readiness.evidence_pack_ref.content_hash,
            value.task_run_ref.content_hash,
            value.receipt_ref.content_hash,
            value.lineage_ref.content_hash,
            value.effect_review_ref.content_hash,
            value.observed_cutoff.isoformat(),
            *(item.content_hash for item in value.logic_refs),
            *(item.content_hash for item in value.chain_refs),
        )
        packs.append(
            R30EvidencePackDraft(
                scenario_id=value.scenario_id,
                state=R30ScenarioState.BLOCKED if blockers else R30ScenarioState.READY_FOR_REVIEW,
                scenario_ref=value.scenario_ref,
                source_readiness_ref=value.source_readiness.evidence_pack_ref,
                logic_refs=value.logic_refs,
                chain_refs=value.chain_refs,
                task_run_ref=value.task_run_ref,
                receipt_ref=value.receipt_ref,
                lineage_ref=value.lineage_ref,
                effect_review_ref=value.effect_review_ref,
                replay_digest=replay_digest,
                blockers=blockers,
            )
        )
    state = R30ScenarioState.READY_FOR_REVIEW if all(item.state is R30ScenarioState.READY_FOR_REVIEW for item in packs) else R30ScenarioState.BLOCKED
    return R30Compilation(tenant=tenant, requested_at=requested_at, state=state, evidence_packs=packs)


__all__ = [
    "ComplaintCaseGuard",
    "CreatorLifecycleGuard",
    "PriceGovernanceGuard",
    "PriceTaskType",
    "ProductRelation",
    "R30Compilation",
    "R30EvidencePackDraft",
    "R30ScenarioInput",
    "R30ScenarioState",
    "SCENARIO_CHAINS",
    "SCENARIO_LOGICS",
    "compile_sc07_sc09_acceptance",
]
