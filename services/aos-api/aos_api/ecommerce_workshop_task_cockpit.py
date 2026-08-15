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

from aos_api.aip_contracts import TaskRunStatus
from aos_api.db import connect
from aos_api.ecommerce_workshop_task_cockpit_contracts import (
    TASK_COCKPIT_SCHEMA_VERSION,
    TaskCockpitBlocker,
    TaskCockpitBlockerSeverity,
    TaskCockpitCoreEnvelope,
    TaskCockpitPageInfo,
    TaskCockpitReadiness,
    TaskCockpitRunSummary,
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
    last_updated_at: datetime,
    last_task_id: str,
) -> str:
    body = {
        "v": _CURSOR_VERSION,
        "orgId": scope.org_id,
        "projectId": scope.project_id,
        "status": status.value if status is not None else None,
        "cutoff": _format_time(cutoff),
        "lastUpdatedAt": _format_time(last_updated_at),
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
) -> tuple[datetime, datetime, str]:
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
            "lastUpdatedAt",
            "lastTaskId",
        }
        valid = (
            set(payload) == expected_keys
            and payload["v"] == _CURSOR_VERSION
            and payload["orgId"] == scope.org_id
            and payload["projectId"] == scope.project_id
            and payload["status"] == (status.value if status is not None else None)
            and isinstance(payload["lastTaskId"], str)
            and bool(payload["lastTaskId"])
            and checksum == _checksum(payload)
        )
        if not valid:
            raise ValueError("cursor identity or checksum mismatch")
        cutoff = _parse_time(payload["cutoff"])
        last_updated_at = _parse_time(payload["lastUpdatedAt"])
        if last_updated_at > cutoff:
            raise ValueError("cursor boundary exceeds cutoff")
        return cutoff, last_updated_at, payload["lastTaskId"]
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
            boundary: tuple[datetime, str] | None = None
        else:
            cutoff, last_updated_at, last_task_id = _decode_cursor(
                cursor, scope=scope, status=status
            )
            boundary = (last_updated_at, last_task_id)

        try:
            with self._connect_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_transaction_scope(conn, scope)
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
                last_updated_at=last["task_updated_at"],
                last_task_id=str(last["task_id"]),
            )
        return TaskCockpitCoreEnvelope(
            schemaVersion=TASK_COCKPIT_SCHEMA_VERSION,
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            evaluatedAt=evaluated_at,
            taskCutoff=cutoff,
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
        clauses = ["t.org_id=%s", "t.project_id=%s", "t.updated_at<=%s"]
        params: list[Any] = [cutoff, scope.org_id, scope.project_id, cutoff]
        if status is not None:
            clauses.append("t.status=%s")
            params.append(status.value)
        if boundary is not None:
            clauses.append("(t.updated_at,t.task_id)<(%s,%s)")
            params.extend(boundary)
        params.append(limit + 1)
        return conn.execute(
            f"""SELECT t.task_id,t.task_type,t.title,t.status AS task_status,
                       t.priority,t.version AS task_version,
                       t.current_plan_revision_id,t.updated_at AS task_updated_at,
                       run.run_id,run.plan_revision_id,run.status AS run_status,
                       run.version AS run_version,run.started_at,run.finished_at,
                       run.updated_at AS run_updated_at
                  FROM aip_task t
                  LEFT JOIN LATERAL (
                    SELECT r.run_id,r.plan_revision_id,r.status,r.version,
                           r.started_at,r.finished_at,r.updated_at
                      FROM aip_task_run r
                     WHERE r.org_id=t.org_id AND r.project_id=t.project_id
                       AND r.task_id=t.task_id
                       AND r.updated_at<=%s
                     ORDER BY r.updated_at DESC,r.run_id DESC
                     LIMIT 1
                  ) run ON TRUE
                 WHERE {' AND '.join(clauses)}
                 ORDER BY t.updated_at DESC,t.task_id DESC
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
