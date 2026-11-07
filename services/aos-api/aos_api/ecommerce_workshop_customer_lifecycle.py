"""W6-07 customer lifecycle authority and side-effect-free batch preparation."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_workshop_customer_contracts import CustomerExactRef
from aos_api.tenant_scope import TenantScope


CUSTOMER_LIFECYCLE_SCHEMA_VERSION = "aos.ecommerce-workshop.customer-lifecycle/v1"
CUSTOMER_LOGIC_ID = "ecommerce-customer-relationship"
CUSTOMER_SKILL_IDS = (
    "build-evidence-pack",
    "segment-entities",
    "consent-and-purpose-check",
    "needs-discovery",
    "customer-journey-plan",
    "response-or-outreach-draft",
    "verify-claims",
    "review-outcomes",
)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class CustomerLifecycleBlocked(RuntimeError):
    code = "CUSTOMER_LIFECYCLE_BLOCKED"


class CustomerLifecycleConflict(CustomerLifecycleBlocked):
    code = "CUSTOMER_LIFECYCLE_CONFLICT"


class ConsentDecision(StrEnum):
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class CustomerBatchDisposition(StrEnum):
    ELIGIBLE = "eligible"
    EXCLUDED = "excluded"
    NEEDS_REVIEW = "needs_review"
    UNKNOWN = "unknown"
    DEDUPLICATED = "deduplicated"


def _unique(values: list[str], label: str) -> list[str]:
    if len(values) != len(set(values)) or any(not value.strip() for value in values):
        raise ValueError(f"{label} must be unique and non-empty")
    return values


def _unique_refs(values: list[CustomerExactRef], label: str) -> list[CustomerExactRef]:
    identities = [(ref.resource_type, ref.resource_id, ref.revision, ref.content_hash, ref.receipt_id) for ref in values]
    if len(identities) != len(set(identities)):
        raise ValueError(f"{label} must be unique")
    return values


class CreateCustomerConsentPolicyRequest(AipContractModel):
    policy_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    purpose: str = Field(min_length=1, max_length=160)
    allowed_channels: list[str] = Field(min_length=1, max_length=16)
    marking_policy_ref: CustomerExactRef
    retention_policy_ref: CustomerExactRef
    preference_policy_ref: CustomerExactRef
    retention_days: int = Field(ge=1, le=3650)
    unknown_behavior: str = Field(default="block", pattern=r"^block$")

    @model_validator(mode="after")
    def _canonical(self) -> "CreateCustomerConsentPolicyRequest":
        _unique(self.allowed_channels, "allowedChannels")
        expected = (
            (self.marking_policy_ref, "MarkingPolicyRevision"),
            (self.retention_policy_ref, "RetentionPolicyRevision"),
            (self.preference_policy_ref, "PreferencePolicyRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("customer consent policy exact refs drifted")
        return self


class CustomerConsentPolicyRevision(CreateCustomerConsentPolicyRequest):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class CreateCustomerSegmentRequest(AipContractModel):
    segment_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    definition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_ref: CustomerExactRef
    source_refs: list[CustomerExactRef] = Field(min_length=1, max_length=100)
    consent_policy_ref: CustomerExactRef
    k_anonymity_minimum: int = Field(ge=5, le=10000)
    cutoff: datetime

    @field_validator("cutoff")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("cutoff must include timezone")
        return value

    @model_validator(mode="after")
    def _refs(self) -> "CreateCustomerSegmentRequest":
        if self.schema_ref.resource_type != "SegmentSchemaRevision" or self.consent_policy_ref.resource_type != "CustomerConsentPolicyRevision":
            raise ValueError("segment schema or consent policy ref drifted")
        if any(ref.resource_type not in {"CustomerLiteProjectionRevision", "SourceReadinessRevision"} for ref in self.source_refs):
            raise ValueError("segment source refs must remain privacy-minimized")
        _unique_refs(self.source_refs, "sourceRefs")
        return self


class CustomerSegmentRevision(CreateCustomerSegmentRequest):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class CreateCustomerJourneyRequest(AipContractModel):
    journey_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    segment_ref: CustomerExactRef
    stage_definition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    entry_condition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    exit_condition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    stop_conditions: list[str] = Field(min_length=1, max_length=32)
    allowed_channels: list[str] = Field(min_length=1, max_length=16)
    eval_ref: CustomerExactRef
    policy_ref: CustomerExactRef

    @model_validator(mode="after")
    def _refs(self) -> "CreateCustomerJourneyRequest":
        expected = ((self.segment_ref, "CustomerSegmentRevision"), (self.eval_ref, "EvalContractRevision"), (self.policy_ref, "JourneyPolicyRevision"))
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("journey exact refs drifted")
        _unique(self.stop_conditions, "stopConditions")
        _unique(self.allowed_channels, "allowedChannels")
        return self


class CustomerJourneyRevision(CreateCustomerJourneyRequest):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class CreateCustomerDialogueRequest(AipContractModel):
    dialogue_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    journey_ref: CustomerExactRef
    brief_ref: CustomerExactRef
    evidence_ref: CustomerExactRef
    eval_ref: CustomerExactRef
    responsibility_ref: CustomerExactRef
    template_ref: CustomerExactRef
    strategy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    originals_reachable: bool

    @model_validator(mode="after")
    def _refs(self) -> "CreateCustomerDialogueRequest":
        expected = (
            (self.journey_ref, "CustomerJourneyRevision"), (self.brief_ref, "TaskBriefRevision"),
            (self.evidence_ref, "EvidenceBundleRevision"), (self.eval_ref, "EvalContractRevision"),
            (self.responsibility_ref, "ResponsibilityPlanRevision"), (self.template_ref, "TemplateRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("dialogue exact refs drifted")
        if not self.originals_reachable:
            raise ValueError("dialogue originals must remain reachable")
        return self


class CustomerDialogueStrategyRevision(CreateCustomerDialogueRequest):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class PrepareCustomerDialogueBatchItem(AipContractModel):
    item_key: str = Field(min_length=1, max_length=200)
    customer_ref: CustomerExactRef
    disposition: CustomerBatchDisposition
    consent_decision: ConsentDecision
    retention_active: bool | None
    k_anonymity_satisfied: bool | None
    reason_codes: list[str] = Field(default_factory=list, max_length=32)
    eligibility_evidence_refs: list[CustomerExactRef] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def _privacy_and_disposition(self) -> "PrepareCustomerDialogueBatchItem":
        if self.customer_ref.resource_type != "CustomerLiteProjectionRevision":
            raise ValueError("batch item only accepts CustomerLiteProjectionRevision")
        _unique(self.reason_codes, "reasonCodes")
        _unique_refs(self.eligibility_evidence_refs, "eligibilityEvidenceRefs")
        eligible = self.consent_decision is ConsentDecision.GRANTED and self.retention_active is True and self.k_anonymity_satisfied is True and bool(self.eligibility_evidence_refs)
        if self.disposition is CustomerBatchDisposition.ELIGIBLE and (not eligible or self.reason_codes):
            raise ValueError("eligible item requires exact granted consent/retention/k-anonymity evidence")
        if self.disposition is not CustomerBatchDisposition.ELIGIBLE and not self.reason_codes:
            raise ValueError("non-eligible item requires reasonCodes")
        return self


class CustomerDialogueBatchLedger(AipContractModel):
    input: int = Field(ge=0)
    eligible: int = Field(ge=0)
    excluded: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    unknown: int = Field(ge=0)
    deduplicated: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserves(self) -> "CustomerDialogueBatchLedger":
        if self.input != self.eligible + self.excluded + self.needs_review + self.unknown + self.deduplicated:
            raise ValueError("customer batch ledger must conserve input")
        return self


class PrepareCustomerDialogueBatchRequest(AipContractModel):
    batch_id: str = Field(min_length=1, max_length=200)
    segment_ref: CustomerExactRef
    journey_ref: CustomerExactRef
    dialogue_ref: CustomerExactRef
    consent_policy_ref: CustomerExactRef
    frequency_policy_ref: CustomerExactRef
    channel_capability_ref: CustomerExactRef
    items: list[PrepareCustomerDialogueBatchItem] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _refs(self) -> "PrepareCustomerDialogueBatchRequest":
        expected = (
            (self.segment_ref, "CustomerSegmentRevision"), (self.journey_ref, "CustomerJourneyRevision"),
            (self.dialogue_ref, "CustomerDialogueStrategyRevision"), (self.consent_policy_ref, "CustomerConsentPolicyRevision"),
            (self.frequency_policy_ref, "FrequencyPolicyRevision"), (self.channel_capability_ref, "CapabilityBindingRevision"),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError("customer batch exact refs drifted")
        _unique([item.item_key for item in self.items], "itemKeys")
        return self


class CustomerDialogueBatchRevision(AipContractModel):
    tenant: TenantContext
    batch_id: str
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    lifecycle: str = Field(pattern=r"^(prepared|frozen|stale)$")
    segment_ref: CustomerExactRef
    journey_ref: CustomerExactRef
    dialogue_ref: CustomerExactRef
    consent_policy_ref: CustomerExactRef
    frequency_policy_ref: CustomerExactRef
    channel_capability_ref: CustomerExactRef
    items: list[PrepareCustomerDialogueBatchItem]
    item_hashes: list[str]
    ledger: CustomerDialogueBatchLedger
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    contact_resolution_count: int = Field(default=0, ge=0, le=0)
    action_count: int = Field(default=0, ge=0, le=0)
    provider_call_count: int = Field(default=0, ge=0, le=0)
    send_count: int = Field(default=0, ge=0, le=0)
    external_effect_count: int = Field(default=0, ge=0, le=0)
    prior_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class FreezeCustomerDialogueBatchRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_refs: dict[str, CustomerExactRef]
    item_hashes: list[str]


class CustomerLifecycleContributionView(AipContractModel):
    schema_version: str = CUSTOMER_LIFECYCLE_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    atomic_skill_ids: list[str] = Field(default_factory=lambda: list(CUSTOMER_SKILL_IDS))
    logic_id: str = CUSTOMER_LOGIC_ID
    primary_colleague: str = "私域管家"
    collaborator_colleagues: list[str] = Field(default_factory=lambda: ["内容官", "客服专员", "导购顾问", "数据参谋"])
    consent_policy_count: int = Field(ge=0)
    segment_count: int = Field(ge=0)
    journey_count: int = Field(ge=0)
    dialogue_count: int = Field(ge=0)
    latest_batch: CustomerDialogueBatchRevision | None
    blockers: list[str]
    allowed_commands: list[str] = Field(default_factory=lambda: [
        "CREATE_CUSTOMER_CONSENT_POLICY", "CREATE_CUSTOMER_SEGMENT", "CREATE_CUSTOMER_JOURNEY",
        "CREATE_CUSTOMER_DIALOGUE", "PREPARE_CUSTOMER_DIALOGUE_BATCH", "FREEZE_CUSTOMER_DIALOGUE_BATCH",
    ])
    contact_resolution_allowed: bool = False
    start_allowed: bool = False
    send_allowed: bool = False
    external_effects_allowed: bool = False


class EcommerceWorkshopCustomerLifecycleService:
    def __init__(self, store: Any) -> None:
        self.store = store

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _ref(resource_type: str, resource_id: str, revision: int, content_hash: str) -> CustomerExactRef:
        return CustomerExactRef(resourceType=resource_type, resourceId=resource_id, revision=revision, contentHash=f"sha256:{content_hash}", receiptId=f"receipt-{resource_id}")

    def _create(self, scope: TenantScope, request: Any, actor: str, model: type[Any], append: Any, *, now: datetime | None = None) -> Any:
        at = now or datetime.now(UTC)
        payload = request.model_dump(mode="json", by_alias=True)
        item = model(tenant=self._tenant(scope), **payload, contentHash=canonical_hash(payload), createdBy=actor, createdAt=at)
        return append(scope, item)

    def create_consent_policy(self, scope: TenantScope, request: CreateCustomerConsentPolicyRequest, actor: str, *, now: datetime | None = None) -> CustomerConsentPolicyRevision:
        return self._create(scope, request, actor, CustomerConsentPolicyRevision, self.store.append_consent_policy, now=now)

    def create_segment(self, scope: TenantScope, request: CreateCustomerSegmentRequest, actor: str, *, now: datetime | None = None) -> CustomerSegmentRevision:
        self.store.require_consent_policy(scope, request.consent_policy_ref)
        return self._create(scope, request, actor, CustomerSegmentRevision, self.store.append_segment, now=now)

    def create_journey(self, scope: TenantScope, request: CreateCustomerJourneyRequest, actor: str, *, now: datetime | None = None) -> CustomerJourneyRevision:
        self.store.require_segment(scope, request.segment_ref)
        return self._create(scope, request, actor, CustomerJourneyRevision, self.store.append_journey, now=now)

    def create_dialogue(self, scope: TenantScope, request: CreateCustomerDialogueRequest, actor: str, *, now: datetime | None = None) -> CustomerDialogueStrategyRevision:
        journey = self.store.require_journey(scope, request.journey_ref)
        if journey.eval_ref != request.eval_ref:
            raise CustomerLifecycleBlocked("CUSTOMER_DIALOGUE_JOURNEY_EVAL_DRIFTED")
        return self._create(scope, request, actor, CustomerDialogueStrategyRevision, self.store.append_dialogue, now=now)

    def prepare_batch(self, scope: TenantScope, request: PrepareCustomerDialogueBatchRequest, actor: str, *, now: datetime | None = None) -> CustomerDialogueBatchRevision:
        at = now or datetime.now(UTC)
        segment = self.store.require_segment(scope, request.segment_ref)
        journey = self.store.require_journey(scope, request.journey_ref)
        dialogue = self.store.require_dialogue(scope, request.dialogue_ref)
        self.store.require_consent_policy(scope, request.consent_policy_ref)
        if journey.segment_ref != request.segment_ref or dialogue.journey_ref != request.journey_ref or segment.consent_policy_ref != request.consent_policy_ref:
            raise CustomerLifecycleBlocked("CUSTOMER_BATCH_LINEAGE_DRIFTED")
        self.store.require_external_policy_authorities(scope, request.frequency_policy_ref, request.channel_capability_ref)
        counts = {item: 0 for item in CustomerBatchDisposition}
        for item in request.items:
            counts[item.disposition] += 1
        ledger = CustomerDialogueBatchLedger(
            input=len(request.items), eligible=counts[CustomerBatchDisposition.ELIGIBLE],
            excluded=counts[CustomerBatchDisposition.EXCLUDED], needsReview=counts[CustomerBatchDisposition.NEEDS_REVIEW],
            unknown=counts[CustomerBatchDisposition.UNKNOWN], deduplicated=counts[CustomerBatchDisposition.DEDUPLICATED],
        )
        refs = {
            "segment": request.segment_ref, "journey": request.journey_ref, "dialogue": request.dialogue_ref,
            "consentPolicy": request.consent_policy_ref, "frequencyPolicy": request.frequency_policy_ref,
            "channelCapability": request.channel_capability_ref,
        }
        item_hashes = [canonical_hash(item.model_dump(mode="json", by_alias=True)) for item in request.items]
        binding_hash = canonical_hash({"refs": refs, "itemHashes": item_hashes})
        payload = request.model_dump(mode="json", by_alias=True)
        content_hash = canonical_hash({**payload, "ledger": ledger, "bindingHash": binding_hash})
        existing = self.store.latest_batch_or_none(scope, request.batch_id)
        if existing is not None:
            if existing.content_hash == content_hash:
                return existing
            raise CustomerLifecycleConflict("CUSTOMER_BATCH_IDEMPOTENCY_CONFLICT")
        item = CustomerDialogueBatchRevision(
            tenant=self._tenant(scope), batchId=request.batch_id, revision=1, version=1, lifecycle="prepared",
            segmentRef=request.segment_ref, journeyRef=request.journey_ref, dialogueRef=request.dialogue_ref,
            consentPolicyRef=request.consent_policy_ref, frequencyPolicyRef=request.frequency_policy_ref,
            channelCapabilityRef=request.channel_capability_ref, items=request.items, itemHashes=item_hashes,
            ledger=ledger, bindingHash=binding_hash, contentHash=content_hash, createdBy=actor, createdAt=at,
        )
        return self.store.append_batch(scope, item)

    def freeze_batch(self, scope: TenantScope, batch_id: str, request: FreezeCustomerDialogueBatchRequest, actor: str, *, now: datetime | None = None) -> CustomerDialogueBatchRevision:
        at = now or datetime.now(UTC)
        current = self.store.latest_batch(scope, batch_id)
        if current.lifecycle != "prepared" or current.version != request.expected_version or current.content_hash != request.expected_content_hash:
            raise CustomerLifecycleConflict("CUSTOMER_BATCH_EXPECTED_VERSION_OR_HASH_DRIFTED")
        expected_refs = {
            "segment": current.segment_ref, "journey": current.journey_ref, "dialogue": current.dialogue_ref,
            "consentPolicy": current.consent_policy_ref, "frequencyPolicy": current.frequency_policy_ref,
            "channelCapability": current.channel_capability_ref,
        }
        if request.exact_refs != expected_refs or request.item_hashes != current.item_hashes:
            raise CustomerLifecycleConflict("CUSTOMER_BATCH_EXACT_REFS_OR_ITEMS_DRIFTED")
        payload = current.model_dump(mode="json", by_alias=True, exclude={"revision", "version", "lifecycle", "prior_content_hash", "content_hash", "created_by", "created_at"})
        content_hash = canonical_hash({**payload, "revision": current.revision + 1, "version": current.version + 1, "lifecycle": "frozen", "priorContentHash": current.content_hash})
        frozen = current.model_copy(update={"revision": current.revision + 1, "version": current.version + 1, "lifecycle": "frozen", "prior_content_hash": current.content_hash, "content_hash": content_hash, "created_by": actor, "created_at": at})
        return self.store.append_batch(scope, frozen)

    def contribution_view(self, scope: TenantScope, *, now: datetime | None = None) -> CustomerLifecycleContributionView:
        blockers: list[str] = []
        try:
            counts = self.store.authority_counts(scope)
            latest = self.store.latest_batch_or_none_any(scope)
        except CustomerLifecycleBlocked as exc:
            counts = {"consent_policy": 0, "segment": 0, "journey": 0, "dialogue": 0}
            latest = None
            blockers.append(str(exc))
        blockers.extend(["CUSTOMER_CONTACT_RESOLUTION_NOT_AUTHORIZED", "CUSTOMER_START_SEND_NOT_AUTHORIZED"])
        return CustomerLifecycleContributionView(
            tenant=self._tenant(scope), evaluatedAt=now or datetime.now(UTC),
            consentPolicyCount=counts["consent_policy"], segmentCount=counts["segment"],
            journeyCount=counts["journey"], dialogueCount=counts["dialogue"], latestBatch=latest, blockers=blockers,
        )


__all__ = [
    "CUSTOMER_LIFECYCLE_SCHEMA_VERSION", "CUSTOMER_LOGIC_ID", "CUSTOMER_SKILL_IDS", "ConsentDecision",
    "CustomerBatchDisposition", "CustomerConsentPolicyRevision", "CustomerDialogueBatchLedger",
    "CustomerDialogueBatchRevision", "CustomerDialogueStrategyRevision", "CustomerJourneyRevision",
    "CustomerLifecycleBlocked", "CustomerLifecycleConflict", "CustomerLifecycleContributionView",
    "CustomerSegmentRevision", "CreateCustomerConsentPolicyRequest", "CreateCustomerDialogueRequest",
    "CreateCustomerJourneyRequest", "CreateCustomerSegmentRequest", "EcommerceWorkshopCustomerLifecycleService",
    "FreezeCustomerDialogueBatchRequest", "PrepareCustomerDialogueBatchItem", "PrepareCustomerDialogueBatchRequest",
]
