from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.ecommerce_workshop_creator_prepare import (
    CREATOR_SKILL_IDS,
    CreateCreatorMatchObservationRequest,
    CreatorDiscoveryProfileRequest,
    CreatorPrepareBlocked,
    CreatorPrepareConflict,
    DecideCreatorMatchRequest,
    EcommerceWorkshopCreatorPrepareService,
    FreezeCreatorBatchRequest,
    NormalizeCreatorArtifactRequest,
    PrepareCreatorBatchRequest,
)
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 25, 5, 0, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
OTHER = TenantScope("dev-org", "dev-project")
HASH = "a" * 64


def ref(kind: str, identity: str, content_hash: str = HASH):
    return {"resourceType": kind, "resourceId": identity, "revision": 1, "contentHash": content_hash}


class MemoryStore:
    def __init__(self) -> None:
        self.profiles = {}
        self.normalized = {}
        self.observations = {}
        self.decisions = {}
        self.batches = {}

    @staticmethod
    def _key(scope, identity): return (*scope.key, identity)

    def append_profile(self, scope, item): self.profiles[self._key(scope, item.profile_id)] = item; return item
    def append_normalizer_receipt(self, scope, item): self.normalized[self._key(scope, item.receipt_id)] = item; return item
    def append_match_observation(self, scope, item): self.observations[self._key(scope, item.observation_id)] = item; return item
    def append_match_decision(self, scope, item): self.decisions[self._key(scope, item.decision_id)] = item; return item
    def append_batch(self, scope, item): self.batches.setdefault(self._key(scope, item.batch_id), []).append(item); return item

    def require_profile(self, scope, exact): return self._require(self.profiles, scope, exact)
    def require_match_observation(self, scope, exact): return self._require(self.observations, scope, exact)
    def require_match_decision(self, scope, exact): return self._require(self.decisions, scope, exact)
    def _require(self, source, scope, exact):
        item = source.get(self._key(scope, exact.resource_id))
        if item is None or item.content_hash != exact.content_hash:
            raise CreatorPrepareBlocked("MISSING_OR_DRIFTED")
        return item

    def latest_batch(self, scope, batch_id):
        values = self.batches.get(self._key(scope, batch_id), [])
        if not values: raise CreatorPrepareBlocked("CREATOR_BATCH_NOT_FOUND")
        return values[-1]
    def latest_batch_or_none_by_id(self, scope, batch_id):
        values = self.batches.get(self._key(scope, batch_id), [])
        return values[-1] if values else None
    def latest_batch_or_none(self, scope):
        values = [rows[-1] for key, rows in self.batches.items() if key[:2] == scope.key]
        return values[-1] if values else None


def profile(service):
    return service.create_profile(
        SCOPE,
        CreatorDiscoveryProfileRequest(
            profileId="creator-profile", revision=1, allowedSourceKinds=["platform-public"],
            requiredFactKeys=["audience", "contentHistory"], outputSchemaRef=ref("SchemaRevision", "creator-output"),
            freshnessSeconds=3600, retentionDays=30, minimumDisclosure=["publicProfile"],
        ),
        "user:maker", now=NOW,
    )


def normalize(service, profile_item, *, conflict=False, license="allowed", source_at=NOW):
    return service.normalize(
        SCOPE,
        NormalizeCreatorArtifactRequest(
            profileRef=ref("CreatorDiscoveryProfileRevision", profile_item.profile_id, profile_item.content_hash),
            researchArtifactRef=ref("ResearchArtifactRevision", "artifact-1"), sourceKind="platform-public",
            sourceLicense=license, sourceFreshAt=source_at, artifactSchemaRef=ref("SchemaRevision", "creator-output"),
            artifactHash="b" * 64, originalRecordRefs=[ref("SourceRecordRevision", "source-1"), ref("SourceRecordRevision", "source-2")],
            stableIdentityKeys=["platform:opaque-1"], conflictingIdentityKeys=["alias:conflict"] if conflict else [],
            factKeys=["audience", "contentHistory"], piiRefs=["vault://creator/opaque-1"],
        ),
        "user:maker", now=NOW,
    )


