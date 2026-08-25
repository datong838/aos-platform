"""W6-05 governed price research authority and side-effect-free batch preparation."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.ecommerce_workshop_price_governance_contracts import PriceExactRef, PriceQuoteBasis
from aos_api.tenant_scope import TenantScope


PRICE_RESEARCH_SCHEMA_VERSION = "aos.ecommerce-workshop.price-research/v1"
PRICE_LOGIC_ID = "ecommerce-price-governance"
PRICE_SKILL_IDS = (
    "discover-price-sources",
    "normalize-price-observations",
    "match-comparable-products",
    "evaluate-price-policy",
    "prepare-price-research-batch",
)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class PriceResearchBlocked(RuntimeError):
    code = "PRICE_RESEARCH_BLOCKED"


class PriceResearchConflict(PriceResearchBlocked):
    code = "PRICE_RESEARCH_CONFLICT"


class PriceSourceLicense(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    UNKNOWN = "unknown"


class PriceComparability(StrEnum):
    COMPARABLE = "comparable"
    NOT_COMPARABLE = "not_comparable"
    UNKNOWN = "unknown"


class PriceMatchConfidence(StrEnum):
    PRELIMINARY = "preliminary"
    CONFIRMED = "confirmed"


class PriceBatchDisposition(StrEnum):
    ELIGIBLE = "eligible"
    EXCLUDED = "excluded"
    NEEDS_REVIEW = "needs_review"
    UNKNOWN = "unknown"
    DEDUPLICATED = "deduplicated"


def _unique(values: list[str], label: str) -> list[str]:
    if len(values) != len(set(values)) or any(not value.strip() for value in values):
        raise ValueError(f"{label} must be unique and non-empty")
    return values


class PriceResearchProfileRequest(AipContractModel):
    profile_id: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=1)
    allowed_source_kinds: list[str] = Field(min_length=1, max_length=32)
    allowed_markets: list[str] = Field(min_length=1, max_length=32)
    allowed_currencies: list[str] = Field(min_length=1, max_length=32)
    allowed_units: list[str] = Field(min_length=1, max_length=32)
    required_fact_keys: list[str] = Field(min_length=1, max_length=64)
    output_schema_ref: PriceExactRef
    freshness_seconds: int = Field(ge=60, le=2_592_000)
    retention_days: int = Field(ge=1, le=3650)
    rate_limit_per_hour: int = Field(ge=1, le=100_000)
    capacity_limit: int = Field(ge=1, le=100_000)
    allow_arbitrary_urls: bool = False

    @model_validator(mode="after")
    def _canonical(self) -> "PriceResearchProfileRequest":
        for field in ("allowed_source_kinds", "allowed_markets", "allowed_currencies", "allowed_units", "required_fact_keys"):
            _unique(getattr(self, field), field)
        if self.output_schema_ref.resource_type != "SchemaRevision":
            raise ValueError("outputSchemaRef must reference SchemaRevision")
        if self.allow_arbitrary_urls:
            raise ValueError("price research never accepts arbitrary URLs")
        return self


class PriceResearchProfileRevision(PriceResearchProfileRequest):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class NormalizePriceObservationRequest(AipContractModel):
    profile_ref: PriceExactRef
    research_artifact_ref: PriceExactRef
    source_kind: str = Field(min_length=1, max_length=120)
    source_license: PriceSourceLicense
    market: str = Field(min_length=1, max_length=120)
    amount: float | None = Field(default=None, ge=0)
    quote_basis: PriceQuoteBasis
    observed_at: datetime
    source_sequence: int = Field(ge=1)
    artifact_schema_ref: PriceExactRef
    original_refs: list[PriceExactRef] = Field(min_length=1, max_length=100)
    merged_original_refs: list[PriceExactRef] = Field(default_factory=list, max_length=100)
    fact_keys: list[str] = Field(min_length=1, max_length=100)
    comparability: PriceComparability

    @field_validator("observed_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("observedAt must include timezone")
        return value

    @model_validator(mode="after")
    def _typed(self) -> "NormalizePriceObservationRequest":
        expected = ((self.profile_ref, "PriceResearchProfileRevision"), (self.research_artifact_ref, "ResearchArtifactRevision"), (self.artifact_schema_ref, "SchemaRevision"))
        if any(ref.resource_type != resource_type for ref, resource_type in expected):
            raise ValueError("price normalization exact refs have invalid resourceType")
        identities = [(ref.resource_type, ref.resource_id, ref.revision, ref.content_hash) for ref in [*self.original_refs, *self.merged_original_refs]]
        if len(identities) != len(set(identities)):
            raise ValueError("price originals must be unique")
        _unique(self.fact_keys, "factKeys")
        if self.amount is not None and not isfinite(self.amount):
            raise ValueError("amount must be finite")
        if self.comparability is PriceComparability.COMPARABLE and self.amount is None:
            raise ValueError("comparable observation requires amount")
        if self.comparability is PriceComparability.UNKNOWN and self.amount is not None:
            raise ValueError("unknown observation cannot expose amount")
        return self


class PriceObservationRevision(AipContractModel):
    tenant: TenantContext
    observation_id: str
    revision: int = 1
    profile_ref: PriceExactRef
    research_artifact_ref: PriceExactRef
    source_kind: str
    market: str
    amount: float | None
    quote_basis: PriceQuoteBasis
    observed_at: datetime
    source_sequence: int
    original_refs: list[PriceExactRef]
    merged_original_refs: list[PriceExactRef]
    fact_keys: list[str]
    comparability: PriceComparability
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class CreatePriceMatchObservationRequest(AipContractModel):
    observation_ref: PriceExactRef
    sku_ref: PriceExactRef
    evidence_bundle_ref: PriceExactRef
    feature_schema_ref: PriceExactRef
    logic_ref: PriceExactRef
    policy_ref: PriceExactRef
    score: float = Field(ge=0, le=1)
    policy_threshold: float = Field(ge=0, le=1)
    feature_summaries: dict[str, float] = Field(min_length=1, max_length=64)
    conflicting_feature_keys: list[str] = Field(default_factory=list, max_length=64)
    originals_reachable: bool

    @model_validator(mode="after")
    def _typed(self) -> "CreatePriceMatchObservationRequest":
        expected = {
            "observation_ref": "PriceObservationRevision", "sku_ref": "ProductSkuRevision",
            "evidence_bundle_ref": "EvidenceBundleRevision", "feature_schema_ref": "FeatureSchemaRevision",
            "logic_ref": "LogicPublicationRevision", "policy_ref": "ProductMatchPolicyRevision",
        }
        for field, resource_type in expected.items():
            if getattr(self, field).resource_type != resource_type:
                raise ValueError(f"{field} must reference {resource_type}")
        _unique(self.conflicting_feature_keys, "conflictingFeatureKeys")
        return self


class ProductMatchObservation(AipContractModel):
    tenant: TenantContext
    match_observation_id: str
    revision: int = 1
    observation_ref: PriceExactRef
    sku_ref: PriceExactRef
    evidence_bundle_ref: PriceExactRef
    feature_schema_ref: PriceExactRef
    logic_ref: PriceExactRef
    policy_ref: PriceExactRef
    score: float
    policy_threshold: float
    feature_summaries: dict[str, float]
    conflicting_feature_keys: list[str]
    originals_reachable: bool
    confidence: PriceMatchConfidence
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class DecideProductMatchRequest(AipContractModel):
    match_observation_ref: PriceExactRef
    disposition: str = Field(pattern=r"^(confirmed|rejected|needs_review)$")
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,119}$")
    evidence_ref: PriceExactRef

    @model_validator(mode="after")
    def _refs(self) -> "DecideProductMatchRequest":
        if self.match_observation_ref.resource_type != "ProductMatchObservation" or self.evidence_ref.resource_type != "EvidenceBundleRevision":
            raise ValueError("match decision requires observation and evidence exact refs")
        return self


class ProductMatchDecisionRevision(AipContractModel):
    tenant: TenantContext
    decision_id: str
    revision: int = 1
    match_observation_ref: PriceExactRef
    disposition: str
    reason_code: str
    evidence_ref: PriceExactRef
    decided_by: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decided_at: datetime


class MonitoringPolicyRequest(AipContractModel):
    policy_id: str = Field(min_length=1, max_length=160)
    revision: int = Field(ge=1)
    scope_refs: list[PriceExactRef] = Field(min_length=1, max_length=100)
    basis: str = Field(pattern=r"^(list|landed)$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    unit: str = Field(min_length=1, max_length=80)
    tolerance_ratio: float = Field(ge=0, le=1)
    freshness_seconds: int = Field(ge=60, le=2_592_000)
    minimum_originals: int = Field(ge=1, le=100)
    minimum_match_confidence: PriceMatchConfidence
    eval_ref: PriceExactRef

    @model_validator(mode="after")
    def _refs(self) -> "MonitoringPolicyRequest":
        if self.eval_ref.resource_type != "EvalContractRevision":
            raise ValueError("evalRef must reference EvalContractRevision")
        identities = [(ref.resource_type, ref.resource_id, ref.revision, ref.content_hash) for ref in self.scope_refs]
        if len(identities) != len(set(identities)):
            raise ValueError("scopeRefs must be unique")
        return self


class MonitoringPolicyRevision(MonitoringPolicyRequest):
    tenant: TenantContext
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class PreparePriceResearchBatchItem(AipContractModel):
    sku_ref: PriceExactRef
    observation_ref: PriceExactRef
    match_observation_ref: PriceExactRef
    match_decision_ref: PriceExactRef
    disposition: PriceBatchDisposition
    reason_codes: list[str] = Field(default_factory=list, max_length=32)
    license_eligible: bool
    freshness_eligible: bool
    rate_eligible: bool
    capacity_eligible: bool
    budget_eligible: bool

    @model_validator(mode="after")
    def _item(self) -> "PreparePriceResearchBatchItem":
        expected = ((self.sku_ref, "ProductSkuRevision"), (self.observation_ref, "PriceObservationRevision"), (self.match_observation_ref, "ProductMatchObservation"), (self.match_decision_ref, "ProductMatchDecisionRevision"))
        if any(ref.resource_type != resource_type for ref, resource_type in expected):
            raise ValueError("price batch item exact refs have invalid resourceType")
        gates = self.license_eligible and self.freshness_eligible and self.rate_eligible and self.capacity_eligible and self.budget_eligible
        if self.disposition is PriceBatchDisposition.ELIGIBLE and not gates:
            raise ValueError("eligible price item requires every prepare gate")
        if self.disposition is not PriceBatchDisposition.ELIGIBLE and not self.reason_codes:
            raise ValueError("non-eligible price item requires reasonCodes")
        return self


class PreparePriceResearchBatchRequest(AipContractModel):
    batch_id: str = Field(min_length=1, max_length=200)
    brief_ref: PriceExactRef
    eval_ref: PriceExactRef
    responsibility_plan_ref: PriceExactRef
    profile_ref: PriceExactRef
    monitoring_policy_ref: PriceExactRef
    capacity_snapshot_ref: PriceExactRef
    budget_snapshot_ref: PriceExactRef
    skill_refs: list[PriceExactRef] = Field(min_length=5, max_length=12)
    logic_ref: PriceExactRef
    agent_binding_ref: PriceExactRef
    items: list[PreparePriceResearchBatchItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _composition(self) -> "PreparePriceResearchBatchRequest":
        expected = {
            "brief_ref": "TaskBriefRevision", "eval_ref": "EvalContractRevision", "responsibility_plan_ref": "ResponsibilityPlanRevision",
            "profile_ref": "PriceResearchProfileRevision", "monitoring_policy_ref": "MonitoringPolicyRevision",
            "capacity_snapshot_ref": "CapacitySnapshotRevision", "budget_snapshot_ref": "BudgetSnapshotRevision",
            "logic_ref": "LogicPublicationRevision", "agent_binding_ref": "AgentBindingRevision",
        }
        for field, resource_type in expected.items():
            if getattr(self, field).resource_type != resource_type:
                raise ValueError(f"{field} must reference {resource_type}")
        if any(ref.resource_type != "SkillRevision" for ref in self.skill_refs) or [ref.resource_id for ref in self.skill_refs] != list(PRICE_SKILL_IDS):
            raise ValueError("skillRefs must follow canonical atomic price skill order")
        if self.logic_ref.resource_id != PRICE_LOGIC_ID:
            raise ValueError("logicRef must be ecommerce-price-governance")
        identities = [(item.sku_ref.resource_id, item.observation_ref.resource_id) for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate price targets must be represented as deduplicated items")
        return self


class PriceResearchBatchLedger(AipContractModel):
    input: int = Field(ge=0)
    eligible: int = Field(ge=0)
    excluded: int = Field(ge=0)
    needs_review: int = Field(ge=0)
    unknown: int = Field(ge=0)
    deduplicated: int = Field(ge=0)

    @model_validator(mode="after")
    def _conserved(self) -> "PriceResearchBatchLedger":
        if self.input != self.eligible + self.excluded + self.needs_review + self.unknown + self.deduplicated:
            raise ValueError("price research batch ledger must conserve input")
        return self


class PriceResearchBatchRevision(AipContractModel):
    tenant: TenantContext
    batch_id: str
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    lifecycle: str = Field(pattern=r"^(prepared|frozen|stale)$")
    exact_refs: dict[str, PriceExactRef]
    skill_refs: list[PriceExactRef]
    items: list[PreparePriceResearchBatchItem] = Field(max_length=100)
    item_hashes: list[str]
    ledger: PriceResearchBatchLedger
    provider_call_count: int = Field(default=0, ge=0, le=0)
    research_job_count: int = Field(default=0, ge=0, le=0)
    notification_count: int = Field(default=0, ge=0, le=0)
    action_proposal_count: int = Field(default=0, ge=0, le=0)
    repricing_count: int = Field(default=0, ge=0, le=0)
    external_effect_count: int = Field(default=0, ge=0, le=0)
    prior_content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str
    created_at: datetime


class FreezePriceResearchBatchRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    expected_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    exact_refs: dict[str, PriceExactRef]


class PriceResearchContributionView(AipContractModel):
    schema_version: str = PRICE_RESEARCH_SCHEMA_VERSION
    tenant: TenantContext
    evaluated_at: datetime
    atomic_skill_refs: list[PriceExactRef]
    logic_ref: PriceExactRef | None
    primary_colleague: str = "数据参谋"
    collaborator_colleagues: list[str] = Field(default_factory=lambda: ["活动策划师", "导购顾问"])
    latest_batch: PriceResearchBatchRevision | None
    blockers: list[str]
    allowed_commands: list[str] = Field(default_factory=lambda: ["PREPARE_PRICE_RESEARCH_BATCH", "FREEZE_PRICE_RESEARCH_BATCH"])
    external_effects_allowed: bool = False


class EcommerceWorkshopPriceResearchService:
    def __init__(self, store: Any) -> None:
        self.store = store

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    def create_profile(self, scope: TenantScope, request: PriceResearchProfileRequest, actor: str, *, now: datetime | None = None) -> PriceResearchProfileRevision:
        at = now or datetime.now(UTC)
        payload = request.model_dump(mode="json", by_alias=True)
        item = PriceResearchProfileRevision(tenant=self._tenant(scope), **payload, contentHash=canonical_hash(payload), createdBy=actor, createdAt=at)
        return self.store.append_profile(scope, item)

    def normalize(self, scope: TenantScope, request: NormalizePriceObservationRequest, actor: str, *, now: datetime | None = None) -> PriceObservationRevision:
        at = now or datetime.now(UTC)
        profile = self.store.require_profile(scope, request.profile_ref)
        if request.source_license is not PriceSourceLicense.ALLOWED or request.source_kind not in profile.allowed_source_kinds:
            raise PriceResearchBlocked("PRICE_SOURCE_NOT_ALLOWED")
        if request.market not in profile.allowed_markets or request.quote_basis.currency not in profile.allowed_currencies or request.quote_basis.unit not in profile.allowed_units:
            raise PriceResearchBlocked("PRICE_QUOTE_BASIS_NOT_ALLOWED")
        if request.artifact_schema_ref != profile.output_schema_ref:
            raise PriceResearchBlocked("PRICE_ARTIFACT_SCHEMA_DRIFTED")
        age = (at - request.observed_at).total_seconds()
        if age < 0 or age > profile.freshness_seconds:
            raise PriceResearchBlocked("PRICE_SOURCE_STALE")
        missing = sorted(set(profile.required_fact_keys) - set(request.fact_keys))
        if missing:
            raise PriceResearchBlocked("PRICE_REQUIRED_FACTS_MISSING:" + ",".join(missing))
        payload = request.model_dump(mode="json", by_alias=True)
        observation_id = f"price-observation-{canonical_hash([*scope.key, request.research_artifact_ref.resource_id, request.source_sequence])[:24]}"
        item = PriceObservationRevision(
            tenant=self._tenant(scope), observationId=observation_id, profileRef=request.profile_ref,
            researchArtifactRef=request.research_artifact_ref, sourceKind=request.source_kind, market=request.market,
            amount=request.amount, quoteBasis=request.quote_basis, observedAt=request.observed_at,
            sourceSequence=request.source_sequence, originalRefs=request.original_refs,
            mergedOriginalRefs=request.merged_original_refs, factKeys=sorted(request.fact_keys),
            comparability=request.comparability, contentHash=canonical_hash(payload), createdBy=actor, createdAt=at,
        )
        return self.store.append_observation(scope, item)

    def observe_match(self, scope: TenantScope, request: CreatePriceMatchObservationRequest, *, now: datetime | None = None) -> ProductMatchObservation:
        at = now or datetime.now(UTC)
        observation = self.store.require_observation(scope, request.observation_ref)
        preliminary = observation.comparability is not PriceComparability.COMPARABLE or request.conflicting_feature_keys or not request.originals_reachable or request.score < request.policy_threshold
        payload = request.model_dump(mode="json", by_alias=True)
        confidence = PriceMatchConfidence.PRELIMINARY if preliminary else PriceMatchConfidence.CONFIRMED
        item = ProductMatchObservation(
            tenant=self._tenant(scope), matchObservationId=f"price-match-{canonical_hash([*scope.key, payload])[:24]}",
            **payload, confidence=confidence, contentHash=canonical_hash({**payload, "confidence": confidence.value}), createdAt=at,
        )
        return self.store.append_match_observation(scope, item)

    def decide_match(self, scope: TenantScope, request: DecideProductMatchRequest, actor: str, *, now: datetime | None = None) -> ProductMatchDecisionRevision:
        at = now or datetime.now(UTC)
        observation = self.store.require_match_observation(scope, request.match_observation_ref)
        if observation.confidence is PriceMatchConfidence.PRELIMINARY and request.disposition == "confirmed" and request.evidence_ref == observation.evidence_bundle_ref:
            raise PriceResearchBlocked("PRELIMINARY_MATCH_REQUIRES_ADDITIONAL_EVIDENCE")
        payload = request.model_dump(mode="json", by_alias=True)
        item = ProductMatchDecisionRevision(
            tenant=self._tenant(scope), decisionId=f"price-match-decision-{canonical_hash([*scope.key, payload, actor])[:24]}",
            **payload, decidedBy=actor, contentHash=canonical_hash({**payload, "actor": actor}), decidedAt=at,
        )
        return self.store.append_match_decision(scope, item)

    def create_policy(self, scope: TenantScope, request: MonitoringPolicyRequest, actor: str, *, now: datetime | None = None) -> MonitoringPolicyRevision:
        at = now or datetime.now(UTC)
        payload = request.model_dump(mode="json", by_alias=True)
        item = MonitoringPolicyRevision(tenant=self._tenant(scope), **payload, contentHash=canonical_hash(payload), createdBy=actor, createdAt=at)
        return self.store.append_policy(scope, item)

    def prepare_batch(self, scope: TenantScope, request: PreparePriceResearchBatchRequest, actor: str, *, now: datetime | None = None) -> PriceResearchBatchRevision:
        at = now or datetime.now(UTC)
        self.store.require_profile(scope, request.profile_ref)
        self.store.require_policy(scope, request.monitoring_policy_ref)
        counts = {item.value: 0 for item in PriceBatchDisposition}
        for item in request.items:
            observation = self.store.require_observation(scope, item.observation_ref)
            match_observation = self.store.require_match_observation(scope, item.match_observation_ref)
            decision = self.store.require_match_decision(scope, item.match_decision_ref)
            if match_observation.observation_ref != item.observation_ref or match_observation.sku_ref != item.sku_ref or decision.match_observation_ref != item.match_observation_ref:
                raise PriceResearchBlocked("PRICE_BATCH_MATCH_LINEAGE_DRIFTED")
            required = {PriceBatchDisposition.ELIGIBLE: "confirmed", PriceBatchDisposition.EXCLUDED: "rejected", PriceBatchDisposition.NEEDS_REVIEW: "needs_review", PriceBatchDisposition.UNKNOWN: "needs_review", PriceBatchDisposition.DEDUPLICATED: "confirmed"}[item.disposition]
            if decision.disposition != required or (item.disposition is PriceBatchDisposition.ELIGIBLE and observation.comparability is not PriceComparability.COMPARABLE):
                raise PriceResearchBlocked("PRICE_BATCH_DISPOSITION_DRIFTED")
            counts[item.disposition.value] += 1
        exact_refs = {
            "brief": request.brief_ref, "eval": request.eval_ref, "responsibilityPlan": request.responsibility_plan_ref,
            "profile": request.profile_ref, "monitoringPolicy": request.monitoring_policy_ref,
            "capacitySnapshot": request.capacity_snapshot_ref, "budgetSnapshot": request.budget_snapshot_ref,
            "logic": request.logic_ref, "agentBinding": request.agent_binding_ref,
        }
        payload = request.model_dump(mode="json", by_alias=True)
        item_hashes = [canonical_hash(value.model_dump(mode="json", by_alias=True)) for value in request.items]
        content_hash = canonical_hash({**payload, "itemHashes": item_hashes})
        existing = self.store.latest_batch_or_none_by_id(scope, request.batch_id)
        if existing is not None:
            if existing.lifecycle == "prepared" and existing.content_hash == content_hash:
                return existing
            raise PriceResearchConflict("PRICE_BATCH_IDEMPOTENCY_CONFLICT")
        item = PriceResearchBatchRevision(
            tenant=self._tenant(scope), batchId=request.batch_id, revision=1, version=1, lifecycle="prepared",
            exactRefs=exact_refs, skillRefs=request.skill_refs, items=request.items, itemHashes=item_hashes,
            ledger=PriceResearchBatchLedger(input=len(request.items), **counts), contentHash=content_hash, createdBy=actor, createdAt=at,
        )
        return self.store.append_batch(scope, item)

    def freeze_batch(self, scope: TenantScope, batch_id: str, request: FreezePriceResearchBatchRequest, actor: str, *, now: datetime | None = None) -> PriceResearchBatchRevision:
        at = now or datetime.now(UTC)
        current = self.store.latest_batch(scope, batch_id)
        if current.lifecycle == "frozen" and current.prior_content_hash == request.expected_content_hash:
            return current
        if current.version != request.expected_version or current.content_hash != request.expected_content_hash:
            raise PriceResearchConflict("PRICE_BATCH_EXPECTED_VERSION_OR_HASH_DRIFTED")
        expected = {key: value.model_dump(mode="json", by_alias=True) for key, value in current.exact_refs.items()}
        actual = {key: value.model_dump(mode="json", by_alias=True) for key, value in request.exact_refs.items()}
        if actual != expected or current.lifecycle != "prepared":
            raise PriceResearchBlocked("PRICE_BATCH_EXACT_REFS_OR_LIFECYCLE_DRIFTED")
        payload = current.model_dump(mode="json", by_alias=True)
        payload.update({"revision": current.revision + 1, "version": current.version + 1, "lifecycle": "frozen", "priorContentHash": current.content_hash, "contentHash": canonical_hash({"prior": current.content_hash, "exactRefs": actual, "lifecycle": "frozen"}), "createdBy": actor, "createdAt": at})
        return self.store.append_batch(scope, PriceResearchBatchRevision.model_validate(payload))

    def contribution_view(self, scope: TenantScope, *, now: datetime | None = None) -> PriceResearchContributionView:
        at = now or datetime.now(UTC)
        try:
            latest = self.store.latest_batch_or_none(scope)
        except PriceResearchBlocked as exc:
            if str(exc) != "PRICE_RESEARCH_AUTHORITY_UNAVAILABLE":
                raise
            return PriceResearchContributionView(tenant=self._tenant(scope), evaluatedAt=at, blockers=["PRICE_RESEARCH_AUTHORITY_UNAVAILABLE", "PRICE_RESEARCH_BATCH_NOT_AVAILABLE"])
        blockers = [] if latest else ["PRICE_RESEARCH_BATCH_NOT_AVAILABLE"]
        if latest and latest.lifecycle != "frozen":
            blockers.append("PRICE_RESEARCH_BATCH_NOT_FROZEN")
        return PriceResearchContributionView(
            tenant=self._tenant(scope), evaluatedAt=at, atomicSkillRefs=latest.skill_refs if latest else [],
            logicRef=latest.exact_refs.get("logic") if latest else None, latestBatch=latest, blockers=blockers,
        )


__all__ = [name for name in globals() if name.startswith(("Price", "Product", "Monitoring", "Prepare", "Freeze", "Normalize", "Create", "Decide")) or name in {"EcommerceWorkshopPriceResearchService", "canonical_hash", "PRICE_RESEARCH_SCHEMA_VERSION", "PRICE_LOGIC_ID", "PRICE_SKILL_IDS"}]
