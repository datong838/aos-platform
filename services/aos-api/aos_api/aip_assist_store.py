"""PostgreSQL append-only authority for canonical AIP Assist."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_assist_contracts import (
    AssistBlocker,
    AssistEventType,
    AssistStreamEvent,
    AssistSubjectRefs,
    AssistThreadSnapshot,
    AssistThreadStatus,
    AssistTurnRecord,
    CreateAssistThreadRequest,
    CreateAssistTurnRequest,
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


class AipAssistStore:
    def create_thread(
        self,
        scope: TenantScope,
        request: CreateAssistThreadRequest,
        *,
        idempotency_key: str,
        actor: str,
    ) -> AssistThreadSnapshot:
        self._require_identity(idempotency_key, actor)
        payload = request.model_dump(mode="json", by_alias=True)
        subject_payload = AssistSubjectRefs(
            task_ref=request.task_ref,
            task_run_ref=request.task_run_ref,
            agent_run_ref=request.agent_run_ref,
            selection_refs=request.selection_refs,
            cutoff_at=request.cutoff_at,
        ).model_dump(mode="json", by_alias=True)
        request_hash = _hash({"scope": scope.key, "request": payload, "actor": actor})
        thread_id = _id("assist-thread", scope, idempotency_key)
        now = datetime.now(UTC)
        with connect(scope) as conn:
            replay = self._replay(
                conn, scope, "create_thread", idempotency_key, request_hash
            )
            if replay:
                return AssistThreadSnapshot.model_validate(replay)
            conn.execute(
                """INSERT INTO aip_assist_thread(
                  org_id,project_id,thread_id,subject_json,subject_hash,
                  idempotency_key,created_by,created_at)
                  VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s,%s)""",
                (
                    *scope.key,
                    thread_id,
                    _json(subject_payload),
                    _hash(subject_payload),
                    idempotency_key,
                    actor,
                    now,
                ),
            )
            snapshot = self._snapshot(conn, scope, thread_id)
            self._receipt(
                conn,
                scope,
                "create_thread",
                idempotency_key,
                request_hash,
                snapshot,
                actor,
                now,
            )
            conn.commit()
            return snapshot

    def get_thread(self, scope: TenantScope, thread_id: str) -> AssistThreadSnapshot:
        with connect(scope) as conn:
            return self._snapshot(conn, scope, thread_id)

    def create_blocked_turn(
        self,
        scope: TenantScope,
        thread_id: str,
        request: CreateAssistTurnRequest,
        *,
        idempotency_key: str,
        actor: str,
    ) -> AssistTurnRecord:
        self._require_identity(idempotency_key, actor)
        payload = request.model_dump(mode="json", by_alias=True)
        request_hash = _hash(
            {
                "scope": scope.key,
                "threadId": thread_id,
                "request": payload,
                "actor": actor,
            }
        )
        now = datetime.now(UTC)
        with connect(scope) as conn:
            replay = self._replay(
                conn, scope, "create_turn", idempotency_key, request_hash
            )
            if replay:
                return AssistTurnRecord.model_validate(replay)
            row = conn.execute(
                """SELECT thread_id FROM aip_assist_thread
                WHERE org_id=%s AND project_id=%s AND thread_id=%s
                FOR UPDATE""",
                (*scope.key, thread_id),
            ).fetchone()
            if row is None:
                self._not_found()
            latest = conn.execute(
                """SELECT COALESCE(MAX(turn_sequence),0) AS sequence
                FROM aip_assist_turn
                WHERE org_id=%s AND project_id=%s AND thread_id=%s""",
                (*scope.key, thread_id),
            ).fetchone()
            current_version = int(latest["sequence"]) + 1
            if request.expected_thread_version != current_version:
                raise ApiError(
                    code="REVISION_CONFLICT",
                    message="assist thread version changed",
                    status_code=412,
                    details={
                        "expected": request.expected_thread_version,
                        "actual": current_version,
                    },
                )
            turn_sequence = current_version
            turn_id = _id("assist-turn", scope, thread_id, idempotency_key)
            conn.execute(
                """INSERT INTO aip_assist_turn(
                  org_id,project_id,thread_id,turn_id,turn_sequence,
                  request_json,request_hash,cutoff_at,created_by,created_at)
                  VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)""",
                (
                    *scope.key,
                    thread_id,
                    turn_id,
                    turn_sequence,
                    _json(payload),
                    request_hash,
                    request.cutoff_at,
                    actor,
                    now,
                ),
            )
            events = [
                AssistStreamEvent(
                    event_type=AssistEventType.START,
                    thread_id=thread_id,
                    turn_id=turn_id,
                    sequence=1,
                    occurred_at=now,
                ),
                AssistStreamEvent(
                    event_type=AssistEventType.BLOCKED,
                    thread_id=thread_id,
                    turn_id=turn_id,
                    sequence=2,
                    occurred_at=now,
                    blocker=AssistBlocker(
                        code="ASSIST_RUNTIME_NOT_INSTALLED",
                        message="Assist runtime is not installed",
                        retryable=False,
                    ),
                ),
            ]
            for event in events:
                self._event(conn, scope, event, actor)
            outcome = AssistTurnRecord(
                thread=self._snapshot(conn, scope, thread_id),
                events=events,
            )
            self._receipt(
                conn,
                scope,
                "create_turn",
                idempotency_key,
                request_hash,
                outcome,
                actor,
                now,
                turn_id=turn_id,
            )
            conn.commit()
            return outcome

    def _snapshot(
        self, conn: Any, scope: TenantScope, thread_id: str
    ) -> AssistThreadSnapshot:
        row = conn.execute(
            """SELECT t.*,
              COALESCE(v.turn_count,0) AS turn_count,
              latest.event_type AS latest_event_type
              FROM aip_assist_thread t
              LEFT JOIN LATERAL (
                SELECT COUNT(*) AS turn_count FROM aip_assist_turn
                WHERE org_id=t.org_id AND project_id=t.project_id
                  AND thread_id=t.thread_id
              ) v ON true
              LEFT JOIN LATERAL (
                SELECT e.event_type FROM aip_assist_event e
                JOIN aip_assist_turn tr ON tr.org_id=e.org_id
                  AND tr.project_id=e.project_id AND tr.thread_id=e.thread_id
                  AND tr.turn_id=e.turn_id
                WHERE e.org_id=t.org_id AND e.project_id=t.project_id
                  AND e.thread_id=t.thread_id
                ORDER BY tr.turn_sequence DESC,e.sequence DESC LIMIT 1
              ) latest ON true
              WHERE t.org_id=%s AND t.project_id=%s AND t.thread_id=%s""",
            (*scope.key, thread_id),
        ).fetchone()
        if row is None:
            self._not_found()
        latest_type = row["latest_event_type"]
        status = (
            AssistThreadStatus.BLOCKED
            if latest_type in {AssistEventType.BLOCKED.value, AssistEventType.ERROR.value}
            else AssistThreadStatus.CLOSED
            if latest_type == AssistEventType.DONE.value
            else AssistThreadStatus.OPEN
        )
        return AssistThreadSnapshot(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            thread_id=thread_id,
            subject=AssistSubjectRefs.model_validate(row["subject_json"]),
            status=status,
            version=int(row["turn_count"]) + 1,
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    def _event(
        self,
        conn: Any,
        scope: TenantScope,
        event: AssistStreamEvent,
        actor: str,
    ) -> None:
        payload = event.model_dump(mode="json", by_alias=True)
        conn.execute(
            """INSERT INTO aip_assist_event(
              org_id,project_id,event_id,thread_id,turn_id,sequence,event_type,
              event_json,event_hash,actor,occurred_at)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
            (
                *scope.key,
                _id("assist-event", scope, event.turn_id, event.sequence),
                event.thread_id,
                event.turn_id,
                event.sequence,
                event.event_type.value,
                _json(payload),
                _hash(payload),
                actor,
                event.occurred_at,
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
            """SELECT request_hash,response_json FROM aip_assist_receipt
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
        response: AssistThreadSnapshot | AssistTurnRecord,
        actor: str,
        created_at: datetime,
        *,
        turn_id: str | None = None,
    ) -> None:
        thread_id = (
            response.thread_id
            if isinstance(response, AssistThreadSnapshot)
            else response.thread.thread_id
        )
        conn.execute(
            """INSERT INTO aip_assist_receipt(
              org_id,project_id,operation,idempotency_key,request_hash,
              thread_id,turn_id,response_json,actor,created_at)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (
                *scope.key,
                operation,
                key,
                request_hash,
                thread_id,
                turn_id,
                _json(response.model_dump(mode="json", by_alias=True)),
                actor,
                created_at,
            ),
        )

    @staticmethod
    def _require_identity(idempotency_key: str, actor: str) -> None:
        if not idempotency_key.strip() or not actor.strip():
            raise ValueError("idempotency key and actor are required")

    @staticmethod
    def _not_found() -> None:
        raise ApiError(
            code="AIP_ASSIST_THREAD_NOT_FOUND",
            message="assist thread not found",
            status_code=404,
        )


__all__ = ["AipAssistStore"]
