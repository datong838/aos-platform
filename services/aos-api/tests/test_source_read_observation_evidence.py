from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.source_read_observation_evidence import SourceObservationEvidenceStore
from aos_api.tenant_scope import TenantScope
from tests.test_source_read_observation import NOW, observation


SCOPE = TenantScope("org-org", "dev-project")
ROWS = [{"goods_id": 1}]


def test_persist_replay_exact_read_and_rollback_on_isolated_database():
    now = datetime.now(UTC)
    observed = observation().model_copy(update={
        "read_started_at": now - timedelta(seconds=2),
        "read_finished_at": now - timedelta(seconds=1),
    })
    with connect(SCOPE) as conn:
        store = SourceObservationEvidenceStore(HostTransaction(conn), SCOPE)
        ref = store.put(observed, ROWS, actor="user:observation-owner")
        assert store.put(observed, ROWS, actor="user:observation-owner") == ref
        restored = store.read_exact(ref)
        assert restored.observation == observed
        assert restored.recorded_at >= restored.observation.read_finished_at
        row = conn.execute("SELECT payload,subject_ref FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_id=%s",
                           (*SCOPE.key, ref.resource_id)).fetchone()
        assert row["payload"]["factIds"] == []
        assert "goods_id" not in str(row["payload"])
        assert row["subject_ref"].get("revision") is None
        conn.rollback()
    with connect(SCOPE) as conn:
        assert SourceObservationEvidenceStore(HostTransaction(conn), SCOPE).read_exact(ref) is None


class Connection:
    def __init__(self, row):
        self.row = row
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self
    def fetchone(self):
        return self.row


def saved_row():
    from aos_api.source_read_observation_evidence import canonical_observation_evidence
    body, digest = canonical_observation_evidence(SCOPE, observation(), actor="user:owner")
    ref = InvestigationExactRef(resource_type="Evidence", resource_id="evidence-source-read-" + digest,
                               revision=1, content_hash="sha256:" + digest)
    row = dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id, evidence_id=ref.resource_id,
        run_id=None, evidence_type="source-read-observation", source_type="source-read-observation",
        source_ref="source-1", subject_ref={"resourceType": "DataSource", "resourceId": "source-1",
                                          "authority": "postgres:meta_source"},
        observed_at=NOW + timedelta(seconds=1), freshness_at=NOW, content_hash=digest,
        payload=deepcopy(body), redaction={}, created_by="user:owner", created_at=NOW + timedelta(seconds=2),
        revoked=False)
    return ref, row


@pytest.mark.parametrize("field,value", [("org_id", "dev-org"), ("project_id", "other"),
    ("content_hash", "0" * 64), ("source_ref", "other"), ("created_by", "other"),
    ("freshness_at", NOW + timedelta(seconds=1)), ("observed_at", NOW),
    ("created_at", NOW), ("revoked", True), ("subject_ref", {}), ("run_id", "other")])
def test_exact_read_rejects_tampered_columns_without_writes(field, value):
    ref, row = saved_row()
    row[field] = value
    conn = Connection(row)
    with pytest.raises(ValueError):
        SourceObservationEvidenceStore(HostTransaction(conn), SCOPE).read_exact(ref)
    assert all(sql.startswith("SELECT") for sql, _ in conn.calls)


def test_body_change_cannot_reuse_original_reference():
    ref, row = saved_row()
    row["payload"]["factIds"] = ["Product"]
    with pytest.raises(ValueError):
        SourceObservationEvidenceStore(HostTransaction(Connection(row)), SCOPE).read_exact(ref)


def test_invalid_tenant_and_rows_rejected_before_insert():
    conn = Connection(None)
    store = SourceObservationEvidenceStore(HostTransaction(conn), TenantScope("dev-org", "dev-project"))
    with pytest.raises(ValueError, match="scope"):
        store.put(observation(), ROWS, actor="user:owner")
    store = SourceObservationEvidenceStore(HostTransaction(conn), SCOPE)
    with pytest.raises(ValueError, match="rows"):
        store.put(observation(), [{"goods_id": 2}], actor="user:owner")
    assert conn.calls == []


def test_observation_cannot_cover_a_required_business_fact():
    from aos_api.aip_production_contract_store import AipProductionContractStore
    ref, row = saved_row()
    body = SimpleNamespace(required_fact_ids=["Product"], cutoff_at=NOW,
        item_refs=[SimpleNamespace(resource_type="Evidence", resource_id=ref.resource_id,
                                   content_hash=row["content_hash"])])
    coverage, missing, _, _, freshness = AipProductionContractStore()._compute_evidence_bundle_coverage(
        Connection(row), SCOPE, body)
    assert coverage.value == "blocked" and freshness.value == "blocked"
    assert missing == [{"factId": "Product"}]


def test_runtime_role_concurrent_deduplication_canary_and_revocation():
    now = datetime.now(UTC)
    observed = observation().model_copy(update={
        "read_started_at": now - timedelta(seconds=2),
        "read_finished_at": now - timedelta(seconds=1),
    })

    def save(_):
        with connect(SCOPE) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            result = SourceObservationEvidenceStore(HostTransaction(conn), SCOPE).put(
                observed, ROWS, actor="user:concurrent-observer")
            conn.commit()
            return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(pool.map(save, range(2)))
    assert refs[0] == refs[1]
    ref = refs[0]
    canary = TenantScope("dev-org", "dev-project")
    with connect(canary) as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert SourceObservationEvidenceStore(HostTransaction(conn), canary).read_exact(ref) is None
        assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_id=%s",
                            (ref.resource_id,)).fetchone()["n"] == 0
    with connect(SCOPE) as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_id=%s",
                            (ref.resource_id,)).fetchone()["n"] == 1
        conn.execute("""INSERT INTO aip_evidence_revoke_event
            (org_id,project_id,event_id,evidence_id,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,%s,'isolated revocation test','user:reviewer')""",
            (*SCOPE.key, "revoke-" + ref.resource_id, ref.resource_id, ref.content_hash[7:]))
        conn.commit()
    with connect(SCOPE) as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        store = SourceObservationEvidenceStore(HostTransaction(conn), SCOPE)
        with pytest.raises(ValueError, match="revoked"):
            store.read_exact(ref)
        with pytest.raises(ValueError, match="revoked"):
            store.put(observed, ROWS, actor="user:concurrent-observer")
