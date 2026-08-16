"""PostgreSQL authority store for AIP-9 MediaJob and AvatarSession."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_content_contracts import (
    AvatarSessionEventKind,
    AvatarSessionOpenRequest,
    AvatarSessionSnapshot,
    AvatarSessionStatus,
    MediaJobCreateRequest,
    MediaJobEventKind,
    MediaJobSnapshot,
    MediaJobStatus,
)
from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_production_contracts import ContractBlocker, ExactRevisionRef
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _id(prefix: str, scope: TenantScope, *parts: object) -> str:
    return f"{prefix}-{_hash([scope.org_id, scope.project_id, *parts])[:24]}"


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, list):
        return [_dump(item) for item in value]
    return value


class AipContentRuntimeStore:
    def submit_media_job(
        self,
        scope: TenantScope,
        request: MediaJobCreateRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime | None = None,
    ) -> MediaJobSnapshot:
        self._identity(idempotency_key, actor)
        now = occurred_at or datetime.now(UTC)
        payload = request.model_dump(mode="json", by_alias=True)
        request_hash = _hash({"scope": scope.key, "request": payload, "actor": actor})
        job_id = _id("media-job", scope, idempotency_key)
        with connect(scope) as conn:
            replay = self._replay(conn, "aip_media_job_receipt", scope, "submit", idempotency_key, request_hash)
            if replay:
                return MediaJobSnapshot.model_validate(replay)
            self._require_run_step(conn, scope, request.task_run_ref.resource_id, request.step_run_ref.resource_id)
            conn.execute(
                """INSERT INTO aip_media_job(
                  org_id,project_id,job_id,task_run_id,step_run_id,job_kind,
                  request_json,request_hash,idempotency_key,attempt,status,
                  latest_sequence,version,deadline_at,created_by,created_at,updated_at)
                  VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,1,'queued',1,1,%s,%s,%s,%s)""",
                (*scope.key, job_id, request.task_run_ref.resource_id,
                 request.step_run_ref.resource_id, request.job_kind.value,
                 _json(payload), request_hash, idempotency_key, request.deadline_at,
                 actor, now, now),
            )
            self._event(conn, "media", scope, job_id, 1, MediaJobEventKind.CREATED.value,
                        {"status": MediaJobStatus.QUEUED.value}, actor, now)
            snapshot = self._media_snapshot(conn, scope, job_id)
            self._receipt(conn, "media", scope, job_id, "submit", idempotency_key,
                          request_hash, snapshot, actor, now)
            conn.commit()
            return snapshot

    def get_media_job(self, scope: TenantScope, job_id: str) -> MediaJobSnapshot:
        with connect(scope) as conn:
            return self._media_snapshot(conn, scope, job_id)

    def command_media_job(
        self,
        scope: TenantScope,
        job_id: str,
        operation: str,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        executor_lease_ref: ResourceRef | None = None,
        heartbeat_at: datetime | None = None,
        lease_expires_at: datetime | None = None,
        output_artifact_refs: list[ArtifactRef] | None = None,
        blockers: list[ContractBlocker] | None = None,
        reason_code: str | None = None,
        reconcile_status: MediaJobStatus | None = None,
        occurred_at: datetime | None = None,
    ) -> MediaJobSnapshot:
        self._identity(idempotency_key, actor)
        if operation not in {"claim", "heartbeat", "succeed", "fail", "cancel", "mark_unknown", "reconcile"}:
            raise ValueError("unsupported media job operation")
        now = occurred_at or datetime.now(UTC)
        command = {
            "jobId": job_id, "operation": operation, "expectedVersion": expected_version,
            "executorLeaseRef": _dump(executor_lease_ref), "heartbeatAt": heartbeat_at,
            "leaseExpiresAt": lease_expires_at, "outputArtifactRefs": _dump(output_artifact_refs or []),
            "blockers": _dump(blockers or []), "reasonCode": reason_code,
            "reconcileStatus": reconcile_status.value if reconcile_status else None, "actor": actor,
        }
        request_hash = _hash(command)
        with connect(scope) as conn:
            replay = self._replay(conn, "aip_media_job_receipt", scope, operation, idempotency_key, request_hash)
            if replay:
                return MediaJobSnapshot.model_validate(replay)
            row = self._media_row(conn, scope, job_id, lock=True)
            self._cas(row, expected_version)
            current = MediaJobStatus(row["status"])
            sequence = int(row["latest_sequence"]) + 1
            target, event_kind = self._media_transition(current, operation, reconcile_status)
            updates: dict[str, Any] = {
                "status": target.value, "latest_sequence": sequence,
                "version": expected_version + 1, "updated_at": now,
                "executor_lease_ref": None, "heartbeat_at": None,
                "lease_expires_at": None, "output_artifact_refs": [],
                "completion_receipt_ref": None, "blockers": [],
                "reason_code": None, "finished_at": None,
            }
            if operation in {"claim", "heartbeat"}:
                if not executor_lease_ref or not heartbeat_at or not lease_expires_at:
                    self._conflict("media lease, heartbeat and expiry are required")
                if lease_expires_at <= heartbeat_at or lease_expires_at <= now:
                    self._conflict("media lease must be live beyond heartbeat and command time")
                if operation == "heartbeat":
                    previous_ref = dict(row["executor_lease_ref"] or {})
                    if previous_ref != _dump(executor_lease_ref) or heartbeat_at <= row["heartbeat_at"]:
                        self._conflict("media heartbeat must use the same lease and advance time")
                updates.update(executor_lease_ref=_dump(executor_lease_ref), heartbeat_at=heartbeat_at,
                               lease_expires_at=lease_expires_at)
            elif operation == "succeed":
                artifacts = output_artifact_refs or []
                if not artifacts or any(not item.revision or not item.content_hash for item in artifacts):
                    self._conflict("media success requires exact output artifacts")
                receipt_ref = self._receipt_ref(
                    "media", "MediaJobReceipt", scope, job_id, operation,
                    idempotency_key, request_hash,
                )
                updates.update(output_artifact_refs=_dump(artifacts), completion_receipt_ref=receipt_ref,
                               finished_at=now)
            elif target in {MediaJobStatus.FAILED, MediaJobStatus.CANCELLED}:
                if not reason_code:
                    self._conflict("failed or cancelled media job requires reason code")
                receipt_ref = self._receipt_ref(
                    "media", "MediaJobReceipt", scope, job_id, operation,
                    idempotency_key, request_hash,
                )
                updates.update(reason_code=reason_code, completion_receipt_ref=receipt_ref, finished_at=now)
            elif target is MediaJobStatus.UNKNOWN:
                if not blockers:
                    self._conflict("unknown media job requires blockers")
                updates["blockers"] = _dump(blockers)
            self._update_head(conn, "aip_media_job", "job_id", scope, job_id, updates, expected_version)
            self._event(conn, "media", scope, job_id, sequence, event_kind.value,
                        {"status": target.value, "reasonCode": reason_code,
                         "blockers": _dump(blockers or [])}, actor, now)
            snapshot = self._media_snapshot(conn, scope, job_id)
            self._receipt(conn, "media", scope, job_id, operation, idempotency_key,
                          request_hash, snapshot, actor, now)
            conn.commit()
            return snapshot

    def open_avatar_session(
        self,
        scope: TenantScope,
        request: AvatarSessionOpenRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime | None = None,
    ) -> AvatarSessionSnapshot:
        self._identity(idempotency_key, actor)
        now = occurred_at or datetime.now(UTC)
        payload = request.model_dump(mode="json", by_alias=True)
        request_hash = _hash({"scope": scope.key, "request": payload, "actor": actor})
        session_id = _id("avatar-session", scope, idempotency_key)
        with connect(scope) as conn:
            replay = self._replay(conn, "aip_avatar_session_receipt", scope, "open", idempotency_key, request_hash)
            if replay:
                return AvatarSessionSnapshot.model_validate(replay)
            self._require_run_step(conn, scope, request.task_run_ref.resource_id, request.step_run_ref.resource_id)
            conn.execute(
                """INSERT INTO aip_avatar_session(
                  org_id,project_id,session_id,task_run_id,step_run_id,request_json,
                  request_hash,idempotency_key,capability_binding_ref,budget_ref,
                  kill_policy_ref,max_duration_seconds,status,latest_sequence,version,
                  created_by,created_at,updated_at)
                  VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                    %s,'opening',1,1,%s,%s,%s)""",
                (*scope.key, session_id, request.task_run_ref.resource_id,
                 request.step_run_ref.resource_id, _json(payload), request_hash,
                 idempotency_key, _json(_dump(request.capability_binding_ref)),
                 _json(_dump(request.budget_ref)), _json(_dump(request.kill_policy_ref)),
                 request.max_duration_seconds, actor, now, now),
            )
            self._event(conn, "avatar", scope, session_id, 1, AvatarSessionEventKind.OPENED.value,
                        {"status": AvatarSessionStatus.OPENING.value}, actor, now)
            snapshot = self._avatar_snapshot(conn, scope, session_id)
            self._receipt(conn, "avatar", scope, session_id, "open", idempotency_key,
                          request_hash, snapshot, actor, now)
            conn.commit()
            return snapshot

    def get_avatar_session(self, scope: TenantScope, session_id: str) -> AvatarSessionSnapshot:
        with connect(scope) as conn:
            return self._avatar_snapshot(conn, scope, session_id)

    def command_avatar_session(
        self,
        scope: TenantScope,
        session_id: str,
        operation: str,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        engine_session_ref: ExactRevisionRef | None = None,
        heartbeat_at: datetime | None = None,
        heartbeat_expires_at: datetime | None = None,
        blockers: list[ContractBlocker] | None = None,
        reason_code: str | None = None,
        reconcile_status: AvatarSessionStatus | None = None,
        occurred_at: datetime | None = None,
    ) -> AvatarSessionSnapshot:
        self._identity(idempotency_key, actor)
        allowed = {"ready", "live", "heartbeat", "pause", "resume", "closing", "close",
                   "fail", "kill", "mark_unknown", "reconcile"}
        if operation not in allowed:
            raise ValueError("unsupported avatar session operation")
        now = occurred_at or datetime.now(UTC)
        command = {"sessionId": session_id, "operation": operation,
                   "expectedVersion": expected_version, "engineSessionRef": _dump(engine_session_ref),
                   "heartbeatAt": heartbeat_at, "heartbeatExpiresAt": heartbeat_expires_at,
                   "blockers": _dump(blockers or []), "reasonCode": reason_code,
                   "reconcileStatus": reconcile_status.value if reconcile_status else None, "actor": actor}
        request_hash = _hash(command)
        with connect(scope) as conn:
            replay = self._replay(conn, "aip_avatar_session_receipt", scope, operation, idempotency_key, request_hash)
            if replay:
                return AvatarSessionSnapshot.model_validate(replay)
            row = self._avatar_row(conn, scope, session_id, lock=True)
            self._cas(row, expected_version)
            current = AvatarSessionStatus(row["status"])
            target, event_kind = self._avatar_transition(current, operation, reconcile_status)
            sequence = int(row["latest_sequence"]) + 1
            updates: dict[str, Any] = {
                "status": target.value, "latest_sequence": sequence,
                "version": expected_version + 1, "updated_at": now,
                "engine_session_ref": dict(row["engine_session_ref"] or {}) or None,
                "human_heartbeat_at": None, "human_heartbeat_expires_at": None,
                "completion_receipt_ref": None, "blockers": [], "reason_code": None,
                "finished_at": None,
            }
            if target is AvatarSessionStatus.LIVE:
                effective_engine = engine_session_ref or (
                    ExactRevisionRef.model_validate(row["engine_session_ref"])
                    if row["engine_session_ref"] else None
                )
                if not effective_engine or effective_engine.resource_type != "OpaqueAvatarEngineSessionRef":
                    self._conflict("live avatar session requires opaque engine session ref")
                if not heartbeat_at or not heartbeat_expires_at or heartbeat_expires_at <= heartbeat_at or heartbeat_expires_at <= now:
                    self._conflict("live avatar session requires a live human heartbeat")
                if operation == "heartbeat" and heartbeat_at <= row["human_heartbeat_at"]:
                    self._conflict("avatar heartbeat must advance time")
                updates.update(engine_session_ref=_dump(effective_engine), human_heartbeat_at=heartbeat_at,
                               human_heartbeat_expires_at=heartbeat_expires_at)
            if target in {AvatarSessionStatus.CLOSED, AvatarSessionStatus.FAILED, AvatarSessionStatus.KILLED}:
                if target in {AvatarSessionStatus.FAILED, AvatarSessionStatus.KILLED} and not reason_code:
                    self._conflict("failed or killed avatar session requires reason code")
                receipt_ref = self._receipt_ref(
                    "avatar", "AvatarSessionReceipt", scope, session_id, operation,
                    idempotency_key, request_hash,
                )
                updates.update(completion_receipt_ref=receipt_ref, reason_code=reason_code, finished_at=now)
            elif target is AvatarSessionStatus.UNKNOWN:
                if not blockers:
                    self._conflict("unknown avatar session requires blockers")
                updates["blockers"] = _dump(blockers)
            self._update_head(conn, "aip_avatar_session", "session_id", scope, session_id, updates, expected_version)
            self._event(conn, "avatar", scope, session_id, sequence, event_kind.value,
                        {"status": target.value, "reasonCode": reason_code,
                         "blockers": _dump(blockers or [])}, actor, now)
            snapshot = self._avatar_snapshot(conn, scope, session_id)
            self._receipt(conn, "avatar", scope, session_id, operation, idempotency_key,
                          request_hash, snapshot, actor, now)
            conn.commit()
            return snapshot

    @staticmethod
    def _media_transition(current: MediaJobStatus, operation: str,
                          reconcile: MediaJobStatus | None) -> tuple[MediaJobStatus, MediaJobEventKind]:
        if operation == "claim" and current is MediaJobStatus.QUEUED:
            return MediaJobStatus.RUNNING, MediaJobEventKind.CLAIMED
        if operation == "heartbeat" and current is MediaJobStatus.RUNNING:
            return current, MediaJobEventKind.HEARTBEAT
        if operation == "succeed" and current is MediaJobStatus.RUNNING:
            return MediaJobStatus.SUCCEEDED, MediaJobEventKind.SUCCEEDED
        if operation in {"fail", "cancel"} and current in {MediaJobStatus.QUEUED, MediaJobStatus.RUNNING}:
            target = MediaJobStatus.FAILED if operation == "fail" else MediaJobStatus.CANCELLED
            kind = MediaJobEventKind.FAILED if operation == "fail" else MediaJobEventKind.CANCELLED
            return target, kind
        if operation == "mark_unknown" and current in {MediaJobStatus.QUEUED, MediaJobStatus.RUNNING}:
            return MediaJobStatus.UNKNOWN, MediaJobEventKind.UNKNOWN
        if operation == "reconcile" and current is MediaJobStatus.UNKNOWN and reconcile in {
            MediaJobStatus.QUEUED, MediaJobStatus.FAILED, MediaJobStatus.CANCELLED
        }:
            return reconcile, MediaJobEventKind.RECONCILED
        AipContentRuntimeStore._conflict("invalid media job transition")

    @staticmethod
    def _avatar_transition(current: AvatarSessionStatus, operation: str,
                           reconcile: AvatarSessionStatus | None) -> tuple[AvatarSessionStatus, AvatarSessionEventKind]:
        rules = {
            "ready": ({AvatarSessionStatus.OPENING}, AvatarSessionStatus.READY, AvatarSessionEventKind.READY),
            "live": ({AvatarSessionStatus.READY}, AvatarSessionStatus.LIVE, AvatarSessionEventKind.LIVE),
            "heartbeat": ({AvatarSessionStatus.LIVE}, AvatarSessionStatus.LIVE, AvatarSessionEventKind.HEARTBEAT),
            "pause": ({AvatarSessionStatus.LIVE}, AvatarSessionStatus.PAUSED, AvatarSessionEventKind.PAUSED),
            "resume": ({AvatarSessionStatus.PAUSED}, AvatarSessionStatus.LIVE, AvatarSessionEventKind.RESUMED),
            "closing": ({AvatarSessionStatus.READY, AvatarSessionStatus.LIVE, AvatarSessionStatus.PAUSED}, AvatarSessionStatus.CLOSING, AvatarSessionEventKind.CLOSING),
            "close": ({AvatarSessionStatus.CLOSING}, AvatarSessionStatus.CLOSED, AvatarSessionEventKind.CLOSED),
        }
        if operation in rules and current in rules[operation][0]:
            _, target, kind = rules[operation]
            return target, kind
        active = {AvatarSessionStatus.OPENING, AvatarSessionStatus.READY, AvatarSessionStatus.LIVE,
                  AvatarSessionStatus.PAUSED, AvatarSessionStatus.CLOSING}
        if operation in {"fail", "kill"} and current in active | {AvatarSessionStatus.UNKNOWN}:
            target = AvatarSessionStatus.FAILED if operation == "fail" else AvatarSessionStatus.KILLED
            kind = AvatarSessionEventKind.FAILED if operation == "fail" else AvatarSessionEventKind.KILLED
            return target, kind
        if operation == "mark_unknown" and current in active:
            return AvatarSessionStatus.UNKNOWN, AvatarSessionEventKind.UNKNOWN
        if operation == "reconcile" and current is AvatarSessionStatus.UNKNOWN and reconcile in {
            AvatarSessionStatus.OPENING, AvatarSessionStatus.FAILED, AvatarSessionStatus.KILLED
        }:
            return reconcile, AvatarSessionEventKind.RECONCILED
        AipContentRuntimeStore._conflict("invalid avatar session transition")

    @staticmethod
    def _require_run_step(conn: Any, scope: TenantScope, run_id: str, step_run_id: str) -> None:
        row = conn.execute(
            """SELECT 1 FROM aip_step_run WHERE org_id=%s AND project_id=%s
               AND run_id=%s AND step_run_id=%s""", (*scope.key, run_id, step_run_id)
        ).fetchone()
        if row is None:
            raise ApiError(code="CONTENT_RUNTIME_PARENT_NOT_FOUND", message="exact TaskRun/StepRun not found", status_code=409)

    @staticmethod
    def _update_head(conn: Any, table: str, id_column: str, scope: TenantScope,
                     resource_id: str, updates: dict[str, Any], expected_version: int) -> None:
        assignments = ",".join(f"{key}=%s" + ("::jsonb" if key in {
            "executor_lease_ref", "output_artifact_refs", "completion_receipt_ref", "blockers",
            "engine_session_ref"} else "") for key in updates)
        values = [_json(value) if key in {"executor_lease_ref", "output_artifact_refs",
                  "completion_receipt_ref", "blockers", "engine_session_ref"} and value is not None
                  else value for key, value in updates.items()]
        result = conn.execute(
            f"UPDATE {table} SET {assignments} WHERE org_id=%s AND project_id=%s "
            f"AND {id_column}=%s AND version=%s",
            (*values, *scope.key, resource_id, expected_version),
        )
        if result.rowcount != 1:
            AipContentRuntimeStore._conflict("runtime authority version changed")

    @staticmethod
    def _event(conn: Any, kind: str, scope: TenantScope, resource_id: str, sequence: int,
               event_kind: str, payload: dict[str, Any], actor: str, occurred_at: datetime) -> None:
        table = f"aip_{'media_job' if kind == 'media' else 'avatar_session'}_event"
        id_column = "job_id" if kind == "media" else "session_id"
        event_hash = _hash({"sequence": sequence, "kind": event_kind, "payload": payload})
        event_id = _id(f"{kind}-event", scope, resource_id, sequence, event_hash)
        conn.execute(
            f"""INSERT INTO {table}(org_id,project_id,event_id,{id_column},sequence,
                event_kind,event_json,event_hash,actor,occurred_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
            (*scope.key, event_id, resource_id, sequence, event_kind, _json(payload),
             event_hash, actor, occurred_at),
        )

    @staticmethod
    def _receipt(conn: Any, kind: str, scope: TenantScope, resource_id: str,
                 operation: str, key: str, request_hash: str, response: Any,
                 actor: str, occurred_at: datetime) -> None:
        table = f"aip_{'media_job' if kind == 'media' else 'avatar_session'}_receipt"
        id_column = "job_id" if kind == "media" else "session_id"
        payload = response.model_dump(mode="json", by_alias=True)
        response_hash = _hash(payload)
        receipt_id = _id(f"{kind}-receipt", scope, resource_id, operation, key)
        conn.execute(
            f"""INSERT INTO {table}(org_id,project_id,receipt_id,{id_column},operation,
                idempotency_key,request_hash,response_json,response_hash,actor,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
            (*scope.key, receipt_id, resource_id, operation, key, request_hash,
             _json(payload), response_hash, actor, occurred_at),
        )

    @staticmethod
    def _replay(conn: Any, table: str, scope: TenantScope, operation: str,
                key: str, request_hash: str) -> dict[str, Any] | None:
        row = conn.execute(
            f"""SELECT request_hash,response_json FROM {table}
                WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s""",
            (*scope.key, operation, key),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise ApiError(code="IDEMPOTENCY_CONFLICT", message="idempotency key payload differs", status_code=409)
        return dict(row["response_json"])

    @staticmethod
    def _receipt_ref(kind: str, resource_type: str, scope: TenantScope,
                     resource_id: str, operation: str, idempotency_key: str,
                     request_hash: str) -> dict[str, Any]:
        receipt_id = _id(f"{kind}-receipt", scope, resource_id, operation, idempotency_key)
        return {"resourceType": resource_type, "resourceId": receipt_id, "revision": 1,
                "contentHash": _hash({"receiptId": receipt_id, "requestHash": request_hash})}

    def _media_snapshot(self, conn: Any, scope: TenantScope, job_id: str) -> MediaJobSnapshot:
        row = self._media_row(conn, scope, job_id)
        request = MediaJobCreateRequest.model_validate(row["request_json"])
        return MediaJobSnapshot(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            jobId=job_id, requestHash=row["request_hash"], taskRunRef=request.task_run_ref,
            stepRunRef=request.step_run_ref, jobKind=row["job_kind"], attempt=row["attempt"],
            status=row["status"], latestSequence=row["latest_sequence"],
            executorLeaseRef=row["executor_lease_ref"], heartbeatAt=row["heartbeat_at"],
            leaseExpiresAt=row["lease_expires_at"], outputArtifactRefs=row["output_artifact_refs"],
            completionReceiptRef=row["completion_receipt_ref"], blockers=row["blockers"],
            reasonCode=row["reason_code"], createdAt=row["created_at"], updatedAt=row["updated_at"],
            finishedAt=row["finished_at"])

    def _avatar_snapshot(self, conn: Any, scope: TenantScope, session_id: str) -> AvatarSessionSnapshot:
        row = self._avatar_row(conn, scope, session_id)
        request = AvatarSessionOpenRequest.model_validate(row["request_json"])
        return AvatarSessionSnapshot(tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            sessionId=session_id, requestHash=row["request_hash"], taskRunRef=request.task_run_ref,
            stepRunRef=request.step_run_ref, capabilityBindingRef=row["capability_binding_ref"],
            budgetRef=row["budget_ref"], killPolicyRef=row["kill_policy_ref"],
            maxDurationSeconds=row["max_duration_seconds"], status=row["status"],
            latestSequence=row["latest_sequence"], engineSessionRef=row["engine_session_ref"],
            humanHeartbeatAt=row["human_heartbeat_at"],
            humanHeartbeatExpiresAt=row["human_heartbeat_expires_at"],
            completionReceiptRef=row["completion_receipt_ref"], blockers=row["blockers"],
            reasonCode=row["reason_code"], createdAt=row["created_at"], updatedAt=row["updated_at"],
            finishedAt=row["finished_at"])

    @staticmethod
    def _media_row(conn: Any, scope: TenantScope, job_id: str, *, lock: bool = False):
        suffix = " FOR UPDATE" if lock else ""
        row = conn.execute("SELECT * FROM aip_media_job WHERE org_id=%s AND project_id=%s AND job_id=%s" + suffix,
                           (*scope.key, job_id)).fetchone()
        if row is None:
            raise ApiError(code="CONTENT_MEDIA_JOB_NOT_FOUND", message="media job not found", status_code=404)
        return row

    @staticmethod
    def _avatar_row(conn: Any, scope: TenantScope, session_id: str, *, lock: bool = False):
        suffix = " FOR UPDATE" if lock else ""
        row = conn.execute("SELECT * FROM aip_avatar_session WHERE org_id=%s AND project_id=%s AND session_id=%s" + suffix,
                           (*scope.key, session_id)).fetchone()
        if row is None:
            raise ApiError(code="CONTENT_AVATAR_SESSION_NOT_FOUND", message="avatar session not found", status_code=404)
        return row

    @staticmethod
    def _cas(row: Any, expected_version: int) -> None:
        if int(row["version"]) != expected_version:
            raise ApiError(code="REVISION_CONFLICT", message="runtime authority version changed", status_code=412,
                           details={"expected": expected_version, "actual": int(row["version"])})

    @staticmethod
    def _identity(key: str, actor: str) -> None:
        if not key.strip() or not actor.strip():
            raise ValueError("idempotency key and actor are required")

    @staticmethod
    def _conflict(message: str):
        raise ApiError(code="CONTENT_RUNTIME_TRANSITION_BLOCKED", message=message, status_code=409)
