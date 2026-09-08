from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from aos_api.data_requirement_quality_evidence import (
    QualityEvidenceInput, QualityEvidenceStore, canonical_quality_evidence,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from tests.aip._migration_test_support import isolated_aip_migration_database
from tests.test_data_requirement_quality import NOW, SCOPE, measurement, policy, requirement
from tests.test_data_fulfillment_store import Connection


def evidence_input():
    return QualityEvidenceInput(requirement=requirement(), measurement=measurement(),
        population_policy=policy(), evaluated_at=NOW, actor="user:quality-owner", run_id=None)


def test_quality_measurement_never_claims_business_fact_coverage():
    value = evidence_input()
    body, digest = canonical_quality_evidence(SCOPE, value)
    assert body["factIds"] == [] and body["assessment"]["satisfied"]
    value.measurement.facts[0].valid_count = 1
    failed, failed_hash = canonical_quality_evidence(SCOPE, value)
    assert failed["factIds"] == [] and not failed["assessment"]["satisfied"]
    assert failed_hash != digest


def test_equivalent_timezones_are_same_content_and_tenant_is_bound():
    value = evidence_input()
    expected = canonical_quality_evidence(SCOPE, value)
    value.measurement.measured_at = NOW.astimezone(timezone(timedelta(hours=8)))
    assert canonical_quality_evidence(SCOPE, value) == expected
    with pytest.raises(ValueError, match="scope"):
        canonical_quality_evidence(TenantScope("dev-org", "dev-project"), value)


def test_original_requirement_timezone_and_hash_are_not_rewritten():
    from aos_api.data_requirement_store import canonical_revision_content_hash
    value = evidence_input()
    offset = timezone(timedelta(hours=8))
    value.requirement.created_at = NOW.astimezone(offset)
    value.requirement.content_hash = canonical_revision_content_hash(value.requirement)
    value.measurement.requirement_ref.content_hash = value.requirement.content_hash
    body, digest = canonical_quality_evidence(SCOPE, value)
    assert body["input"]["requirement"]["createdAt"].endswith("+08:00")
    assert canonical_quality_evidence(SCOPE, QualityEvidenceInput.model_validate(body["input"])) == (body, digest)


@pytest.mark.parametrize("defect", ["tenant", "hash", "actor", "source", "freshness", "body", "ref"])
def test_exact_read_rejects_column_and_payload_drift_without_writes(defect):
    value = evidence_input()
    body, digest = canonical_quality_evidence(SCOPE, value)
    ref = InvestigationExactRef(resource_type="Evidence", resource_id="evidence-quality-" + digest,
                               revision=1, content_hash="sha256:" + digest)
    row = dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id, evidence_id=ref.resource_id,
        run_id=None, evidence_type="data-requirement-quality",
        subject_ref={**value.measurement.requirement_ref.model_dump(by_alias=True), "authority": "postgres:data_requirement_revision"},
        source_type="data-requirement-quality", source_ref=value.requirement.requirement_id,
        observed_at=NOW, freshness_at=NOW, content_hash=digest, redaction={}, payload=deepcopy(body),
        created_by=value.actor, created_at=NOW, revoked=False)
    if defect == "tenant": row["org_id"] = "dev-org"
    if defect == "hash": row["content_hash"] = "0" * 64
    if defect == "actor": row["created_by"] = "another-actor"
    if defect == "source": row["source_ref"] = "another-requirement"
    if defect == "freshness": row["freshness_at"] = NOW + timedelta(seconds=1)
    if defect == "body": row["payload"]["factIds"] = ["Order"]
    if defect == "ref": ref.revision = "1"
    conn = Connection(row)
    with pytest.raises(ValueError): QualityEvidenceStore(HostTransaction(conn), SCOPE).read_exact(ref)
    assert conn.commits == 0 and all(sql.startswith("SELECT") for sql, _ in conn.calls)


def test_isolated_postgres_replay_rollback_canary_and_revocation():
    with isolated_aip_migration_database("ar2_quality_evidence") as (_, dsn):
        @contextmanager
        def runtime(scope=SCOPE):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                yield conn, QualityEvidenceStore(HostTransaction(conn), scope)

        value = evidence_input()
        def save(_):
            with runtime() as (conn, store):
                result = store.put(value)
                conn.commit()
                return result
        with ThreadPoolExecutor(max_workers=2) as pool:
            refs = list(pool.map(save, range(2)))
        assert refs[0] == refs[1]
        ref = refs[0]
        with runtime() as (conn, store):
            assert store.read_exact(ref).measurement == value.measurement
            row = conn.execute("SELECT count(*) AS count,min(freshness_at) AS freshness FROM aip_evidence").fetchone()
            assert row == {"count": 1, "freshness": NOW}
        with runtime(TenantScope("dev-org", "dev-project")) as (_, store):
            assert store.read_exact(ref) is None
        different = evidence_input()
        different.measurement.facts[0].valid_count = 5
        with runtime() as (conn, store):
            abandoned = store.put(different)
            conn.rollback()
        with runtime() as (_, store):
            assert store.read_exact(abandoned) is None
        with runtime() as (conn, store):
            conn.execute("""INSERT INTO aip_evidence_revoke_event
                (org_id,project_id,event_id,evidence_id,content_hash,reason,actor)
                VALUES(%s,%s,'revoke-quality',%s,%s,'test revocation','user:reviewer')""",
                (*SCOPE.key, ref.resource_id, ref.content_hash[7:]))
            conn.commit()
        with runtime() as (_, store):
            with pytest.raises(ValueError, match="revoked"): store.read_exact(ref)
            with pytest.raises(ValueError, match="revoked"): store.put(value)
