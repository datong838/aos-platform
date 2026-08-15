from datetime import UTC, datetime, timedelta
import hashlib
import json
from uuid import uuid4

import pytest
import psycopg

from aos_api.aip_analyst_contracts import (
    AnalystQueryStatus,
    CreateQueryJobRequest,
    QueryColumn,
    QueryJobCommand,
    QueryJobStatus,
    QueryResultRevision,
    QueryRow,
    QuerySourceRef,
    RecordQueryResultRequest,
    SemanticQueryRequest,
)
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.errors import ApiError
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _key(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _create() -> CreateQueryJobRequest:
    now = datetime.now(UTC)
    return CreateQueryJobRequest(
        query=SemanticQueryRequest(object_type="Order", cutoff_at=now),
        deadline_at=now + timedelta(hours=1),
    )


def _result(query_id: str, cutoff: datetime) -> QueryResultRevision:
    now = datetime.now(UTC)
    columns = [QueryColumn(key="orderNo", label="订单", value_type="string")]
    rows = [QueryRow(row_id="order-1", values={"orderNo": "20260815001"})]
    sources = [QuerySourceRef(ref=ResourceRef(resource_type="ObjectTypeRevision", resource_id="Order", revision="12", authority="ontology"), content_hash="a" * 64, cutoff_at=cutoff, freshness="fresh", markings=["public"])]
    query = SemanticQueryRequest(object_type="Order", cutoff_at=cutoff)
    request_hash = hashlib.sha256(json.dumps(query.model_dump(mode="json", by_alias=True), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload = {"scope": SCOPE.key, "requestHash": request_hash, "status": "complete", "columns": [item.model_dump(mode="json", by_alias=True) for item in columns], "rows": [item.model_dump(mode="json", by_alias=True) for item in rows], "sources": [item.model_dump(mode="json", by_alias=True) for item in sources], "lineage": [], "uncertainties": []}
    content_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return QueryResultRevision(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id), query_id=query_id,
        revision=1, kind="semantic", status=AnalystQueryStatus.COMPLETE,
        columns=columns, rows=rows, source_refs=sources,
        cutoff_at=cutoff, content_hash=content_hash, created_at=now,
    )


def test_store_idempotency_cas_result_and_tenant_isolation() -> None:
    store = AipAnalystQueryStore()
    request = _create()
    key = _key("create")
    created = store.create(SCOPE, request, idempotency_key=key, actor="user:dev")
    replay = store.create(SCOPE, request, idempotency_key=key, actor="user:dev")
    assert replay == created and created.status == QueryJobStatus.QUEUED
    with pytest.raises(ApiError) as hidden:
        store.get(TenantScope("dev-org", "dev-project"), created.query_id)
    assert hidden.value.status_code == 404
    with connect(TenantScope("dev-org", "dev-project")) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM aip_analyst_query_job WHERE query_id=%s", (created.query_id,)).fetchone()["n"] == 0

    start_key = _key("start")
    start_command = QueryJobCommand(
        expected_sequence=1,
        reason_code="EXECUTOR_ACCEPTED",
    )
    started = store.command(
        SCOPE,
        created.query_id,
        "start",
        start_command,
        idempotency_key=start_key,
        actor="user:dev",
    )
    assert started.status == QueryJobStatus.RUNNING and started.latest_sequence == 2
    assert store.command(
        SCOPE,
        created.query_id,
        "start",
        start_command,
        idempotency_key=start_key,
        actor="user:dev",
    ) == started
    with pytest.raises(ApiError) as stale:
        store.command(SCOPE, created.query_id, "cancel", QueryJobCommand(expected_sequence=1, reason_code="STALE"), idempotency_key=_key("stale"), actor="user:dev")
    assert stale.value.status_code == 412
    forged = _result(created.query_id, request.query.cutoff_at).model_copy(update={"content_hash": "f" * 64})
    with pytest.raises(ApiError) as invalid_hash:
        store.record_result(SCOPE, created.query_id, RecordQueryResultRequest(expected_sequence=2, result=forged), idempotency_key=_key("forged"), actor="user:dev")
    assert invalid_hash.value.code == "AIP_ANALYST_RESULT_HASH_MISMATCH"
    future_result = _result(created.query_id, request.query.cutoff_at).model_copy(
        update={"created_at": datetime.now(UTC) + timedelta(minutes=5)}
    )
    with pytest.raises(ApiError) as invalid_time:
        store.record_result(
            SCOPE,
            created.query_id,
            RecordQueryResultRequest(expected_sequence=2, result=future_result),
            idempotency_key=_key("future"),
            actor="user:dev",
        )
    assert invalid_time.value.code == "AIP_ANALYST_RESULT_TIME_DRIFT"
    completed = store.record_result(SCOPE, created.query_id, RecordQueryResultRequest(expected_sequence=2, result=_result(created.query_id, request.query.cutoff_at)), idempotency_key=_key("result"), actor="user:dev")
    assert completed.status == QueryJobStatus.SUCCEEDED
    assert completed.latest_result is not None
    with pytest.raises(ApiError):
        store.command(SCOPE, created.query_id, "cancel", QueryJobCommand(expected_sequence=3, reason_code="TOO_LATE"), idempotency_key=_key("late"), actor="user:dev")
    reconciled = store.command(SCOPE, created.query_id, "reconcile", QueryJobCommand(expected_sequence=3, reason_code="RESULT_VERIFIED"), idempotency_key=_key("reconcile"), actor="user:dev")
    assert reconciled.status == QueryJobStatus.SUCCEEDED and reconciled.latest_sequence == 4


def test_idempotency_payload_drift_is_rejected() -> None:
    store = AipAnalystQueryStore()
    key = _key("drift")
    store.create(SCOPE, _create(), idempotency_key=key, actor="user:dev")
    with pytest.raises(ApiError) as drift:
        store.create(SCOPE, _create(), idempotency_key=key, actor="user:dev")
    assert drift.value.code == "IDEMPOTENCY_CONFLICT"


def test_cancel_timeout_and_reconcile_are_append_only_terminal_facts() -> None:
    store = AipAnalystQueryStore()
    cancelled = store.create(SCOPE, _create(), idempotency_key=_key("cancel-create"), actor="user:dev")
    cancelled = store.command(SCOPE, cancelled.query_id, "cancel", QueryJobCommand(expected_sequence=1, reason_code="USER_CANCELLED"), idempotency_key=_key("cancel"), actor="user:dev")
    assert cancelled.status == QueryJobStatus.CANCELLED
    reconciled = store.command(SCOPE, cancelled.query_id, "reconcile", QueryJobCommand(expected_sequence=2, reason_code="CANCEL_CONFIRMED"), idempotency_key=_key("cancel-reconcile"), actor="user:dev")
    assert reconciled.status == QueryJobStatus.CANCELLED
    timed_out = store.create(SCOPE, _create(), idempotency_key=_key("timeout-create"), actor="user:dev")
    timed_out = store.command(SCOPE, timed_out.query_id, "timeout", QueryJobCommand(expected_sequence=1, reason_code="DEADLINE_EXCEEDED"), idempotency_key=_key("timeout"), actor="user:dev")
    assert timed_out.status == QueryJobStatus.TIMED_OUT
    failed = store.create(
        SCOPE,
        _create(),
        idempotency_key=_key("fail-create"),
        actor="user:dev",
    )
    failed = store.command(
        SCOPE,
        failed.query_id,
        "fail",
        QueryJobCommand(expected_sequence=1, reason_code="ADAPTER_FAILED"),
        idempotency_key=_key("fail"),
        actor="user:dev",
    )
    assert failed.status == QueryJobStatus.FAILED


def test_tables_force_rls_and_reject_mutation() -> None:
    with connect(SCOPE) as conn:
        rows = conn.execute("""SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class
          WHERE relname=ANY(%s) ORDER BY relname""", (["aip_analyst_query_job", "aip_analyst_query_event", "aip_analyst_query_result_revision", "aip_analyst_query_receipt"],)).fetchall()
        assert len(rows) == 4
        assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
    store = AipAnalystQueryStore()
    created = store.create(SCOPE, _create(), idempotency_key=_key("immutable"), actor="user:dev")
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        with connect(SCOPE) as conn:
            conn.execute("UPDATE aip_analyst_query_job SET created_by='forged' WHERE org_id=%s AND project_id=%s AND query_id=%s", (*SCOPE.key, created.query_id))
