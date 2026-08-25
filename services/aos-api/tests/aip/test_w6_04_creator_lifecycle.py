from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.ecommerce_workshop_creator_lifecycle import (
    CreateCreatorContractRevisionRequest,
    CreateCreatorRelationshipRevisionRequest,
    CreatorActionKind,
    CreatorLifecycleBlocked,
    CreatorLifecycleConflict,
    EcommerceWorkshopCreatorLifecycleService,
    RecordCreatorDeliveryRequest,
    RecordCreatorLaneObservationRequest,
    StartCreatorBatchRequest,
)
from aos_api.ecommerce_workshop_creator_prepare import (
    CREATOR_SKILL_IDS,
    CreatorBatchCountLedger,
    CreatorBatchPreparationRevision,
    PrepareCreatorBatchItem,
    canonical_hash,
)
from aos_api.aip_contracts import TenantContext
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 25, 8, 0, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
OTHER = TenantScope("dev-org", "dev-project")
HASH = "a" * 64


def ref(kind: str, identity: str, content_hash: str = HASH, revision: int = 1):
    return {"resourceType": kind, "resourceId": identity, "revision": revision, "contentHash": content_hash}


def prepared_item():
    return PrepareCreatorBatchItem(
        candidateRef=ref("CreatorCandidateRevision", "candidate-1"),
        evidenceBundleRef=ref("EvidenceBundleRevision", "evidence-1"),
        matchObservationRef=ref("CreatorPreparedMatchObservation", "observation-1"),
        matchDecisionRef=ref("CreatorPreparedMatchDecision", "decision-1"),
        disposition="eligible", reasonCodes=[], frequencyEligible=True, capacityEligible=True, budgetEligible=True,
    )


def frozen_batch(*, items=True, version=2):
    item = prepared_item()
    payload = item.model_dump(mode="json", by_alias=True)
    return CreatorBatchPreparationRevision(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        batchId="batch-1", revision=2, version=version, lifecycle="frozen",
        exactRefs={"logic": ref("LogicPublicationRevision", "ecommerce-creator-match")},
        skillRefs=[ref("SkillRevision", skill) for skill in CREATOR_SKILL_IDS],
        items=[item] if items else [], itemHashes=[canonical_hash(payload)],
        ledger=CreatorBatchCountLedger(input=1, eligible=1, excluded=0, needsReview=0, unknown=0, deduplicated=0),
        priorContentHash="b" * 64, contentHash="c" * 64, createdBy="user:maker", createdAt=NOW,
    )


def lanes():
    result = []
    for kind in CreatorActionKind:
        result.append({
            "candidateRef": ref("CreatorCandidateRevision", "candidate-1"),
            "actionKind": kind.value,
            "actionTypeRef": ref("ActionTypeRevision", f"ecommerce.creator.{kind.value}"),
            "impactPreviewRef": ref("ImpactPreviewRevision", f"impact-{kind.value}"),
            "adapterCapabilityRef": ref("AdapterCapabilityRevision", f"adapter-{kind.value}"),
            "accountBindingRef": ref("AccountBindingRevision", f"account-{kind.value}"),
            "budgetReservationRef": ref("ActionBudgetReservationRevision", f"budget-{kind.value}"),
            "approvalPolicyRef": ref("ApprovalPolicyRevision", f"approval-{kind.value}"),
        })
    return result


class BatchStore:
    def __init__(self, batch): self.batch = batch
    def latest_batch(self, scope, batch_id):
        if scope != SCOPE or batch_id != self.batch.batch_id: raise CreatorLifecycleBlocked("CREATOR_BATCH_NOT_FOUND")
        return self.batch


