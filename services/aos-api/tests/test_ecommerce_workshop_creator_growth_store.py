from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_workshop_creator_growth_authorities import CreatorCandidateRevision, OutreachStartLedger
from aos_api.ecommerce_workshop_creator_growth_store import CreatorAuthorityReadError, EcommerceWorkshopCreatorGrowthStore
from aos_api.ecommerce_workshop_creator_lifecycle import CreatorContractRevision
from aos_api.ecommerce_workshop_creator_prepare import CreatorBatchPreparationRevision, CreatorNormalizerReceipt
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 24, tzinfo=UTC)
HASH = "a" * 64
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")


class Cursor:
    def __init__(self, value=None): self.value = value
    def fetchall(self): return self.value


class Connection:
    def __init__(self, rows=()): self.rows, self.calls, self.commits = list(rows), [], 0
    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return Cursor(self.rows.pop(0) if sql.lstrip().startswith("SELECT") else None)
    def commit(self): self.commits += 1


def factory(connection):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection
    return connect


def candidate(org="org-org"):
    return CreatorCandidateRevision.model_validate({"tenant": {"orgId": org, "projectId": "dev-project"}, "candidateId": "c1", "revision": 1, "identityRef": {"resourceType": "CreatorIdentityRevision", "resourceId": "i1", "revision": 1, "contentHash": HASH}, "profileEvidenceRefs": [{"resourceType": "ProfileEvidenceRevision", "resourceId": "e1", "revision": 1, "contentHash": HASH}], "contentHash": HASH, "observedAt": NOW})


def test_append_is_tenant_bound_and_never_updates() -> None:
    connection = Connection()
    EcommerceWorkshopCreatorGrowthStore(factory(connection)).append_candidate(SCOPE, candidate(), "receipt-1")
    assert connection.commits == 1
    assert "INSERT INTO ecommerce_creator_candidate_revision" in connection.calls[0][0]
    assert "UPDATE" not in connection.calls[0][0]
    with pytest.raises(ValueError, match="tenant"):
        EcommerceWorkshopCreatorGrowthStore(factory(Connection())).append_candidate(SCOPE, candidate("dev-org"), "receipt-2")


def test_bounded_read_is_repeatable_and_fails_closed_on_tenant_drift() -> None:
    payload = CreatorNormalizerReceipt.model_validate({
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "receiptId": "receipt-1", "candidateId": "c1", "revision": 1,
        "profileRef": {"resourceType": "CreatorDiscoveryProfileRevision", "resourceId": "profile-1", "revision": 1, "contentHash": HASH},
        "researchArtifactRef": {"resourceType": "ResearchArtifactRevision", "resourceId": "research-1", "revision": 1, "contentHash": HASH},
        "originalRecordRefs": [{"resourceType": "SourceRecordRevision", "resourceId": "source-1", "revision": 1, "contentHash": HASH}],
        "identityStatus": "resolved", "identityKeyHash": HASH, "conflictCodes": [], "factKeys": ["channel"], "piiRefs": [],
        "contentHash": HASH, "createdBy": "tester", "createdAt": NOW,
    }).model_dump(mode="json", by_alias=True)
    connection = Connection(rows=[[{"org_id": "org-org", "project_id": "dev-project", "authority_receipt_id": "receipt-1", "content_hash": HASH, "authority_data": payload}]])
    write_connection = Connection()
    rows = EcommerceWorkshopCreatorGrowthStore(
        factory(write_connection), factory(connection)
    ).list_candidates(SCOPE, cutoff=NOW, limit=1)
    assert rows[0].receipt_id == "receipt-1"
    assert connection.calls[0][0].startswith("SELECT")
    assert write_connection.calls == []
    drift = Connection(rows=[[{"org_id": "dev-org", "project_id": "dev-project", "authority_receipt_id": "receipt-1", "content_hash": HASH, "authority_data": payload}]])
    with pytest.raises(CreatorAuthorityReadError):
        EcommerceWorkshopCreatorGrowthStore(
            factory(Connection()), factory(drift)
        ).list_candidates(SCOPE, cutoff=NOW)


def test_start_ledger_append_has_no_provider_or_update_side_effect() -> None:
    ledger = OutreachStartLedger.model_validate({"tenant": {"orgId": "org-org", "projectId": "dev-project"}, "ledgerId": "ledger-1", "revision": 1, "batchRef": {"resourceType": "OutreachBatchRevision", "resourceId": "batch-1", "revision": 1, "contentHash": HASH}, "input": 1, "accepted": 0, "applied": 0, "failed": 0, "unknown": 1, "skipped": 0, "contentHash": HASH, "recordedAt": NOW})
    connection = Connection()
    EcommerceWorkshopCreatorGrowthStore(factory(connection)).append_start_ledger(SCOPE, ledger, "receipt-ledger-1")
    sql = connection.calls[0][0]
    assert "INSERT INTO ecommerce_creator_outreach_start_ledger" in sql
    assert "UPDATE" not in sql and "provider" not in sql.lower()


