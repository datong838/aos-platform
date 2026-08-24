from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_workshop_creator_growth_authorities import CreatorCandidateRevision, CreatorMatchDecision, CreatorMatchObservation, OutreachBatchRevision, OutreachItemRevision, OutreachStartLedger

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
