"""Tenant-scoped, read-only Task Cockpit core projection."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from functools import partial
from typing import Any

import psycopg

from aos_api.aip_contracts import StepRunStatus, TaskRunStatus
from aos_api.db import connect
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TASK_COCKPIT_SCHEMA_VERSION,
    TaskCockpitBlocker,
    TaskCockpitBlockerSeverity,
    TaskCockpitCheckpointPageEnvelope,
    TaskCockpitCheckpointSummary,
    TaskCockpitCoreEnvelope,
    TaskCockpitPageInfo,
    TaskCockpitReadiness,
    TaskCockpitRunSummary,
    TaskCockpitStateConsistency,
    TaskCockpitStepPageEnvelope,
    TaskCockpitStepSummary,
    TaskCockpitTaskSummary,
)
from aos_api.errors import ApiError
from aos_api.public_contracts import TaskStatus
from aos_api.tenant_scope import TenantScope, apply_transaction_scope

ConnectFactory = Callable[[], AbstractContextManager[Any]]
Clock = Callable[[], datetime]

_CURSOR_VERSION = 1
_BLOCKERS = (
    TaskCockpitBlocker(
        code="TASK_COCKPIT_STAGE_MAPPING_UNAVAILABLE",
        severity=TaskCockpitBlockerSeverity.WARNING,
        dependency="aip.production.stage-compilation",
        requiredAction=(
            "接入签名 StageTemplate 到 PlanStep/StepRun 的 exact compilation mapping"
        ),
    ),
    TaskCockpitBlocker(
        code="TASK_COCKPIT_RESPONSIBILITY_HANDOFF_UNAVAILABLE",
        severity=TaskCockpitBlockerSeverity.WARNING,
        dependency="aip.responsibility-handoff-readers",
        requiredAction=(
            "接入 Responsibility、assignee readiness、Handoff、Approval "
            "与 ReviewIssue exact readers"
        ),
    ),
    TaskCockpitBlocker(
        code="TASK_COCKPIT_BUSINESS_CONTEXT_BLOCKED",
        severity=TaskCockpitBlockerSeverity.WARNING,
        dependency="ecommerce.source-readiness",
        requiredAction=(
            "等待 W2-00 SourceReadinessEnvelope 后再启用业务上下文 enrichment"
        ),
    ),
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _format_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("cursor timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("cursor timestamp requires a timezone")
    return parsed.astimezone(UTC)


def _encode_cursor(
    *,
    scope: TenantScope,
    status: TaskStatus | None,
    cutoff: datetime,
    snapshot_hash: str,
    last_created_at: datetime,
    last_task_id: str,
) -> str:
    body = {
        "v": _CURSOR_VERSION,
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "status": status.value if status is not None else None,
        "cutoff": _format_time(cutoff),
        "snapshotHash": snapshot_hash,
        "lastCreatedAt": _format_time(last_created_at),
        "lastTaskId": last_task_id,
    }
    payload = {**body, "checksum": _checksum(body)}
    return base64.urlsafe_b64encode(_canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    ).rstrip("=")


def _decode_cursor(
    value: str,
    *,
    scope: TenantScope,
    status: TaskStatus | None,
) -> tuple[datetime, str, datetime, str]:
    invalid = ApiError(
        code="TASK_COCKPIT_CURSOR_INVALID",
        message="Task Cockpit cursor is invalid or does not match this query",
        status_code=400,
    )
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("cursor body must be an object")
        checksum = payload.pop("checksum")
        expected_keys = {
            "v",
            "orgId",
            "projectId",
            "status",
            "cutoff",
            "snapshotHash",
            "lastCreatedAt",
            "lastTaskId",
        }
        valid = (
            set(payload) == expected_keys
            and payload["v"] == _CURSOR_VERSION
            and payload["orgId"] == scope.org_id
            and payload["projectId"] == scope.project_id
            and payload["status"] == (status.value if status is not None else None)
            and isinstance(payload["snapshotHash"], str)
            and len(payload["snapshotHash"]) == 32
            and isinstance(payload["lastTaskId"], str)
            and bool(payload["lastTaskId"])
            and checksum == _checksum(payload)
        )
        if not valid:
            raise ValueError("cursor identity or checksum mismatch")
        cutoff = _parse_time(payload["cutoff"])
        last_created_at = _parse_time(payload["lastCreatedAt"])
        if last_created_at > cutoff:
            raise ValueError("cursor boundary exceeds cutoff")
        return cutoff, payload["snapshotHash"], last_created_at, payload["lastTaskId"]
    except (
        binascii.Error,
        ValueError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise invalid from None


def _encode_step_cursor(
    *,
    scope: TenantScope,
    run_id: str,
    cutoff: datetime,
    snapshot_hash: str,
    last_created_at: datetime,
    last_step_run_id: str,
) -> str:
    body = {
        "v": _CURSOR_VERSION,
        "kind": "step",
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "runId": run_id,
        "cutoff": _format_time(cutoff),
        "snapshotHash": snapshot_hash,
        "lastCreatedAt": _format_time(last_created_at),
        "lastId": last_step_run_id,
    }
    payload = {**body, "checksum": _checksum(body)}
    return base64.urlsafe_b64encode(_canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    ).rstrip("=")


def _encode_checkpoint_cursor(
    *,
    scope: TenantScope,
    run_id: str,
    cutoff: datetime,
    snapshot_hash: str,
    last_sequence: int,
    last_checkpoint_id: str,
) -> str:
    body = {
        "v": _CURSOR_VERSION,
        "kind": "checkpoint",
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "runId": run_id,
        "cutoff": _format_time(cutoff),
        "snapshotHash": snapshot_hash,
        "lastSequence": last_sequence,
        "lastId": last_checkpoint_id,
    }
    payload = {**body, "checksum": _checksum(body)}
    return base64.urlsafe_b64encode(_canonical_json(payload).encode("utf-8")).decode(
        "ascii"
    ).rstrip("=")


def _decode_detail_cursor(
    value: str,
    *,
    scope: TenantScope,
    run_id: str,
    kind: str,
) -> dict[str, Any]:
    invalid = ApiError(
        code="TASK_COCKPIT_CURSOR_INVALID",
        message="Task Cockpit cursor is invalid or does not match this query",
        status_code=400,
    )
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("cursor body must be an object")
        checksum = payload.pop("checksum")
        common = {
            "v",
            "kind",
            "orgId",
            "projectId",
            "runId",
            "cutoff",
            "lastId",
        }
        expected = common | (
            {"snapshotHash", "lastCreatedAt"}
            if kind == "step"
            else {"snapshotHash", "lastSequence"}
        )
        valid = (
            kind in {"step", "checkpoint"}
            and set(payload) == expected
            and payload["v"] == _CURSOR_VERSION
            and payload["kind"] == kind
            and payload["orgId"] == scope.org_id
            and payload["projectId"] == scope.project_id
            and payload["runId"] == run_id
            and isinstance(payload["lastId"], str)
            and bool(payload["lastId"])
            and checksum == _checksum(payload)
        )
        if not valid:
            raise ValueError("cursor identity or checksum mismatch")
        payload["cutoff"] = _parse_time(payload["cutoff"])
        if kind == "step":
            if not isinstance(payload["snapshotHash"], str) or len(
                payload["snapshotHash"]
            ) != 32:
                raise ValueError("step snapshot hash is invalid")
            payload["lastCreatedAt"] = _parse_time(payload["lastCreatedAt"])
            if payload["lastCreatedAt"] > payload["cutoff"]:
                raise ValueError("cursor boundary exceeds cutoff")
        else:
            if not isinstance(payload["snapshotHash"], str) or len(
                payload["snapshotHash"]
            ) != 32:
                raise ValueError("checkpoint snapshot hash is invalid")
            if not isinstance(payload["lastSequence"], int) or payload[
                "lastSequence"
            ] < 1:
                raise ValueError("checkpoint sequence is invalid")
        return payload
    except (
        binascii.Error,
        ValueError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise invalid from None


class TaskCockpitPersistenceError(RuntimeError):
    pass


class EcommerceWorkshopTaskCockpit:
    """Read canonical AIP Task/Run rows without creating a second authority."""

    def __init__(
        self,
        *,
        connect_factory: ConnectFactory | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._connect_factory = connect_factory or partial(connect, inherit_scope=False)
        self._clock = clock or (lambda: datetime.now(UTC))

    def read_core(
        self,
        *,
        org_id: str,
        project_id: str,
        status: TaskStatus | None,
        limit: int,
        cursor: str | None,
    ) -> TaskCockpitCoreEnvelope:
        scope = TenantScope(org_id, project_id)
        if not 1 <= limit <= 100:
            raise ApiError(
                code="VALIDATION",
                message="Task Cockpit limit must be between 1 and 100",
                status_code=400,
            )
        evaluated_at = self._aware_now()
        if cursor is None:
            cutoff = evaluated_at
            expected_snapshot_hash = None
            boundary: tuple[datetime, str] | None = None
        else:
            cutoff, expected_snapshot_hash, last_created_at, last_task_id = (
                _decode_cursor(cursor, scope=scope, status=status)
            )
            boundary = (last_created_at, last_task_id)

        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                snapshot_hash = self._read_core_snapshot_hash(
                    conn, scope=scope, status=status, cutoff=cutoff
                )
                self._require_current_snapshot(
                    expected=expected_snapshot_hash, actual=snapshot_hash
                )
                rows = self._read_rows(
                    conn,
                    scope=scope,
                    status=status,
                    cutoff=cutoff,
                    boundary=boundary,
                    limit=limit,
                )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit core projection"
            ) from exc

        has_more = len(rows) > limit
        visible = rows[:limit]
        items = [self._task_summary(row) for row in visible]
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = _encode_cursor(
                scope=scope,
                status=status,
                cutoff=cutoff,
                snapshot_hash=snapshot_hash,
                last_created_at=last["task_created_at"],
                last_task_id=str(last["task_id"]),
            )
        return TaskCockpitCoreEnvelope(
            schemaVersion=TASK_COCKPIT_SCHEMA_VERSION,
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            evaluatedAt=evaluated_at,
            taskCutoff=cutoff,
            stateConsistency=TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE,
            readiness=TaskCockpitReadiness.DEGRADED,
            blockers=list(_BLOCKERS),
            items=items,
            page=TaskCockpitPageInfo(
                limit=limit,
                count=len(items),
                hasMore=has_more,
                nextCursor=next_cursor,
            ),
        )

    def read_steps(
        self,
        *,
        org_id: str,
        project_id: str,
        run_id: str,
        limit: int,
        cursor: str | None,
    ) -> TaskCockpitStepPageEnvelope:
        scope = TenantScope(org_id, project_id)
        self._validate_detail_request(run_id=run_id, limit=limit)
        evaluated_at = self._aware_now()
        if cursor is None:
            cutoff = evaluated_at
            expected_snapshot_hash = None
            boundary: tuple[datetime, str] | None = None
        else:
            decoded = _decode_detail_cursor(
                cursor, scope=scope, run_id=run_id, kind="step"
            )
            cutoff = decoded["cutoff"]
            expected_snapshot_hash = decoded["snapshotHash"]
            boundary = (decoded["lastCreatedAt"], decoded["lastId"])

        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                self._require_run(conn, scope=scope, run_id=run_id)
                snapshot_hash = self._read_step_snapshot_hash(
                    conn, scope=scope, run_id=run_id, cutoff=cutoff
                )
                self._require_current_snapshot(
                    expected=expected_snapshot_hash, actual=snapshot_hash
                )
                rows = self._read_step_rows(
                    conn,
                    scope=scope,
                    run_id=run_id,
                    cutoff=cutoff,
                    boundary=boundary,
                    limit=limit,
                )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit StepRun projection"
            ) from exc

        has_more = len(rows) > limit
        visible = rows[:limit]
        items = [self._step_summary(row) for row in visible]
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = _encode_step_cursor(
                scope=scope,
                run_id=run_id,
                cutoff=cutoff,
                snapshot_hash=snapshot_hash,
                last_created_at=last["created_at"],
                last_step_run_id=str(last["step_run_id"]),
            )
        return TaskCockpitStepPageEnvelope(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            runId=run_id,
            evaluatedAt=evaluated_at,
            membershipCutoff=cutoff,
            stateConsistency=TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE,
            items=items,
            page=TaskCockpitPageInfo(
                limit=limit,
                count=len(items),
                hasMore=has_more,
                nextCursor=next_cursor,
            ),
        )

    def read_checkpoints(
        self,
        *,
        org_id: str,
        project_id: str,
        run_id: str,
        limit: int,
        cursor: str | None,
    ) -> TaskCockpitCheckpointPageEnvelope:
        scope = TenantScope(org_id, project_id)
        self._validate_detail_request(run_id=run_id, limit=limit)
        evaluated_at = self._aware_now()
        if cursor is None:
            cutoff = evaluated_at
            expected_snapshot_hash = None
            boundary: tuple[int, str] | None = None
        else:
            decoded = _decode_detail_cursor(
                cursor, scope=scope, run_id=run_id, kind="checkpoint"
            )
            cutoff = decoded["cutoff"]
            expected_snapshot_hash = decoded["snapshotHash"]
            boundary = (decoded["lastSequence"], decoded["lastId"])

        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
                self._require_run(conn, scope=scope, run_id=run_id)
                snapshot_hash = self._read_checkpoint_snapshot_hash(
                    conn, scope=scope, run_id=run_id, cutoff=cutoff
                )
                self._require_current_snapshot(
                    expected=expected_snapshot_hash, actual=snapshot_hash
                )
                rows = self._read_checkpoint_rows(
                    conn,
                    scope=scope,
                    run_id=run_id,
                    cutoff=cutoff,
                    boundary=boundary,
                    limit=limit,
                )
        except ApiError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise TaskCockpitPersistenceError(
                "failed to read Task Cockpit Checkpoint projection"
            ) from exc

        has_more = len(rows) > limit
        visible = rows[:limit]
        items = [self._checkpoint_summary(row) for row in visible]
        next_cursor = None
        if has_more and visible:
            last = visible[-1]
            next_cursor = _encode_checkpoint_cursor(
                scope=scope,
                run_id=run_id,
                cutoff=cutoff,
                snapshot_hash=snapshot_hash,
                last_sequence=int(last["sequence"]),
                last_checkpoint_id=str(last["checkpoint_id"]),
            )
        return TaskCockpitCheckpointPageEnvelope(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            runId=run_id,
            evaluatedAt=evaluated_at,
            membershipCutoff=cutoff,
            stateConsistency=TaskCockpitStateConsistency.CURRENT_STATE_PER_PAGE,
            items=items,
            page=TaskCockpitPageInfo(
                limit=limit,
                count=len(items),
                hasMore=has_more,
                nextCursor=next_cursor,
            ),
        )

    @staticmethod
    def _validate_detail_request(*, run_id: str, limit: int) -> None:
        if not run_id or run_id != run_id.strip() or len(run_id) > 200:
            raise ApiError(
                code="VALIDATION",
                message="Task Cockpit runId is invalid",
                status_code=400,
            )
        if not 1 <= limit <= 100:
            raise ApiError(
                code="VALIDATION",
                message="Task Cockpit limit must be between 1 and 100",
                status_code=400,
            )

    @staticmethod
    def _require_current_snapshot(*, expected: str | None, actual: str) -> None:
        if expected is not None and expected != actual:
            raise ApiError(
                code="TASK_COCKPIT_CURSOR_STALE",
                message="Task Cockpit data changed; restart pagination",
                status_code=409,
            )

    @staticmethod
    def _read_core_snapshot_hash(
        conn: Any,
        *,
        scope: TenantScope,
        status: TaskStatus | None,
        cutoff: datetime,
    ) -> str:
        status_clause = ""
        params: list[Any] = [cutoff, scope.org_id, scope.project_id, cutoff]
        if status is not None:
            status_clause = "AND t.status=%s"
            params.append(status.value)
        row = conn.execute(
            f"""SELECT md5(COALESCE(string_agg(
                         concat_ws(':',t.task_id,t.version,t.status,
                           COALESCE(run.run_id,''),
                           COALESCE(run.version::text,''),
                           COALESCE(run.status,'')),
                         '|' ORDER BY t.task_id),'EMPTY')) AS snapshot_hash
                  FROM aip_task t
                  LEFT JOIN LATERAL (
                    SELECT r.run_id,r.version,r.status
                      FROM aip_task_run r
                     WHERE r.org_id=t.org_id AND r.project_id=t.project_id
                       AND r.task_id=t.task_id AND r.created_at<=%s
                     ORDER BY r.created_at DESC,r.run_id DESC LIMIT 1
                  ) run ON TRUE
                 WHERE t.org_id=%s AND t.project_id=%s AND t.created_at<=%s
                       {status_clause}""",
            tuple(params),
        ).fetchone()
        if row is None or not isinstance(row["snapshot_hash"], str):
            raise ValueError("Task Cockpit snapshot hash is unavailable")
        return row["snapshot_hash"]

    @staticmethod
    def _require_run(conn: Any, *, scope: TenantScope, run_id: str) -> None:
        row = conn.execute(
            """SELECT 1 FROM aip_task_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (scope.org_id, scope.project_id, run_id),
        ).fetchone()
        if row is None:
            raise ApiError(
                code="TASK_COCKPIT_RUN_NOT_FOUND",
                message="Task Cockpit Run was not found",
                status_code=404,
            )

    @staticmethod
    def _read_step_snapshot_hash(
        conn: Any,
        *,
        scope: TenantScope,
        run_id: str,
        cutoff: datetime,
    ) -> str:
        row = conn.execute(
            """SELECT md5(COALESCE(string_agg(
                         concat_ws(':',step_run_id,attempt,status,token_count,
                           cost_amount::text,updated_at::text),
                         '|' ORDER BY step_run_id),'EMPTY')) AS snapshot_hash
                  FROM aip_step_run
                 WHERE org_id=%s AND project_id=%s AND run_id=%s
                   AND created_at<=%s""",
            (scope.org_id, scope.project_id, run_id, cutoff),
        ).fetchone()
        if row is None or not isinstance(row["snapshot_hash"], str):
            raise ValueError("Task Cockpit StepRun snapshot hash is unavailable")
        return row["snapshot_hash"]

    @staticmethod
    def _read_step_rows(
        conn: Any,
        *,
        scope: TenantScope,
        run_id: str,
        cutoff: datetime,
        boundary: tuple[datetime, str] | None,
        limit: int,
    ) -> list[Any]:
        clauses = [
            "org_id=%s",
            "project_id=%s",
            "run_id=%s",
            "created_at<=%s",
        ]
        params: list[Any] = [scope.org_id, scope.project_id, run_id, cutoff]
        if boundary is not None:
            clauses.append("(created_at,step_run_id)>(%s,%s)")
            params.extend(boundary)
        params.append(limit + 1)
        return conn.execute(
            f"""SELECT step_run_id,step_key,attempt,status,token_count,
                       cost_amount,created_at,updated_at,
                       jsonb_array_length(input_refs)>0 AS has_input_refs,
                       jsonb_array_length(output_refs)>0 AS has_output_refs,
                       COALESCE(jsonb_typeof(error)<>'null',false) AS has_error
                  FROM aip_step_run
                 WHERE {' AND '.join(clauses)}
                 ORDER BY created_at ASC,step_run_id ASC
                 LIMIT %s""",
            tuple(params),
        ).fetchall()

    @staticmethod
    def _read_checkpoint_snapshot_hash(
        conn: Any,
        *,
        scope: TenantScope,
        run_id: str,
        cutoff: datetime,
    ) -> str:
        row = conn.execute(
            """SELECT md5(COALESCE(string_agg(
                         concat_ws(':',checkpoint_id,sequence,schema_version,
                           COALESCE(step_key,''),state_hash,artifact_refs::text,
                           created_at::text),
                         '|' ORDER BY checkpoint_id),'EMPTY')) AS snapshot_hash
                  FROM aip_checkpoint
                 WHERE org_id=%s AND project_id=%s AND run_id=%s
                   AND created_at<=%s""",
            (scope.org_id, scope.project_id, run_id, cutoff),
        ).fetchone()
        if row is None or not isinstance(row["snapshot_hash"], str):
            raise ValueError("Task Cockpit Checkpoint snapshot hash is unavailable")
        return row["snapshot_hash"]

    @staticmethod
    def _read_checkpoint_rows(
        conn: Any,
        *,
        scope: TenantScope,
        run_id: str,
        cutoff: datetime,
        boundary: tuple[int, str] | None,
        limit: int,
    ) -> list[Any]:
        clauses = [
            "org_id=%s",
            "project_id=%s",
            "run_id=%s",
            "created_at<=%s",
        ]
        params: list[Any] = [scope.org_id, scope.project_id, run_id, cutoff]
        if boundary is not None:
            clauses.append("(sequence,checkpoint_id)>(%s,%s)")
            params.extend(boundary)
        params.append(limit + 1)
        return conn.execute(
            f"""SELECT checkpoint_id,sequence,schema_version,step_key,state_hash,
                       jsonb_array_length(artifact_refs) AS artifact_count,created_at
                  FROM aip_checkpoint
                 WHERE {' AND '.join(clauses)}
                 ORDER BY sequence ASC,checkpoint_id ASC
                 LIMIT %s""",
            tuple(params),
        ).fetchall()

    @staticmethod
    def _step_summary(row: Any) -> TaskCockpitStepSummary:
        return TaskCockpitStepSummary(
            stepRunId=str(row["step_run_id"]),
            stepKey=str(row["step_key"]),
            attempt=int(row["attempt"]),
            status=StepRunStatus(str(row["status"])),
            tokenCount=int(row["token_count"]),
            costAmount=row["cost_amount"],
            hasInputRefs=bool(row["has_input_refs"]),
            hasOutputRefs=bool(row["has_output_refs"]),
            hasError=bool(row["has_error"]),
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )

    @staticmethod
    def _checkpoint_summary(row: Any) -> TaskCockpitCheckpointSummary:
        return TaskCockpitCheckpointSummary(
            checkpointId=str(row["checkpoint_id"]),
            sequence=int(row["sequence"]),
            schemaVersion=int(row["schema_version"]),
            stepKey=row["step_key"],
            stateHash=str(row["state_hash"]),
            artifactCount=int(row["artifact_count"]),
            createdAt=row["created_at"],
        )

    @staticmethod
    def _read_rows(
        conn: Any,
        *,
        scope: TenantScope,
        status: TaskStatus | None,
        cutoff: datetime,
        boundary: tuple[datetime, str] | None,
        limit: int,
    ) -> list[Any]:
        clauses = ["t.org_id=%s", "t.project_id=%s", "t.created_at<=%s"]
        params: list[Any] = [cutoff, scope.org_id, scope.project_id, cutoff]
        if status is not None:
            clauses.append("t.status=%s")
            params.append(status.value)
        if boundary is not None:
            clauses.append("(t.created_at,t.task_id)<(%s,%s)")
            params.extend(boundary)
        params.append(limit + 1)
        return conn.execute(
            f"""SELECT t.task_id,t.task_type,t.title,t.status AS task_status,
                       t.priority,t.version AS task_version,
                       t.current_plan_revision_id,t.created_at AS task_created_at,
                       t.updated_at AS task_updated_at,
                       run.run_id,run.plan_revision_id,run.status AS run_status,
                       run.version AS run_version,run.started_at,run.finished_at,
                       run.created_at AS run_created_at,
                       run.updated_at AS run_updated_at
                  FROM aip_task t
                  LEFT JOIN LATERAL (
                    SELECT r.run_id,r.plan_revision_id,r.status,r.version,
                           r.started_at,r.finished_at,r.created_at,r.updated_at
                      FROM aip_task_run r
                     WHERE r.org_id=t.org_id AND r.project_id=t.project_id
                       AND r.task_id=t.task_id
                       AND r.created_at<=%s
                     ORDER BY r.created_at DESC,r.run_id DESC
                     LIMIT 1
                  ) run ON TRUE
                 WHERE {' AND '.join(clauses)}
                 ORDER BY t.created_at DESC,t.task_id DESC
                 LIMIT %s""",
            tuple(params),
        ).fetchall()

    @staticmethod
    def _task_summary(row: Any) -> TaskCockpitTaskSummary:
        run = None
        if row["run_id"] is not None:
            run = TaskCockpitRunSummary(
                runId=str(row["run_id"]),
                planRevisionId=str(row["plan_revision_id"]),
                status=TaskRunStatus(str(row["run_status"])),
                version=int(row["run_version"]),
                startedAt=row["started_at"],
                finishedAt=row["finished_at"],
                createdAt=row["run_created_at"],
                updatedAt=row["run_updated_at"],
            )
        return TaskCockpitTaskSummary(
            taskId=str(row["task_id"]),
            taskType=str(row["task_type"]),
            title=str(row["title"]),
            status=TaskStatus(str(row["task_status"])),
            priority=int(row["priority"]),
            version=int(row["task_version"]),
            currentPlanRevisionId=row["current_plan_revision_id"],
            createdAt=row["task_created_at"],
            updatedAt=row["task_updated_at"],
            run=run,
        )

    def _aware_now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise TaskCockpitPersistenceError("Task Cockpit clock must be timezone aware")
        return value.astimezone(UTC)


__all__ = [
    "EcommerceWorkshopTaskCockpit",
    "TaskCockpitPersistenceError",
    "_decode_cursor",
    "_encode_cursor",
]