class MemoryLifecycleStore:
    def __init__(self):
        self.starts = {}; self.observations = []; self.contracts = []; self.deliveries = []; self.relationships = []
        self.receipts = {}

    @staticmethod
    def _assert(scope, item):
        assert (item.tenant.org_id, item.tenant.project_id) == scope.key

    def append_start(self, scope, batch_id, item): self._assert(scope, item); self.starts[(*scope.key, batch_id)] = item; return item
    def latest_start_or_none(self, scope, batch_id): return self.starts.get((*scope.key, batch_id))
    def latest_start_for_tenant_or_none(self, scope): return next((item for key, item in self.starts.items() if key[:2] == scope.key), None)
    def require_start(self, scope, exact):
        item = next((item for key, item in self.starts.items() if key[:2] == scope.key and item.decision_id == exact.resource_id), None)
        if item is None or item.content_hash != exact.content_hash: raise CreatorLifecycleBlocked("CREATOR_START_DECISION_MISSING_OR_DRIFTED")
        return item
    def require_action_receipt(self, scope, exact, binding_hash):
        if self.receipts.get((*scope.key, exact.resource_id)) != (exact.content_hash, binding_hash): raise CreatorLifecycleBlocked("CREATOR_ACTION_RECEIPT_MISSING_OR_BINDING_DRIFTED")
    def require_lane_authorities(self, scope, lane): assert scope == SCOPE and lane.action_type_ref.content_hash == HASH
    def append_lane_observation(self, scope, item): self._assert(scope, item); self.observations.append(item); return item
    def list_lane_observations(self, scope, decision_id): return [item for item in self.observations if item.start_decision_ref.resource_id == decision_id and (item.tenant.org_id, item.tenant.project_id) == scope.key]
    def append_contract(self, scope, item): self._assert(scope, item); self.contracts.append(item); return item
    def require_contract(self, scope, exact):
        item = next((item for item in self.contracts if item.collaboration_id == exact.resource_id and item.revision == exact.revision and (item.tenant.org_id, item.tenant.project_id) == scope.key), None)
        if item is None or item.content_hash != exact.content_hash: raise CreatorLifecycleBlocked("CREATOR_CONTRACT_MISSING_OR_DRIFTED")
        return item
    def append_delivery(self, scope, item): self._assert(scope, item); self.deliveries.append(item); return item
    def require_delivery(self, scope, exact):
        item = next((item for item in self.deliveries if item.observation_id == exact.resource_id and (item.tenant.org_id, item.tenant.project_id) == scope.key), None)
        if item is None or item.content_hash != exact.content_hash: raise CreatorLifecycleBlocked("CREATOR_DELIVERY_MISSING_OR_DRIFTED")
        return item
    def append_relationship(self, scope, item): self._assert(scope, item); self.relationships.append(item); return item
    def latest_relationship_or_none(self, scope, relationship_id): return next((item for item in reversed(self.relationships) if item.relationship_id == relationship_id and (item.tenant.org_id, item.tenant.project_id) == scope.key), None)
    def list_contracts(self, scope): return [item for item in self.contracts if (item.tenant.org_id, item.tenant.project_id) == scope.key]
    def list_deliveries(self, scope): return [item for item in self.deliveries if (item.tenant.org_id, item.tenant.project_id) == scope.key]
    def list_relationships(self, scope): return [item for item in self.relationships if (item.tenant.org_id, item.tenant.project_id) == scope.key]


def start_request(batch):
    return StartCreatorBatchRequest(expectedVersion=batch.version, expectedContentHash=batch.content_hash, lanes=lanes(), reason="用户显式进入治理链")


def start_service(*, items=True):
    batch = frozen_batch(items=items); store = MemoryLifecycleStore()
    return EcommerceWorkshopCreatorLifecycleService(store, BatchStore(batch)), store, batch


def test_explicit_start_compiles_four_independent_lanes_without_external_effect():
    service, store, batch = start_service()
    started = service.start_batch(SCOPE, batch.batch_id, start_request(batch), "user:maker", now=NOW)
    assert started.ledger.eligible_items == 1 and started.ledger.lanes == started.ledger.prepared == 4
    assert started.external_effect_count == started.ledger.completed == 0
    assert len({lane.binding_hash for lane in started.lanes}) == 4
    assert service.start_batch(SCOPE, batch.batch_id, start_request(batch), "user:maker", now=NOW) == started
    assert store.observations == []


