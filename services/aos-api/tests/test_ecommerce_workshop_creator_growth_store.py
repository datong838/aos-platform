from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_workshop_creator_growth_authorities import CreatorCandidateRevision, OutreachStartLedger
from aos_api.ecommerce_workshop_creator_growth_store import CreatorAuthorityReadError, EcommerceWorkshopCreatorGrowthStore
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
    payload = candidate().model_dump(mode="json", by_alias=True)
    connection = Connection(rows=[[{"org_id": "org-org", "project_id": "dev-project", "receipt_id": "receipt-1", "authority_data": payload}]])
    rows = EcommerceWorkshopCreatorGrowthStore(factory(connection)).list_candidates(SCOPE, cutoff=NOW, limit=1)
    assert rows[0].receipt_id == "receipt-1"
    assert "REPEATABLE READ READ ONLY" in connection.calls[0][0]
    drift = Connection(rows=[[{"org_id": "dev-org", "project_id": "dev-project", "receipt_id": "receipt-1", "authority_data": payload}]])
    with pytest.raises(CreatorAuthorityReadError):
        EcommerceWorkshopCreatorGrowthStore(factory(drift)).list_candidates(SCOPE, cutoff=NOW)


def test_start_ledger_append_has_no_provider_or_update_side_effect() -> None:
    ledger = OutreachStartLedger.model_validate({"tenant": {"orgId": "org-org", "projectId": "dev-project"}, "ledgerId": "ledger-1", "revision": 1, "batchRef": {"resourceType": "OutreachBatchRevision", "resourceId": "batch-1", "revision": 1, "contentHash": HASH}, "input": 1, "accepted": 0, "applied": 0, "failed": 0, "unknown": 1, "skipped": 0, "contentHash": HASH, "recordedAt": NOW})
    connection = Connection()
    EcommerceWorkshopCreatorGrowthStore(factory(connection)).append_start_ledger(SCOPE, ledger, "receipt-ledger-1")
    sql = connection.calls[0][0]
    assert "INSERT INTO ecommerce_creator_outreach_start_ledger" in sql
    assert "UPDATE" not in sql and "provider" not in sql.lower()
