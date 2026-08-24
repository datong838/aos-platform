from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_workshop_creator_growth_authorities import CreatorCandidateRevision, CreatorContractRevision, CreatorDeliveryRevision, CreatorMatchDecision, CreatorMatchObservation, CreatorRelationshipRevision, CreatorTermDiffRevision, OutreachBatchRevision, OutreachItemRevision, OutreachStartLedger

NOW = datetime(2026, 8, 24, tzinfo=UTC)
HASH = "a" * 64


def ref(kind, identity):
    return {"resourceType": kind, "resourceId": identity, "revision": 1, "contentHash": HASH}


def test_candidate_keeps_pii_opaque_and_evidence_unique() -> None:
    item = CreatorCandidateRevision.model_validate({"tenant": {"orgId": "org-org", "projectId": "dev-project"}, "candidateId": "c1", "revision": 1, "identityRef": ref("CreatorIdentityRevision", "i1"), "profileEvidenceRefs": [ref("ProfileEvidenceRevision", "e1")], "piiRefs": ["vault://creator/c1/contact"], "contentHash": HASH, "observedAt": NOW})
    assert item.pii_refs == ["vault://creator/c1/contact"]
    with pytest.raises(ValueError, match="unique"):
        item.model_copy(update={"pii_refs": ["same", "same"]}).model_validate(item.model_copy(update={"pii_refs": ["same", "same"]}))


def test_observation_and_decision_remain_distinct_authorities() -> None:
    observation = CreatorMatchObservation.model_validate({"tenant": {"orgId": "org-org", "projectId": "dev-project"}, "observationId": "o1", "revision": 1, "candidateRef": ref("CreatorCandidateRevision", "c1"), "policyRef": ref("CreatorMatchPolicyRevision", "p1"), "evidenceRefs": [ref("MetricEvidenceRevision", "e1")], "score": 0.82, "contentHash": HASH, "observedAt": NOW})
    decision = CreatorMatchDecision.model_validate({"tenant": observation.tenant, "decisionId": "d1", "revision": 1, "observationRef": ref("CreatorMatchObservation", "o1"), "disposition": "accepted", "reasonCode": "POLICY_THRESHOLD_MET", "decidedBy": "user:operator", "contentHash": HASH, "decidedAt": NOW})
    assert decision.observation_ref.resource_type == "CreatorMatchObservation"
    assert "contract" not in decision.model_dump_json().lower()


def test_outreach_prepare_is_exact_and_start_ledger_conserves_outcomes() -> None:
    item = OutreachItemRevision.model_validate({"tenant": {"orgId": "org-org", "projectId": "dev-project"}, "itemId": "item-1", "revision": 1, "candidateRef": ref("CreatorCandidateRevision", "c1"), "matchDecisionRef": ref("CreatorMatchDecision", "d1"), "contentHash": HASH})
    batch = OutreachBatchRevision.model_validate({"tenant": item.tenant, "batchId": "batch-1", "revision": 1, "lifecycle": "prepared", "itemRefs": [ref("OutreachItemRevision", "item-1")], "contentHash": HASH, "preparedAt": NOW})
    ledger = OutreachStartLedger.model_validate({"tenant": item.tenant, "ledgerId": "ledger-1", "revision": 1, "batchRef": ref("OutreachBatchRevision", "batch-1"), "input": 5, "accepted": 1, "applied": 1, "failed": 1, "unknown": 1, "skipped": 1, "contentHash": HASH, "recordedAt": NOW})
    assert batch.lifecycle.value == "prepared"
    assert ledger.unknown == 1
    with pytest.raises(ValueError, match="conserve"):
        OutreachStartLedger.model_validate({**ledger.model_dump(mode="json", by_alias=True), "input": 6})


def test_contract_delivery_relationship_keep_distinct_exact_lineage() -> None:
    tenant = {"orgId": "org-org", "projectId": "dev-project"}
    contract = CreatorContractRevision.model_validate({"tenant": tenant, "contractId": "contract-1", "collaborationId": "collab-1", "revision": 1, "lifecycle": "signed", "candidateRef": ref("CreatorCandidateRevision", "c1"), "termDocumentRef": "vault://contracts/contract-1/r1", "contentHash": HASH, "recordedAt": NOW})
    diff = CreatorTermDiffRevision.model_validate({"tenant": tenant, "diffId": "diff-1", "revision": 1, "fromContractRef": ref("CreatorContractRevision", "contract-1"), "toContractRef": {**ref("CreatorContractRevision", "contract-1"), "revision": 2}, "changedTermKeys": ["commissionRate"], "contentHash": HASH})
    delivery = CreatorDeliveryRevision.model_validate({"tenant": tenant, "deliveryId": "delivery-1", "collaborationId": "collab-1", "revision": 1, "signedContractRef": ref("CreatorContractRevision", "contract-1"), "outcomeEvidenceRefs": [ref("DeliveryEvidenceRevision", "e1")], "contentHash": HASH, "recordedAt": NOW})
    relationship = CreatorRelationshipRevision.model_validate({"tenant": tenant, "relationshipId": "relationship-1", "collaborationId": "collab-1", "revision": 1, "maturity": "preliminary", "deliveryRefs": [ref("CreatorDeliveryRevision", "delivery-1")], "assessmentEvidenceRefs": [ref("RelationshipEvidenceRevision", "e2")], "contentHash": HASH, "recordedAt": NOW})
    assert contract.lifecycle.value == "signed" and diff.changed_term_keys == ["commissionRate"]
    assert delivery.collaboration_id == relationship.collaboration_id
    assert relationship.maturity.value == "preliminary"