def test_runtime_reader_uses_w6_canonical_candidate_and_outreach_tables() -> None:
    candidate_payload = CreatorNormalizerReceipt.model_validate({
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "receiptId": "creator-normalize-r1", "candidateId": "candidate-1", "revision": 1,
        "profileRef": {"resourceType": "CreatorDiscoveryProfileRevision", "resourceId": "profile-1", "revision": 1, "contentHash": HASH},
        "researchArtifactRef": {"resourceType": "ResearchArtifactRevision", "resourceId": "research-1", "revision": 1, "contentHash": HASH},
        "originalRecordRefs": [{"resourceType": "SourceRecordRevision", "resourceId": "source-1", "revision": 1, "contentHash": HASH}],
        "identityStatus": "resolved", "identityKeyHash": HASH, "conflictCodes": [], "factKeys": ["channel"], "piiRefs": ["vault://creator/contact"],
        "contentHash": "b" * 64, "createdBy": "tester", "createdAt": NOW,
    }).model_dump(mode="json", by_alias=True)
    batch_payload = CreatorBatchPreparationRevision.model_validate({
        "tenant": {"orgId": "org-org", "projectId": "dev-project"}, "batchId": "batch-1", "revision": 2, "version": 2,
        "lifecycle": "prepared", "exactRefs": {}, "skillRefs": [], "items": [], "itemHashes": [],
        "ledger": {"input": 0, "eligible": 0, "excluded": 0, "needsReview": 0, "unknown": 0, "deduplicated": 0},
        "contentHash": "c" * 64, "createdBy": "tester", "createdAt": NOW,
    }).model_dump(mode="json", by_alias=True)
    connection = Connection(rows=[[
        {"org_id": "org-org", "project_id": "dev-project", "authority_receipt_id": "creator-normalize-r1", "content_hash": "b" * 64, "authority_data": candidate_payload},
    ], [
        {"org_id": "org-org", "project_id": "dev-project", "authority_receipt_id": "creator-authority-batch", "content_hash": "c" * 64, "authority_data": batch_payload},
    ]])
    store = EcommerceWorkshopCreatorGrowthStore(factory(Connection()), factory(connection))
    candidates = store.list_candidates(SCOPE, cutoff=NOW)
    batches = store.list_outreach_batches(SCOPE, cutoff=NOW)
    assert candidates[0].resource_type == "CreatorCandidateRevision"
    assert candidates[0].resource_id == "candidate-1"
    assert candidates[0].receipt_id == "creator-normalize-r1"
    assert candidates[0].pii_refs == ["vault://creator/contact"]
    assert batches[0].resource_type == "CreatorBatchPreparationRevision"
    assert batches[0].resource_id == "batch-1" and batches[0].revision == 2
    assert "ecommerce_creator_normalizer_receipt" in connection.calls[0][0]
    assert "ecommerce_creator_batch_preparation_revision" in connection.calls[1][0]


def test_runtime_reader_rejects_missing_receipt_and_content_hash_drift() -> None:
    contract_payload = CreatorContractRevision.model_validate({
        "tenant": {"orgId": "org-org", "projectId": "dev-project"}, "collaborationId": "collab-1", "revision": 1,
        "candidateRef": {"resourceType": "CreatorCandidateRevision", "resourceId": "candidate-1", "revision": 1, "contentHash": HASH},
        "startDecisionRef": {"resourceType": "CreatorBatchStartDecisionRevision", "resourceId": "start-1", "revision": 1, "contentHash": HASH},
        "termsHash": HASH, "monetaryTermsRef": {"resourceType": "ProtectedMonetaryTermsRevision", "resourceId": "terms-1", "revision": 1, "contentHash": HASH},
        "lifecycle": "draft", "diffFields": [], "contentHash": "d" * 64, "createdBy": "tester", "createdAt": NOW,
    }).model_dump(mode="json", by_alias=True)
    for row in (
        {"org_id": "org-org", "project_id": "dev-project", "authority_receipt_id": None, "content_hash": "d" * 64, "authority_data": contract_payload},
        {"org_id": "org-org", "project_id": "dev-project", "authority_receipt_id": "creator-authority-contract", "content_hash": "e" * 64, "authority_data": contract_payload},
    ):
        with pytest.raises(CreatorAuthorityReadError):
            EcommerceWorkshopCreatorGrowthStore(factory(Connection()), factory(Connection(rows=[[row]]))).list_contracts(SCOPE, cutoff=NOW)
