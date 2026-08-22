"""Fail-closed G2 CustomerLite and three-core-agent composition contracts.

This SolutionPack domain module composes existing CustomerLite, C/G/S Logic and
Handoff authorities through exact references.  It is deliberately pure: no
database, Provider, Tool, Action, message, order, refund, price or inventory
side effect is reachable from this module.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef


CONTENT_LOGIC_IDS = tuple(f"C{index:02d}" for index in range(1, 9))
SHOPPING_LOGIC_IDS = tuple(f"G{index:02d}" for index in range(1, 7))
SERVICE_LOGIC_IDS = tuple(f"S{index:02d}" for index in range(1, 7))
CORE_AGENT_LOGIC_IDS = CONTENT_LOGIC_IDS + SHOPPING_LOGIC_IDS + SERVICE_LOGIC_IDS

_UNSAFE_TEXT = re.compile(
    r"(?:\b1[3-9]\d{9}\b|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"(?:openid|open_id|mobile|phone|address|身份证|手机号|收货地址)\s*[:=：]?|"
    r"ignore\s+(?:all\s+)?previous|reveal\s+(?:the\s+)?system\s+prompt|"
    r"jailbreak|忽略(?:以上|之前)|泄露系统提示词)",
    re.IGNORECASE,
)


def _exact_type(value: ExactRevisionRef, expected: str, label: str) -> None:
    if value.resource_type != expected:
        raise ValueError(f"{label} must reference {expected}")


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _digest(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


class ConsentPurpose(StrEnum):
    CONSULTATION = "consultation"
    SERVICE = "service"
    MARKETING = "marketing"


class ConsentStatus(StrEnum):
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


class DeletionState(StrEnum):
    ACTIVE = "active"
    DELETION_REQUESTED = "deletion_requested"
    ERASED = "erased"
    INVALIDATED = "invalidated"


class PriceState(StrEnum):
    CONSISTENT = "consistent"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


class InventoryState(StrEnum):
    AVAILABLE = "available"
    LIMITED = "limited"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


class G2CoreAgentState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"
    BLOCKED = "blocked"


class SourceReadinessStatus(StrEnum):
    READY = "ready"
    FAILED = "failed"
    BLOCKED = "blocked"


class SourceReadinessGateSnapshot(AipContractModel):
    evidence_pack_ref: ExactRevisionRef
    status: SourceReadinessStatus
    source_count: int = Field(ge=12, le=12)
    ready_count: int = Field(ge=0, le=12)
    checked_at: datetime
    cutoff_at: datetime
    fresh_until: datetime

    @model_validator(mode="after")
    def _exact_gate(self) -> "SourceReadinessGateSnapshot":
        _exact_type(
            self.evidence_pack_ref,
            "SourceReadinessEvidencePackRevision",
            "evidencePackRef",
        )
        _aware(self.checked_at, "checkedAt")
        _aware(self.cutoff_at, "cutoffAt")
        _aware(self.fresh_until, "freshUntil")
        if self.fresh_until <= self.checked_at:
            raise ValueError("SourceReadiness freshUntil must be after checkedAt")
        if self.status is SourceReadinessStatus.READY and self.ready_count != 12:
            raise ValueError("ready SourceReadiness requires 12/12 sources")
        if self.status is not SourceReadinessStatus.READY and self.ready_count == 12:
            raise ValueError("non-ready SourceReadiness cannot claim 12/12 sources")
        return self


class ConsentSnapshot(AipContractModel):
    purpose: ConsentPurpose
    status: ConsentStatus
    consent_ref: ExactRevisionRef
    captured_at: datetime

    @model_validator(mode="after")
    def _exact_consent(self) -> "ConsentSnapshot":
        _exact_type(self.consent_ref, "ConsentEventRevision", "consentRef")
        _aware(self.captured_at, "capturedAt")
        return self


class CustomerLiteReadProjection(AipContractModel):
    projection_ref: ExactRevisionRef
    pseudonymous_subject_ref: str = Field(
        pattern=r"^hmac://CustomerLite/[A-Za-z0-9._:-]+@v[1-9][0-9]*$"
    )
    lifecycle_stage: Literal[
        "anonymous", "lead", "consulting", "customer", "repeat", "inactive"
    ]
    member_level_band: Literal["unknown", "standard", "plus", "premium"]
    paid_count_band: Literal["none", "one_to_three", "four_to_ten", "above_ten"]
    paid_amount_band: Literal["none", "low", "medium", "high"]
    last_paid_recency_band: Literal[
        "never", "within_30d", "within_90d", "older_than_90d", "unknown"
    ]
    service_risk_level: Literal["none", "low", "medium", "high"]
    consents: list[ConsentSnapshot] = Field(min_length=1, max_length=3)
    deletion_state: DeletionState
    deletion_event_ref: ExactRevisionRef | None = None
    markings: list[str] = Field(min_length=1, max_length=16)
    observed_at: datetime
    fresh_until: datetime

    @field_validator("markings")
    @classmethod
    def _unique_markings(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized) or len(normalized) != len(set(normalized)):
            raise ValueError("markings must be unique and non-blank")
        return normalized

    @model_validator(mode="after")
    def _minimal_projection(self) -> "CustomerLiteReadProjection":
        _exact_type(
            self.projection_ref,
            "CustomerLiteProjectionRevision",
            "projectionRef",
        )
        _aware(self.observed_at, "observedAt")
        _aware(self.fresh_until, "freshUntil")
        if self.fresh_until <= self.observed_at:
            raise ValueError("freshUntil must be after observedAt")
        purposes = [item.purpose for item in self.consents]
        if len(purposes) != len(set(purposes)):
            raise ValueError("consent purposes must be unique")
        if "PII_MINIMIZED" not in self.markings:
            raise ValueError("CustomerLite projection requires PII_MINIMIZED marking")
        if self.deletion_state is DeletionState.ACTIVE:
            if self.deletion_event_ref is not None:
                raise ValueError("active projection cannot carry a deletion event")
        else:
            if self.deletion_event_ref is None:
                raise ValueError("non-active projection requires a deletion event")
            _exact_type(
                self.deletion_event_ref,
                "CustomerLiteDeletionEventRevision",
                "deletionEventRef",
            )
        return self


class CoreAgentFactSnapshot(AipContractModel):
    product_ref: ExactRevisionRef
    sku_ref: ExactRevisionRef | None = None
    price_ref: ExactRevisionRef
    inventory_ref: ExactRevisionRef
    cutoff_at: datetime
    fresh_until: datetime
    price_state: PriceState
    inventory_state: InventoryState

    @model_validator(mode="after")
    def _exact_facts(self) -> "CoreAgentFactSnapshot":
        _exact_type(self.product_ref, "ProductRevision", "productRef")
        if self.sku_ref is not None:
            _exact_type(self.sku_ref, "ProductSkuRevision", "skuRef")
        _exact_type(self.price_ref, "PriceSnapshotRevision", "priceRef")
        _exact_type(self.inventory_ref, "InventorySnapshotRevision", "inventoryRef")
        _aware(self.cutoff_at, "cutoffAt")
        _aware(self.fresh_until, "freshUntil")
        if self.fresh_until <= self.cutoff_at:
            raise ValueError("freshUntil must be after cutoffAt")
        return self


class CoreAgentLogicStage(AipContractModel):
    order: int = Field(ge=1, le=20)
    logic_id: str = Field(pattern=r"^(?:C0[1-8]|G0[1-6]|S0[1-6])$")
    logic_ref: ExactRevisionRef

    @model_validator(mode="after")
    def _canonical_logic(self) -> "CoreAgentLogicStage":
        _exact_type(self.logic_ref, "LogicGraphRevision", "logicRef")
        if self.logic_ref.resource_id != f"ecommerce.logic.{self.logic_id}":
            raise ValueError("logicRef must bind the canonical ecommerce Logic ID")
        return self


class G2CoreAgentInput(AipContractModel):
    source_readiness: SourceReadinessGateSnapshot
    customer: CustomerLiteReadProjection
    fact_snapshots: list[CoreAgentFactSnapshot] = Field(min_length=1, max_length=50)
    knowledge_snapshot_ref: ExactRevisionRef
    content_policy_ref: ExactRevisionRef
    recommendation_policy_ref: ExactRevisionRef
    service_policy_ref: ExactRevisionRef
    logic_stages: list[CoreAgentLogicStage] = Field(min_length=20, max_length=20)
    consultation_summary: str = Field(min_length=1, max_length=1000)
    service_issue_summary: str = Field(min_length=1, max_length=1000)
    requested_at: datetime

    @field_validator("consultation_summary", "service_issue_summary")
    @classmethod
    def _safe_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if _UNSAFE_TEXT.search(cleaned):
            raise ValueError("summary contains unsafe or identifying content")
        return cleaned

    @model_validator(mode="after")
    def _exact_composition(self) -> "G2CoreAgentInput":
        _exact_type(
            self.knowledge_snapshot_ref,
            "WikiSnapshotRevision",
            "knowledgeSnapshotRef",
        )
        for label, value in (
            ("contentPolicyRef", self.content_policy_ref),
            ("recommendationPolicyRef", self.recommendation_policy_ref),
            ("servicePolicyRef", self.service_policy_ref),
        ):
            _exact_type(value, "PolicyRevision", label)
        actual = [(item.order, item.logic_id) for item in self.logic_stages]
        expected = list(enumerate(CORE_AGENT_LOGIC_IDS, start=1))
        if actual != expected:
            raise ValueError(
                "logicStages must contain ordered C01-C08, G01-G06 and S01-S06"
            )
        _aware(self.requested_at, "requestedAt")
        return self


class ContentAssetDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    draft_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    customer_projection_ref: ExactRevisionRef
    knowledge_snapshot_ref: ExactRevisionRef
    policy_ref: ExactRevisionRef
    production_written: Literal[False] = False


class ConsultationCaseDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    summary_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    customer_projection_ref: ExactRevisionRef
    consent_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=2)
    production_written: Literal[False] = False


class RecommendationDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    customer_projection_ref: ExactRevisionRef
    product_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=50)
    price_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=50)
    inventory_refs: list[ExactRevisionRef] = Field(min_length=1, max_length=50)
    policy_ref: ExactRevisionRef
    external_send_authorized: Literal[False] = False
    discount_authorized: Literal[False] = False
    production_written: Literal[False] = False


class ServiceCaseDraft(AipContractModel):
    status: Literal["draft"] = "draft"
    issue_summary_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    customer_projection_ref: ExactRevisionRef
    policy_ref: ExactRevisionRef
    commitments: list[str] = Field(default_factory=list, max_length=0)
    reply_authorized: Literal[False] = False
    refund_authorized: Literal[False] = False
    compensation_authorized: Literal[False] = False
    production_written: Literal[False] = False


class HandoffReplayDraft(AipContractModel):
    route: Literal[
        "content_to_shopping", "shopping_to_service", "service_to_content"
    ]
    status: Literal["draft"] = "draft"
    allowed_fields: list[str] = Field(min_length=1, max_length=8)
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    external_delivery_authorized: Literal[False] = False

    @field_validator("allowed_fields")
    @classmethod
    def _minimal_fields(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not value.strip() for value in values):
            raise ValueError("allowedFields must be unique and non-blank")
        forbidden = {"name", "mobile", "phone", "address", "openid", "chatRaw"}
        if forbidden.intersection(values):
            raise ValueError("handoff allowedFields contains forbidden identity data")
        return values


class G2CoreAgentCompilation(AipContractModel):
    tenant: TenantContext
    state: G2CoreAgentState
    blockers: list[ContractBlocker]
    content_draft: ContentAssetDraft | None = None
    consultation_draft: ConsultationCaseDraft | None = None
    recommendation_draft: RecommendationDraft | None = None
    service_case_draft: ServiceCaseDraft | None = None
    handoff_replays: list[HandoffReplayDraft] = Field(default_factory=list, max_length=3)
    external_action_authorized: Literal[False] = False
    production_written: Literal[False] = False

    @model_validator(mode="after")
    def _honest_state(self) -> "G2CoreAgentCompilation":
        drafts = (
            self.content_draft,
            self.consultation_draft,
            self.recommendation_draft,
            self.service_case_draft,
        )
        if self.state is G2CoreAgentState.READY_FOR_REVIEW:
            if self.blockers or any(item is None for item in drafts):
                raise ValueError("ready compilation requires all drafts and no blockers")
            if len(self.handoff_replays) != 3:
                raise ValueError("ready compilation requires three handoff replays")
        elif any(item is not None for item in drafts) or self.handoff_replays:
            raise ValueError("blocked compilation cannot contain drafts or handoffs")
        return self


def _blockers(value: G2CoreAgentInput) -> list[ContractBlocker]:
    blockers: list[ContractBlocker] = []
    if value.source_readiness.status is not SourceReadinessStatus.READY:
        blockers.append(
            ContractBlocker(
                code="G2_SOURCE_READINESS_NOT_READY",
                message="canonical SourceReadiness is not 12/12 READY",
                resource_ref=value.source_readiness.evidence_pack_ref,
            )
        )
    if value.source_readiness.fresh_until <= value.requested_at:
        blockers.append(
            ContractBlocker(
                code="G2_SOURCE_READINESS_STALE",
                message="canonical SourceReadiness evidence is stale",
                resource_ref=value.source_readiness.evidence_pack_ref,
            )
        )
    if value.customer.deletion_state is not DeletionState.ACTIVE:
        blockers.append(
            ContractBlocker(
                code="G2_CUSTOMER_DELETED_OR_INVALIDATED",
                message="CustomerLite projection is deleted, pending deletion or invalidated",
                resource_ref=value.customer.projection_ref,
            )
        )
    consent_by_purpose = {item.purpose: item for item in value.customer.consents}
    for purpose in (ConsentPurpose.CONSULTATION, ConsentPurpose.SERVICE):
        consent = consent_by_purpose.get(purpose)
        if consent is None or consent.status is not ConsentStatus.GRANTED:
            blockers.append(
                ContractBlocker(
                    code="G2_REQUIRED_CONSENT_NOT_GRANTED",
                    message=f"{purpose.value} consent is missing or not granted",
                    resource_ref=consent.consent_ref if consent else None,
                )
            )
    if value.customer.fresh_until <= value.requested_at:
        blockers.append(
            ContractBlocker(
                code="G2_CUSTOMER_PROJECTION_STALE",
                message="CustomerLite projection is stale",
                resource_ref=value.customer.projection_ref,
            )
        )
    cutoffs = {item.cutoff_at for item in value.fact_snapshots}
    if len(cutoffs) != 1:
        blockers.append(
            ContractBlocker(
                code="G2_COMMERCE_FACT_CUTOFF_MISMATCH",
                message="Product, price and inventory facts do not share one cutoff",
            )
        )
    elif cutoffs != {value.source_readiness.cutoff_at}:
        blockers.append(
            ContractBlocker(
                code="G2_SOURCE_AND_FACT_CUTOFF_MISMATCH",
                message="commerce facts do not share the SourceReadiness cutoff",
                resource_ref=value.source_readiness.evidence_pack_ref,
            )
        )
    for item in value.fact_snapshots:
        if item.fresh_until <= value.requested_at:
            blockers.append(
                ContractBlocker(
                    code="G2_PRODUCT_FACTS_STALE",
                    message="Product fact snapshot is stale",
                    resource_ref=item.product_ref,
                )
            )
        if item.price_state is not PriceState.CONSISTENT:
            blockers.append(
                ContractBlocker(
                    code="G2_PRICE_NOT_AUTHORITATIVE",
                    message="Price snapshot is conflicting or unknown",
                    resource_ref=item.price_ref,
                )
            )
        if item.inventory_state is not InventoryState.AVAILABLE:
            blockers.append(
                ContractBlocker(
                    code="G2_INVENTORY_NOT_AVAILABLE",
                    message="Inventory is unavailable, limited or unknown",
                    resource_ref=item.inventory_ref,
                )
            )
    return blockers


def compile_g2_core_agent_collaboration(
    tenant: TenantContext,
    value: G2CoreAgentInput,
) -> G2CoreAgentCompilation:
    """Compile review-only G2 drafts without persisting or delivering them."""

    blockers = _blockers(value)
    if blockers:
        return G2CoreAgentCompilation(
            tenant=tenant,
            state=G2CoreAgentState.BLOCKED,
            blockers=blockers,
        )
    consent_refs = [
        item.consent_ref
        for item in value.customer.consents
        if item.purpose in {ConsentPurpose.CONSULTATION, ConsentPurpose.SERVICE}
    ]
    consultation_hash = _digest(
        value.consultation_summary,
        value.customer.projection_ref.content_hash,
    )
    service_hash = _digest(
        value.service_issue_summary,
        value.customer.projection_ref.content_hash,
    )
    content_digest = _digest(
        value.source_readiness.evidence_pack_ref.content_hash,
        value.knowledge_snapshot_ref.content_hash,
        value.content_policy_ref.content_hash,
    )
    return G2CoreAgentCompilation(
        tenant=tenant,
        state=G2CoreAgentState.READY_FOR_REVIEW,
        blockers=[],
        content_draft=ContentAssetDraft(
            draft_digest=content_digest,
            customer_projection_ref=value.customer.projection_ref,
            knowledge_snapshot_ref=value.knowledge_snapshot_ref,
            policy_ref=value.content_policy_ref,
        ),
        consultation_draft=ConsultationCaseDraft(
            summary_hash=consultation_hash,
            customer_projection_ref=value.customer.projection_ref,
            consent_refs=consent_refs,
        ),
        recommendation_draft=RecommendationDraft(
            customer_projection_ref=value.customer.projection_ref,
            product_refs=[item.product_ref for item in value.fact_snapshots],
            price_refs=[item.price_ref for item in value.fact_snapshots],
            inventory_refs=[item.inventory_ref for item in value.fact_snapshots],
            policy_ref=value.recommendation_policy_ref,
        ),
        service_case_draft=ServiceCaseDraft(
            issue_summary_hash=service_hash,
            customer_projection_ref=value.customer.projection_ref,
            policy_ref=value.service_policy_ref,
        ),
        handoff_replays=[
            HandoffReplayDraft(
                route="content_to_shopping",
                allowed_fields=[
                    "contentArtifactRef",
                    "productRefs",
                    "consentRefs",
                    "customerProjectionRef",
                ],
                context_digest=_digest(content_digest, consultation_hash),
            ),
            HandoffReplayDraft(
                route="shopping_to_service",
                allowed_fields=[
                    "recommendationRef",
                    "productRefs",
                    "customerProjectionRef",
                    "serviceIssueSummaryHash",
                ],
                context_digest=_digest(consultation_hash, service_hash),
            ),
            HandoffReplayDraft(
                route="service_to_content",
                allowed_fields=[
                    "aggregateOutcomeRef",
                    "faqTags",
                    "misunderstandingTags",
                ],
                context_digest=_digest(service_hash, content_digest),
            ),
        ],
    )


__all__ = [
    "CONTENT_LOGIC_IDS",
    "CORE_AGENT_LOGIC_IDS",
    "ConsentSnapshot",
    "CoreAgentFactSnapshot",
    "CoreAgentLogicStage",
    "CustomerLiteReadProjection",
    "G2CoreAgentCompilation",
    "G2CoreAgentInput",
    "G2CoreAgentState",
    "SERVICE_LOGIC_IDS",
    "SHOPPING_LOGIC_IDS",
    "SourceReadinessGateSnapshot",
    "SourceReadinessStatus",
    "compile_g2_core_agent_collaboration",
]
