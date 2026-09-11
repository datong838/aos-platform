"""Source body integrity with real disclosure authority in disposable PG only."""
from datetime import datetime, timezone
import os

import pytest

from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked, canonical_hash
from aos_api.aip_production_contracts import ResolveEvidenceDisclosureRequest, RevokeEvidenceRequest
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, insert, SCOPE
from test_aip_taor_lease_adapter import running_run
from aos_api.aip_task_store import AipTaskStore


@pytest.mark.skipif(os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database opt-in required")
@pytest.mark.parametrize("drift", [False, True])
def test_real_disclosure_receipt_cannot_authorize_a_different_body(drift):
    with disposable_database() as connect:
        run = running_run(AipTaskStore(connect_factory=connect))
        original = {"summary": "Synthetic source integrity evidence", "marking": ["public"]}
        stored = dict(original, summary="different content") if drift else original
        source_hash = canonical_hash(original)
        now = datetime.now(timezone.utc)
        with connect(SCOPE) as conn:
            insert(conn, "aip_evidence", evidence_id="source-integrity-fixture", run_id=run.id,
                evidence_type="query", subject_ref={}, source_type="database", source_ref="synthetic",
                observed_at=now, freshness_at=now, content_hash=source_hash, payload=stored, created_by="actor")
        store = AipProductionContractStore(connect)
        body = ResolveEvidenceDisclosureRequest.model_validate(dict(
            evidenceRef=dict(resourceType="Evidence", resourceId="source-integrity-fixture", revision=1, contentHash=source_hash),
            purpose="source", requestedLevel="l3", taskId=run.task_id))
        decision = store.resolve_evidence_disclosure(SCOPE, "actor", "integrity-disclosure", body, markings=["public", "secret"])
        assert decision.status.value == "allowed"
        with connect(SCOPE) as conn:
            if drift:
                with pytest.raises(ProductionContractDependencyBlocked, match="EVIDENCE_SOURCE_DISCLOSURE_DENIED"):
                    store.read_disclosed_evidence_source(conn, SCOPE, "actor", decision.decision_id, body, markings=["public", "secret"])
            else:
                result = store.read_disclosed_evidence_source(conn, SCOPE, "actor", decision.decision_id, body, markings=["public", "secret"])
                assert result["payload"] == original
                assert canonical_hash(result["payload"]) == result["evidenceRef"]["contentHash"]
        store.revoke_evidence(SCOPE, "actor", "source-integrity-fixture", "integrity-revoke",
            RevokeEvidenceRequest(expectedContentHash=source_hash, reason="synthetic withdrawal"))
        with connect(SCOPE) as conn:
            with pytest.raises(ProductionContractDependencyBlocked):
                store.read_disclosed_evidence_source(conn, SCOPE, "actor", decision.decision_id, body, markings=["public", "secret"])