def observation(service, candidate_id, *, conflict=False, score=0.8, threshold=0.7, missing=None):
    return service.observe_match(
        SCOPE,
        CreateCreatorMatchObservationRequest(
            candidateRef=ref("CreatorCandidateRevision", candidate_id), evidenceBundleRef=ref("EvidenceBundleRevision", "evidence-1"),
            featureSchemaRef=ref("FeatureSchemaRevision", "features-1"), logicRef=ref("LogicPublicationRevision", "ecommerce-creator-match"),
            policyRef=ref("CreatorMatchPolicyRevision", "policy-1"), score=score, policyThreshold=threshold,
            featureSummaries={"audienceFit": score}, missingFactKeys=missing or [], identityStatus="conflict" if conflict else "resolved",
        ),
        now=NOW,
    )


def decision(service, observation_item, disposition="accepted"):
    return service.decide_match(
        SCOPE,
        DecideCreatorMatchRequest(
            observationRef=ref("CreatorPreparedMatchObservation", observation_item.observation_id, observation_item.content_hash),
            decision=disposition, reasonCode="HUMAN_POLICY_REVIEWED",
        ),
        "user:checker", now=NOW,
    )


def batch_request(observation_item, decision_item, *, disposition="eligible", frequency=True, capacity=True, budget=True):
    return PrepareCreatorBatchRequest(
        batchId="batch-1", briefRef=ref("TaskBriefRevision", "brief-1"), evalRef=ref("EvalContractRevision", "eval-1"),
        responsibilityPlanRef=ref("ResponsibilityPlanRevision", "plan-1"), frequencyPolicyRef=ref("FrequencyPolicyRevision", "frequency-1"),
        capacitySnapshotRef=ref("CapacitySnapshotRevision", "capacity-1"), budgetSnapshotRef=ref("BudgetSnapshotRevision", "budget-1"),
        skillRefs=[ref("SkillRevision", identity) for identity in CREATOR_SKILL_IDS],
        logicRef=ref("LogicPublicationRevision", "ecommerce-creator-match"), agentBindingRef=ref("AgentBindingRevision", "shopping-advisor-creator"),
        items=[{
            "candidateRef": ref("CreatorCandidateRevision", "candidate-1"), "evidenceBundleRef": ref("EvidenceBundleRevision", "evidence-1"),
            "matchObservationRef": ref("CreatorPreparedMatchObservation", observation_item.observation_id, observation_item.content_hash),
            "matchDecisionRef": ref("CreatorPreparedMatchDecision", decision_item.decision_id, decision_item.content_hash),
            "disposition": disposition, "reasonCodes": [] if disposition == "eligible" else ["POLICY_REVIEW_REQUIRED"],
            "frequencyEligible": frequency, "capacityEligible": capacity, "budgetEligible": budget,
        }],
    )


def test_discovery_normalizer_preserves_originals_and_fails_license_freshness_closed():
    service = EcommerceWorkshopCreatorPrepareService(MemoryStore())
    profile_item = profile(service)
    receipt = normalize(service, profile_item, conflict=True)
    assert receipt.identity_status.value == "conflict"
    assert len(receipt.original_record_refs) == 2
    assert receipt.pii_refs == ["vault://creator/opaque-1"]
    with pytest.raises(CreatorPrepareBlocked, match="LICENSE"):
        normalize(service, profile_item, license="unknown")
    with pytest.raises(CreatorPrepareBlocked, match="STALE"):
        normalize(service, profile_item, source_at=NOW - timedelta(hours=2))


def test_match_preliminary_cannot_reject_and_observation_decision_remain_separate():
    service = EcommerceWorkshopCreatorPrepareService(MemoryStore())
    observed = observation(service, "candidate-1", conflict=True, score=0.2)
    assert observed.confidence.value == "preliminary"
    with pytest.raises(CreatorPrepareBlocked, match="PRELIMINARY"):
        decision(service, observed, "rejected")
    decided = decision(service, observed, "needs_review")
    assert decided.observation_ref.resource_id == observed.observation_id
    assert "contract" not in decided.model_dump_json().lower()


