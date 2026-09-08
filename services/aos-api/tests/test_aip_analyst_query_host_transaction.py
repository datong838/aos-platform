from datetime import UTC, datetime
from uuid import uuid4

import pytest

from aos_api.aip_analyst_contracts import QueryJobCommand, RecordQueryResultRequest
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope
from tests.test_data_fulfillment_store import Connection, factory
from tests.aip.test_aip8_query_store import SCOPE, _create, _result


def save(store):
    key = uuid4().hex
    request = _create()
    created = store.create(SCOPE, request, idempotency_key=key, actor="user:query-owner")
    result = _result(created.query_id, request.query.cutoff_at)
    done = store.record_result(SCOPE, created.query_id,
        RecordQueryResultRequest(expected_sequence=1, result=result),
        idempotency_key=key + "-result", actor="user:query-owner")
    ref = InvestigationExactRef(resource_type="QueryResultRevision", resource_id=created.query_id,
        revision=result.revision, content_hash="sha256:" + result.content_hash)
    return done, ref


def test_host_rolls_back_query_job_event_result_and_receipt_together():
    with connect(SCOPE) as conn:
        store = AipAnalystQueryStore(connect_factory=TransactionBoundConnectFactory(HostTransaction(conn), SCOPE))
        done, ref = save(store)
        assert store.read_result_exact(SCOPE, ref) == done.latest_result
        conn.rollback()
    store = AipAnalystQueryStore()
    assert store.read_result_exact(SCOPE, ref) is None
    with pytest.raises(ApiError): store.get(SCOPE, done.query_id)
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_analyst_query_receipt WHERE org_id=%s AND project_id=%s AND query_id=%s",
                            (*SCOPE.key, done.query_id)).fetchone()["n"] == 0


def test_exact_result_survives_job_head_advance_and_hides_other_tenant():
    store = AipAnalystQueryStore(clock=lambda: datetime.now(UTC))
    done, ref = save(store)
    store.command(SCOPE, done.query_id, "reconcile", QueryJobCommand(expected_sequence=2, reason_code="VERIFIED"),
                  idempotency_key=uuid4().hex, actor="user:query-owner")
    assert store.read_result_exact(SCOPE, ref) == done.latest_result
    assert store.read_result_exact(TenantScope("dev-org", "dev-project"), ref) is None
    bad = ref.model_copy(update={"content_hash": "sha256:" + "f" * 64})
    with pytest.raises(ValueError): store.read_result_exact(SCOPE, bad)
    for change in ({"revision": "1"}, {"resource_type": "DataProductRevision"}, {"receipt_id": "not-a-receipt"}):
        with pytest.raises(ValueError): store.read_result_exact(SCOPE, ref.model_copy(update=change))


@pytest.mark.parametrize("defect", ["rows", "query_id", "revision", "tenant", "status", "cutoff", "created_at", "request"])
def test_exact_read_detects_payload_manifest_and_column_drift(defect):
    request = _create()
    result = _result("query-exact", request.query.cutoff_at)
    ref = InvestigationExactRef(resource_type="QueryResultRevision", resource_id=result.query_id,
                               revision=1, content_hash="sha256:" + result.content_hash)
    row = dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id, query_id=result.query_id,
        revision=1, job_kind="semantic", status="complete", cutoff_at=result.cutoff_at,
        job_cutoff=result.cutoff_at, job_created=result.cutoff_at, created_at=result.created_at,
        content_hash=result.content_hash, request_json=request.query.model_dump(mode="json", by_alias=True),
        result_json=result.model_dump(mode="json", by_alias=True))
    if defect == "rows": row["result_json"]["rows"][0]["values"]["orderNo"] = "changed"
    if defect == "query_id": row["query_id"] = "another-query"
    if defect == "revision": row["revision"] = 2
    if defect == "tenant": row["org_id"] = "dev-org"
    if defect == "status": row["status"] = "empty"
    if defect == "cutoff": row["cutoff_at"] = result.created_at
    if defect == "created_at": row["created_at"] = result.cutoff_at
    if defect == "request": row["request_json"]["objectType"] = "Product"
    conn = Connection(row)
    store = AipAnalystQueryStore(connect_factory=factory(conn))
    with pytest.raises(ValueError): store.read_result_exact(SCOPE, ref)
    assert conn.commits == 0
    assert all(sql.startswith("SELECT") for sql, _ in conn.calls)
