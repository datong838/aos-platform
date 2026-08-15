"""PostgreSQL append-only authority for governed Analyst QueryJobs."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_analyst_contracts import (
    ANALYST_QUERY_ADAPTER,
    AnalystQueryStatus,
    CreateQueryJobRequest,
    QueryJobCommand,
    QueryJobEventKind,
    QueryJobSnapshot,
    QueryJobStatus,
    QueryResultRevision,
    RecordQueryResultRequest,
)
from aos_api.aip_contracts import TenantContext
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _id(prefix: str, scope: TenantScope, *parts: object) -> str:
    return f"{prefix}-{_hash([scope.org_id, scope.project_id, *parts])[:24]}"


class AipAnalystQueryStore:
    def create(
        self,
        scope: TenantScope,
        request: CreateQueryJobRequest,
        *,
        idempotency_key: str,
        actor: str,
    ) -> QueryJobSnapshot:
        if not idempotency_key.strip() or not actor.strip():
            raise ValueError("idempotency key and actor are required")
        payload = request.model_dump(mode="json", by_alias=True)
        request_hash = _hash({"scope": scope.key, "request": payload, "actor": actor})
        query_id = _id("analyst-query", scope, idempotency_key)
        now = datetime.now(UTC)
        with connect(scope) as conn:
            replay = self._replay(conn, scope, "create", idempotency_key, request_hash)
            if replay:
                return QueryJobSnapshot.model_validate(replay)
            conn.execute(
                """INSERT INTO aip_analyst_query_job(
                  org_id,project_id,query_id,kind,request_json,request_hash,
                  cutoff_at,deadline_at,idempotency_key,created_by,created_at)
                  VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)""",
                (
                    *scope.key,
                    query_id,
                    request.query.kind.value,
                    _json(payload["query"]),
                    request_hash,
                    request.query.cutoff_at,
                    request.deadline_at,
                    idempotency_key,
                    actor,
                    now,
                ),
            )
            self._event(
                conn,
                scope,
                query_id,
                1,
                QueryJobEventKind.CREATED,
                QueryJobStatus.QUEUED,
                None,
                actor,
                now,
            )
            snapshot = self._snapshot(conn, scope, query_id)
            self._receipt(conn, scope, "create", idempotency_key, request_hash, snapshot, actor, now)
            conn.commit()
            return snapshot

    def get(self, scope: TenantScope, query_id: str) -> QueryJobSnapshot:
        with connect(scope) as conn:
            return self._snapshot(conn, scope, query_id)

    def command(
        self,
        scope: TenantScope,
        query_id: str,
        operation: str,
        request: QueryJobCommand,
        *,
        idempotency_key: str,
        actor: str,
    ) -> QueryJobSnapshot:
        mapping = {
            "start": (QueryJobEventKind.STARTED, QueryJobStatus.RUNNING),
            "cancel": (QueryJobEventKind.CANCELLED, QueryJobStatus.CANCELLED),
            "timeout": (QueryJobEventKind.TIMED_OUT, QueryJobStatus.TIMED_OUT),
            "fail": (QueryJobEventKind.FAILED, QueryJobStatus.FAILED),
            "reconcile": (QueryJobEventKind.RECONCILED, None),
        }
        if operation not in mapping:
            raise ValueError("unsupported query operation")
        request_hash = _hash(
            {
                "queryId": query_id,
                "operation": operation,
                "request": request.model_dump(mode="json", by_alias=True),
                "actor": actor,
            }
        )
        now = datetime.now(UTC)
        with connect(scope) as conn:
            replay = self._replay(conn, scope, operation, idempotency_key, request_hash)
            if replay:
                return QueryJobSnapshot.model_validate(replay)
            current = self._latest_for_update(conn, scope, query_id)
            self._cas(current, request.expected_sequence)
            current_status = QueryJobStatus(current["status"])
            kind, target = mapping[operation]
            if operation == "start" and current_status != QueryJobStatus.QUEUED:
                self._conflict("only queued queries may start")
            elif operation in {"cancel", "timeout", "fail"} and current_status not in {
                QueryJobStatus.QUEUED,
                QueryJobStatus.RUNNING,
            }:
                self._conflict("terminal query jobs cannot transition")
            elif operation == "reconcile" and current_status in {
                QueryJobStatus.QUEUED,
                QueryJobStatus.RUNNING,
            }:
                self._conflict("only terminal query jobs may reconcile")
            status = target or current_status
            self._event(
                conn,
                scope,
                query_id,
                request.expected_sequence + 1,
                kind,
                status,
                request.reason_code,
                actor,
                now,
            )
            snapshot = self._snapshot(conn, scope, query_id)
            self._receipt(conn, scope, operation, idempotency_key, request_hash, snapshot, actor, now)
            conn.commit()
            return snapshot

    def record_result(
        self,
        scope: TenantScope,
        query_id: str,
        request: RecordQueryResultRequest,
        *,
        idempotency_key: str,
        actor: str,
    ) -> QueryJobSnapshot:
        result = request.result
        expected_tenant = TenantContext(
            org_id=scope.org_id,
            project_id=scope.project_id,
        )
        if result.tenant != expected_tenant or result.query_id != query_id:
            raise ApiError(
                code="AIP_ANALYST_RESULT_SCOPE_MISMATCH",
                message="result authority does not match query",
                status_code=409,
            )
        request_hash = _hash(
            {
                "queryId": query_id,
                "request": request.model_dump(mode="json", by_alias=True),
                "actor": actor,
            }
        )
        now = datetime.now(UTC)
        with connect(scope) as conn:
            replay = self._replay(conn, scope, "result", idempotency_key, request_hash)
            if replay:
                return QueryJobSnapshot.model_validate(replay)
            current = self._latest_for_update(conn, scope, query_id)
            self._cas(current, request.expected_sequence)
            if QueryJobStatus(current["status"]) not in {
                QueryJobStatus.QUEUED,
                QueryJobStatus.RUNNING,
            }:
                self._conflict("terminal query jobs reject results")
            job = conn.execute(
                """SELECT kind,request_json,cutoff_at,created_at
                FROM aip_analyst_query_job
                WHERE org_id=%s AND project_id=%s AND query_id=%s""",
                (*scope.key, query_id),
            ).fetchone()
            if result.kind.value != job["kind"] or result.cutoff_at != job["cutoff_at"]:
                raise ApiError(
                    code="AIP_ANALYST_RESULT_MANIFEST_DRIFT",
                    message="result kind or cutoff drifted from query manifest",
                    status_code=409,
                )
            if result.created_at < job["created_at"] or result.created_at > now:
                raise ApiError(
                    code="AIP_ANALYST_RESULT_TIME_DRIFT",
                    message="result createdAt is outside the query execution window",
                    status_code=409,
                )
            result_payload = {
                "scope": scope.key,
                "requestHash": _hash(dict(job["request_json"])),
                "status": result.status.value,
                "columns": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in result.columns
                ],
                "rows": [item.model_dump(mode="json", by_alias=True) for item in result.rows],
                "sources": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in result.source_refs
                ],
                "lineage": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in result.lineage_refs
                ],
                "uncertainties": result.uncertainties,
            }
            if result.content_hash != _hash(result_payload):
                raise ApiError(
                    code="AIP_ANALYST_RESULT_HASH_MISMATCH",
                    message="result content hash is invalid",
                    status_code=409,
                )
            latest_revision = conn.execute(
                """SELECT COALESCE(MAX(revision),0) AS revision
                FROM aip_analyst_query_result_revision
                WHERE org_id=%s AND project_id=%s AND query_id=%s""",
                (*scope.key, query_id),
            ).fetchone()["revision"]
            if result.revision != int(latest_revision) + 1:
                self._conflict("result revision must be contiguous")
            conn.execute(
                """INSERT INTO aip_analyst_query_result_revision(
                  org_id,project_id,query_id,revision,status,result_json,
                  content_hash,cutoff_at,created_by,created_at)
                  VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)""",
                (
                    *scope.key,
                    query_id,
                    result.revision,
                    result.status.value,
                    _json(result.model_dump(mode="json", by_alias=True)),
                    result.content_hash,
                    result.cutoff_at,
                    actor,
                    now,
                ),
            )
            status = (
                QueryJobStatus.FAILED
                if result.status == AnalystQueryStatus.BLOCKED
                else QueryJobStatus.SUCCEEDED
            )
            self._event(
                conn,
                scope,
                query_id,
                request.expected_sequence + 1,
                QueryJobEventKind.RESULT_RECORDED,
                status,
                result.blockers[0].code if result.blockers else None,
                actor,
                now,
            )
            snapshot = self._snapshot(conn, scope, query_id)
            self._receipt(conn, scope, "result", idempotency_key, request_hash, snapshot, actor, now)
            conn.commit()
            return snapshot

    def _snapshot(self, conn: Any, scope: TenantScope, query_id: str) -> QueryJobSnapshot:
        row = conn.execute(
            """SELECT j.*,e.sequence,e.event_kind,e.status,e.reason_code,
              e.actor,e.observed_at,r.result_json
              FROM aip_analyst_query_job j
              JOIN LATERAL (
                SELECT * FROM aip_analyst_query_event
                WHERE org_id=j.org_id AND project_id=j.project_id
                  AND query_id=j.query_id
                ORDER BY sequence DESC LIMIT 1
              ) e ON true
              LEFT JOIN LATERAL (
                SELECT result_json FROM aip_analyst_query_result_revision
                WHERE org_id=j.org_id AND project_id=j.project_id
                  AND query_id=j.query_id
                ORDER BY revision DESC LIMIT 1
              ) r ON true
              WHERE j.org_id=%s AND j.project_id=%s AND j.query_id=%s""",
            (*scope.key, query_id),
        ).fetchone()
        if row is None:
            raise ApiError(
                code="AIP_ANALYST_QUERY_NOT_FOUND",
                message="query job not found",
                status_code=404,
            )
        return QueryJobSnapshot(
            tenant=TenantContext(
                org_id=scope.org_id,
                project_id=scope.project_id,
            ),
            query_id=query_id,
            query=ANALYST_QUERY_ADAPTER.validate_python(row["request_json"]),
            request_hash=row["request_hash"],
            status=row["status"],
            latest_sequence=row["sequence"],
            latest_event_kind=row["event_kind"],
            latest_reason_code=row["reason_code"],
            deadline_at=row["deadline_at"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            latest_result=(
                QueryResultRevision.model_validate(row["result_json"])
                if row["result_json"]
                else None
            ),
        )

    def _latest_for_update(self, conn: Any, scope: TenantScope, query_id: str) -> Any:
        row = conn.execute(
            """SELECT * FROM aip_analyst_query_event
            WHERE org_id=%s AND project_id=%s AND query_id=%s
            ORDER BY sequence DESC LIMIT 1 FOR UPDATE""",
            (*scope.key, query_id),
        ).fetchone()
        if row is None:
            raise ApiError(
                code="AIP_ANALYST_QUERY_NOT_FOUND",
                message="query job not found",
                status_code=404,
            )
        return row

    @staticmethod
    def _cas(row: Any, expected: int) -> None:
        if int(row["sequence"]) != expected:
            raise ApiError(
                code="REVISION_CONFLICT",
                message="query event sequence changed",
                status_code=412,
                details={"expected": expected, "actual": int(row["sequence"])},
            )

    @staticmethod
    def _conflict(message: str) -> None:
        raise ApiError(code="AIP_ANALYST_QUERY_STATE_CONFLICT", message=message, status_code=409)

    def _event(
        self,
        conn: Any,
        scope: TenantScope,
        query_id: str,
        sequence: int,
        kind: QueryJobEventKind,
        status: QueryJobStatus,
        reason: str | None,
        actor: str,
        observed_at: datetime,
    ) -> None:
        event_id = _id("analyst-event", scope, query_id, sequence)
        event_hash = _hash(
            [
                query_id,
                sequence,
                kind.value,
                status.value,
                reason,
                actor,
                observed_at.isoformat(),
            ]
        )
        conn.execute(
            """INSERT INTO aip_analyst_query_event(
              org_id,project_id,event_id,query_id,sequence,event_kind,status,
              reason_code,event_hash,actor,observed_at)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                event_id,
                query_id,
                sequence,
                kind.value,
                status.value,
                reason,
                event_hash,
                actor,
                observed_at,
            ),
        )

    def _replay(
        self,
        conn: Any,
        scope: TenantScope,
        operation: str,
        key: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        row = conn.execute(
            """SELECT request_hash,response_json
            FROM aip_analyst_query_receipt
            WHERE org_id=%s AND project_id=%s
              AND operation=%s AND idempotency_key=%s""",
            (*scope.key, operation, key),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise ApiError(
                code="IDEMPOTENCY_CONFLICT",
                message="idempotency key payload differs",
                status_code=409,
            )
        return dict(row["response_json"])

    def _receipt(
        self,
        conn: Any,
        scope: TenantScope,
        operation: str,
        key: str,
        request_hash: str,
        snapshot: QueryJobSnapshot,
        actor: str,
        created_at: datetime,
    ) -> None:
        conn.execute(
            """INSERT INTO aip_analyst_query_receipt(
              org_id,project_id,operation,idempotency_key,request_hash,query_id,
              resulting_sequence,resulting_revision,response_json,actor,created_at)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (
                *scope.key,
                operation,
                key,
                request_hash,
                snapshot.query_id,
                snapshot.latest_sequence,
                (
                    snapshot.latest_result.revision
                    if snapshot.latest_result
                    else None
                ),
                _json(snapshot.model_dump(mode="json", by_alias=True)),
                actor,
                created_at,
            ),
        )
