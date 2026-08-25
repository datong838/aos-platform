from datetime import UTC, datetime, timedelta

import pytest

from aos_api.ecommerce_workshop_price_governance_contracts import PriceExactRef, PriceQuoteBasis
from aos_api.ecommerce_workshop_price_research import (
    PRICE_LOGIC_ID,
    PRICE_SKILL_IDS,
    CreatePriceMatchObservationRequest,
    DecideProductMatchRequest,
    EcommerceWorkshopPriceResearchService,
    FreezePriceResearchBatchRequest,
    MonitoringPolicyRequest,
    NormalizePriceObservationRequest,
    PreparePriceResearchBatchItem,
    PreparePriceResearchBatchRequest,
    PriceBatchDisposition,
    PriceComparability,
    PriceMatchConfidence,
    PriceResearchBlocked,
    PriceResearchConflict,
    PriceResearchProfileRequest,
    PriceSourceLicense,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 25, 7, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def ref(kind: str, identity: str, digest: str = "a") -> PriceExactRef:
    return PriceExactRef(resourceType=kind, resourceId=identity, revision=1, contentHash=f"sha256:{digest * 64}", receiptId=f"receipt-{identity}")


class Store:
    def __init__(self) -> None:
        self.profiles = {}
        self.observations = {}
        self.match_observations = {}
        self.decisions = {}
        self.policies = {}
        self.batches = {}

    def append_profile(self, _scope, item): self.profiles[item.profile_id] = item; return item
    def append_observation(self, _scope, item): self.observations[item.observation_id] = item; return item
    def append_match_observation(self, _scope, item): self.match_observations[item.match_observation_id] = item; return item
    def append_match_decision(self, _scope, item): self.decisions[item.decision_id] = item; return item
    def append_policy(self, _scope, item): self.policies[item.policy_id] = item; return item
    def append_batch(self, _scope, item): self.batches.setdefault(item.batch_id, []).append(item); return item
    def require_profile(self, _scope, exact): return self.profiles[exact.resource_id]
    def require_observation(self, _scope, exact): return self.observations[exact.resource_id]
    def require_match_observation(self, _scope, exact): return self.match_observations[exact.resource_id]
    def require_match_decision(self, _scope, exact): return self.decisions[exact.resource_id]
    def require_policy(self, _scope, exact): return self.policies[exact.resource_id]
    def latest_batch(self, _scope, batch_id): return self.batches[batch_id][-1]
    def latest_batch_or_none_by_id(self, _scope, batch_id): return self.batches.get(batch_id, [None])[-1]
    def latest_batch_or_none(self, _scope): return next((items[-1] for items in reversed(list(self.batches.values()))), None)


def exact(item, kind: str, identity_field: str) -> PriceExactRef:
    return PriceExactRef(resourceType=kind, resourceId=getattr(item, identity_field), revision=item.revision, contentHash=f"sha256:{item.content_hash}", receiptId=f"receipt-{getattr(item, identity_field)}")


def build_chain():
    store = Store(); service = EcommerceWorkshopPriceResearchService(store)
    profile = service.create_profile(SCOPE, PriceResearchProfileRequest(
        profileId="price-profile", revision=1, allowedSourceKinds=["licensed_feed"], allowedMarkets=["CN"],
        allowedCurrencies=["CNY"], allowedUnits=["piece"], requiredFactKeys=["amount", "sku", "basis"],
        outputSchemaRef=ref("SchemaRevision", "price-schema"), freshnessSeconds=3600, retentionDays=30,
        rateLimitPerHour=100, capacityLimit=1000,
    ), "operator", now=NOW)
    profile_ref = exact(profile, "PriceResearchProfileRevision", "profile_id")
    basis = PriceQuoteBasis(
        basis="landed", skuRef=ref("ProductSkuRevision", "sku-1"), quantity=1, unit="piece", currency="CNY",
        tax="included", shipping="included", promotionCondition="none", effectiveFrom=NOW - timedelta(hours=1), effectiveUntil=NOW + timedelta(days=1),
    )
    observation = service.normalize(SCOPE, NormalizePriceObservationRequest(
        profileRef=profile_ref, researchArtifactRef=ref("ResearchArtifactRevision", "artifact-1"), sourceKind="licensed_feed",
        sourceLicense=PriceSourceLicense.ALLOWED, market="CN", amount=99.0, quoteBasis=basis, observedAt=NOW - timedelta(minutes=5),
        sourceSequence=1, artifactSchemaRef=profile.output_schema_ref, originalRefs=[ref("PriceOriginalRevision", "original-1")],
        factKeys=["amount", "sku", "basis"], comparability=PriceComparability.COMPARABLE,
    ), "operator", now=NOW)
    observation_ref = exact(observation, "PriceObservationRevision", "observation_id")
    match = service.observe_match(SCOPE, CreatePriceMatchObservationRequest(
        observationRef=observation_ref, skuRef=basis.sku_ref, evidenceBundleRef=ref("EvidenceBundleRevision", "evidence-1"),
        featureSchemaRef=ref("FeatureSchemaRevision", "features-1"), logicRef=ref("LogicPublicationRevision", PRICE_LOGIC_ID),
        policyRef=ref("ProductMatchPolicyRevision", "match-policy"), score=.98, policyThreshold=.9,
        featureSummaries={"sku": 1.0, "unit": 1.0}, originalsReachable=True,
    ), now=NOW)
    match_ref = exact(match, "ProductMatchObservation", "match_observation_id")
    decision = service.decide_match(SCOPE, DecideProductMatchRequest(
        matchObservationRef=match_ref, disposition="confirmed", reasonCode="EXACT_SKU_MATCH",
        evidenceRef=ref("EvidenceBundleRevision", "evidence-2"),
    ), "reviewer", now=NOW)
    decision_ref = exact(decision, "ProductMatchDecisionRevision", "decision_id")
    policy = service.create_policy(SCOPE, MonitoringPolicyRequest(
        policyId="monitoring-policy", revision=1, scopeRefs=[basis.sku_ref], basis="landed", currency="CNY", unit="piece",
        toleranceRatio=.1, freshnessSeconds=3600, minimumOriginals=1, minimumMatchConfidence=PriceMatchConfidence.CONFIRMED,
        evalRef=ref("EvalContractRevision", "eval-1"),
    ), "operator", now=NOW)
    return store, service, profile_ref, observation_ref, match_ref, decision_ref, exact(policy, "MonitoringPolicyRevision", "policy_id"), basis.sku_ref


def test_full_prepare_freeze_conserves_items_and_has_zero_side_effects():
    store, service, profile_ref, observation_ref, match_ref, decision_ref, policy_ref, sku_ref = build_chain()
    request = PreparePriceResearchBatchRequest(
        batchId="price-batch-1", briefRef=ref("TaskBriefRevision", "brief"), evalRef=ref("EvalContractRevision", "eval"),
        responsibilityPlanRef=ref("ResponsibilityPlanRevision", "responsibility"), profileRef=profile_ref,
        monitoringPolicyRef=policy_ref, capacitySnapshotRef=ref("CapacitySnapshotRevision", "capacity"),
        budgetSnapshotRef=ref("BudgetSnapshotRevision", "budget"),
        skillRefs=[ref("SkillRevision", item, chr(97 + index)) for index, item in enumerate(PRICE_SKILL_IDS)],
        logicRef=ref("LogicPublicationRevision", PRICE_LOGIC_ID), agentBindingRef=ref("AgentBindingRevision", "data-advisor"),
        items=[PreparePriceResearchBatchItem(
            skuRef=sku_ref, observationRef=observation_ref, matchObservationRef=match_ref, matchDecisionRef=decision_ref,
            disposition=PriceBatchDisposition.ELIGIBLE, licenseEligible=True, freshnessEligible=True, rateEligible=True,
            capacityEligible=True, budgetEligible=True,
        )],
    )
    prepared = service.prepare_batch(SCOPE, request, "operator", now=NOW)
    assert prepared.ledger.input == prepared.ledger.eligible == 1
    assert prepared.provider_call_count == prepared.research_job_count == prepared.notification_count == 0
    assert prepared.action_proposal_count == prepared.repricing_count == prepared.external_effect_count == 0
    frozen = service.freeze_batch(SCOPE, prepared.batch_id, FreezePriceResearchBatchRequest(
        expectedVersion=prepared.version, expectedContentHash=prepared.content_hash, exactRefs=prepared.exact_refs,
    ), "operator", now=NOW)
    assert frozen.lifecycle == "frozen" and frozen.version == 2 and frozen.prior_content_hash == prepared.content_hash
    view = service.contribution_view(SCOPE, now=NOW)
    assert view.primary_colleague == "数据参谋"
    assert view.collaborator_colleagues == ["活动策划师", "导购顾问"]
    assert {item.resource_id for item in view.atomic_skill_refs} == set(PRICE_SKILL_IDS)
    assert view.external_effects_allowed is False


def test_profile_rejects_arbitrary_url_and_unknown_never_exposes_amount():
    with pytest.raises(ValueError, match="arbitrary URLs"):
        PriceResearchProfileRequest(
            profileId="p", revision=1, allowedSourceKinds=["feed"], allowedMarkets=["CN"], allowedCurrencies=["CNY"],
            allowedUnits=["piece"], requiredFactKeys=["amount"], outputSchemaRef=ref("SchemaRevision", "schema"),
            freshnessSeconds=60, retentionDays=1, rateLimitPerHour=1, capacityLimit=1, allowArbitraryUrls=True,
        )
    with pytest.raises(ValueError, match="unknown observation"):
        NormalizePriceObservationRequest(
            profileRef=ref("PriceResearchProfileRevision", "p"), researchArtifactRef=ref("ResearchArtifactRevision", "a"),
            sourceKind="feed", sourceLicense="allowed", market="CN", amount=0,
            quoteBasis=PriceQuoteBasis(basis="list", skuRef=ref("ProductSkuRevision", "sku"), quantity=1, unit="piece", currency="CNY", tax="unknown", shipping="unknown", promotionCondition="none", effectiveFrom=NOW),
            observedAt=NOW, sourceSequence=1, artifactSchemaRef=ref("SchemaRevision", "schema"), originalRefs=[ref("PriceOriginalRevision", "o")], factKeys=["amount"], comparability="unknown",
        )


def test_preliminary_match_requires_new_evidence_and_batch_is_cas_guarded():
    store, service, _, observation_ref, _, _, _, sku_ref = build_chain()
    preliminary = service.observe_match(SCOPE, CreatePriceMatchObservationRequest(
        observationRef=observation_ref, skuRef=sku_ref, evidenceBundleRef=ref("EvidenceBundleRevision", "same"),
        featureSchemaRef=ref("FeatureSchemaRevision", "features"), logicRef=ref("LogicPublicationRevision", PRICE_LOGIC_ID),
        policyRef=ref("ProductMatchPolicyRevision", "policy"), score=.4, policyThreshold=.9,
        featureSummaries={"sku": .4}, conflictingFeatureKeys=["spec"], originalsReachable=True,
    ), now=NOW)
    with pytest.raises(PriceResearchBlocked, match="ADDITIONAL_EVIDENCE"):
        service.decide_match(SCOPE, DecideProductMatchRequest(
            matchObservationRef=exact(preliminary, "ProductMatchObservation", "match_observation_id"), disposition="confirmed",
            reasonCode="MANUAL_CONFIRM", evidenceRef=preliminary.evidence_bundle_ref,
        ), "reviewer", now=NOW)
    assert preliminary.confidence is PriceMatchConfidence.PRELIMINARY


def test_contribution_fails_closed_when_authority_is_absent():
    view = EcommerceWorkshopPriceResearchService(Store()).contribution_view(SCOPE, now=NOW)
    assert view.latest_batch is None
    assert view.blockers == ["PRICE_RESEARCH_BATCH_NOT_AVAILABLE"]
    assert view.allowed_commands == ["PREPARE_PRICE_RESEARCH_BATCH", "FREEZE_PRICE_RESEARCH_BATCH"]