def test_batch_prepare_freeze_is_conserved_idempotent_and_has_zero_effects():
    store = MemoryStore(); service = EcommerceWorkshopCreatorPrepareService(store)
    observed = observation(service, "candidate-1")
    decided = decision(service, observed)
    request = batch_request(observed, decided)
    prepared = service.prepare_batch(SCOPE, request, "user:maker", now=NOW)
    replay = service.prepare_batch(SCOPE, request, "user:maker", now=NOW)
    assert replay.content_hash == prepared.content_hash
    assert prepared.ledger.input == prepared.ledger.eligible == 1
    assert prepared.external_effect_count == prepared.action_proposal_count == prepared.execution_lease_count == 0
    frozen = service.freeze_batch(
        SCOPE, prepared.batch_id,
        FreezeCreatorBatchRequest(expectedVersion=1, expectedContentHash=prepared.content_hash, exactRefs=prepared.exact_refs),
        "user:checker", now=NOW,
    )
    assert frozen.lifecycle == "frozen" and frozen.revision == 2 and frozen.version == 2
    assert service.freeze_batch(SCOPE, prepared.batch_id, FreezeCreatorBatchRequest(expectedVersion=1, expectedContentHash=prepared.content_hash, exactRefs=prepared.exact_refs), "user:checker", now=NOW) == frozen
    with pytest.raises(CreatorPrepareConflict, match="IDEMPOTENCY"):
        service.prepare_batch(SCOPE, request.model_copy(update={"budget_snapshot_ref": request.budget_snapshot_ref.model_copy(update={"content_hash": "c" * 64})}), "user:maker", now=NOW)


def test_frequency_capacity_budget_and_tenant_are_fail_closed():
    service = EcommerceWorkshopCreatorPrepareService(MemoryStore())
    observed = observation(service, "candidate-1"); decided = decision(service, observed)
    with pytest.raises(ValueError, match="frequency/capacity/budget"):
        batch_request(observed, decided, frequency=False)
    assert service.contribution_view(OTHER, now=NOW).blockers == ["CREATOR_BATCH_PREPARATION_NOT_AVAILABLE"]
    view = service.contribution_view(SCOPE, now=NOW)
    assert view.primary_colleague == "导购顾问"
    assert view.external_effects_allowed is False
    assert "START" not in " ".join(view.allowed_commands)


def test_batch_prepare_requires_exact_decision_lineage_and_disposition():
    store = MemoryStore(); service = EcommerceWorkshopCreatorPrepareService(store)
    observed = observation(service, "candidate-1")
    accepted = decision(service, observed, "accepted")
    with pytest.raises(CreatorPrepareBlocked, match="DISPOSITION_DRIFTED"):
        service.prepare_batch(SCOPE, batch_request(observed, accepted, disposition="needs_review"), "user:maker", now=NOW)

    drifted = accepted.model_copy(update={"observation_ref": accepted.observation_ref.model_copy(update={"resource_id": "other-observation"})})
    store.decisions[store._key(SCOPE, accepted.decision_id)] = drifted
    with pytest.raises(CreatorPrepareBlocked, match="LINEAGE_DRIFTED"):
        service.prepare_batch(SCOPE, batch_request(observed, drifted), "user:maker", now=NOW)


@pytest.mark.parametrize(
    ("decision_disposition", "batch_disposition", "ledger_field"),
    [("needs_review", "unknown", "unknown"), ("accepted", "deduplicated", "deduplicated")],
)
def test_unknown_and_deduplicated_items_remain_conserved(decision_disposition, batch_disposition, ledger_field):
    service = EcommerceWorkshopCreatorPrepareService(MemoryStore())
    observed = observation(service, "candidate-1")
    decided = decision(service, observed, decision_disposition)
    prepared = service.prepare_batch(SCOPE, batch_request(observed, decided, disposition=batch_disposition), "user:maker", now=NOW)
    assert prepared.ledger.input == 1
    assert getattr(prepared.ledger, ledger_field) == 1