def test_start_fails_closed_on_legacy_items_cas_and_lane_coverage():
    service, _store, batch = start_service(items=False)
    with pytest.raises(CreatorLifecycleBlocked, match="ITEMS_NOT_AVAILABLE"):
        service.start_batch(SCOPE, batch.batch_id, start_request(batch), "user:maker", now=NOW)
    service, _store, batch = start_service()
    with pytest.raises(CreatorLifecycleConflict, match="EXPECTED_VERSION_OR_HASH_DRIFTED"):
        service.start_batch(SCOPE, batch.batch_id, start_request(batch).model_copy(update={"expected_version": 99}), "user:maker", now=NOW)
    with pytest.raises(CreatorLifecycleBlocked, match="LANE_COVERAGE_DRIFTED"):
        service.start_batch(SCOPE, batch.batch_id, start_request(batch).model_copy(update={"lanes": start_request(batch).lanes[:-1]}), "user:maker", now=NOW)


def test_partial_unknown_is_not_completed_and_receipt_binding_is_exact():
    service, store, batch = start_service()
    started = service.start_batch(SCOPE, batch.batch_id, start_request(batch), "user:maker", now=NOW)
    lane = started.lanes[0]
    receipt_hash = "d" * 64
    receipt = ref("ActionReceipt", "receipt-1", receipt_hash)
    store.receipts[(*SCOPE.key, "receipt-1")] = (receipt_hash, lane.binding_hash)
    observation = service.record_lane_observation(SCOPE, RecordCreatorLaneObservationRequest(
        startDecisionRef=ref("CreatorBatchStartDecisionRevision", started.decision_id, started.content_hash),
        laneId=lane.lane_id, actionReceiptRef=receipt, outcome="unknown", observedAt=NOW,
    ))
    assert observation.outcome.value == "unknown"
    view = service.view(SCOPE, now=NOW)
    assert view.ledger.unknown == 1 and view.ledger.prepared == 3 and view.ledger.completed == 0
    with pytest.raises(CreatorLifecycleBlocked, match="RECEIPT_MISSING_OR_BINDING_DRIFTED"):
        service.record_lane_observation(SCOPE, RecordCreatorLaneObservationRequest(
            startDecisionRef=ref("CreatorBatchStartDecisionRevision", started.decision_id, started.content_hash),
            laneId=started.lanes[1].lane_id, actionReceiptRef=receipt, outcome="applied", observedAt=NOW,
        ))


def test_contract_delivery_relationship_share_lineage_and_maturity_window_is_closed():
    service, store, batch = start_service()
    started = service.start_batch(SCOPE, batch.batch_id, start_request(batch), "user:maker", now=NOW)
    start_ref = ref("CreatorBatchStartDecisionRevision", started.decision_id, started.content_hash)
    contract = service.create_contract(SCOPE, CreateCreatorContractRevisionRequest(
        collaborationId="collab-1", candidateRef=ref("CreatorCandidateRevision", "candidate-1"), startDecisionRef=start_ref,
        termsHash="e" * 64, monetaryTermsRef=ref("ProtectedMonetaryTermsRevision", "terms-1"), lifecycle="draft", diffFields=["scope"],
    ), "user:maker", now=NOW)
    contract_ref = ref("CreatorContractRevision", contract.collaboration_id, contract.content_hash, contract.revision)
    delivery = service.record_delivery(SCOPE, RecordCreatorDeliveryRequest(
        collaborationId="collab-1", contractRef=contract_ref, deliveryRef=ref("DeliveryRevision", "delivery-1"),
        evidenceBundleRef=ref("EvidenceBundleRevision", "delivery-evidence-1"), sequence=1, status="accepted", observedAt=NOW,
    ))
    request = CreateCreatorRelationshipRevisionRequest(
        relationshipId="relationship-1", collaborationId="collab-1", contractRef=contract_ref,
        deliveryObservationRefs=[ref("CreatorDeliveryObservation", delivery.observation_id, delivery.content_hash)],
        maturityPolicyRef=ref("RelationshipMaturityPolicyRevision", "maturity-1"), maturityWindowEndsAt=NOW + timedelta(days=30), status="mature",
    )
    with pytest.raises(CreatorLifecycleBlocked, match="MATURITY_WINDOW_NOT_SATISFIED"):
        service.create_relationship(SCOPE, request, now=NOW)
    preliminary = service.create_relationship(SCOPE, request.model_copy(update={"status": "preliminary"}), now=NOW)
    assert preliminary.collaboration_id == contract.collaboration_id == delivery.collaboration_id
    assert service.view(OTHER, now=NOW).latest_start is None
