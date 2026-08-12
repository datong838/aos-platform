"""Tenant-scoped PostgreSQL authority for governed AIP knowledge pipelines."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta
from typing import Any

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_pipeline_contracts import (
    ClaimKnowledgePipelineRunRequest,
    CompleteKnowledgePipelineRunRequest,
    CreateKnowledgePipelineScheduleRequest,
    KnowledgePipelineAlert,
    KnowledgePipelineAlertSeverity,
    KnowledgePipelineCheckpointRevision,
    KnowledgePipelineReceipt,
    KnowledgePipelineRun,
    KnowledgePipelineRunEvent,
    KnowledgePipelineRunStatus,
    KnowledgePipelineSchedule,
    KnowledgePipelineScheduleEvent,
    KnowledgePipelineScheduleStatus,
    KnowledgePipelineTrigger,
    StartKnowledgePipelineRunRequest,
    TERMINAL_PIPELINE_RUN_STATUSES,
    TransitionKnowledgePipelineRunRequest,
    TransitionKnowledgePipelineScheduleRequest,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipMemoryPipelineStoreError(RuntimeError):
    code = "AIP_MEMORY_PIPELINE_STORE_ERROR"


class AipMemoryPipelineNotFound(AipMemoryPipelineStoreError):
    code = "AIP_MEMORY_PIPELINE_NOT_FOUND"


class AipMemoryPipelineConflict(AipMemoryPipelineStoreError):
    code = "AIP_MEMORY_PIPELINE_CONFLICT"


class AipMemoryPipelineTransitionBlocked(AipMemoryPipelineStoreError):
    code = "AIP_MEMORY_PIPELINE_TRANSITION_BLOCKED"


class AipMemoryPipelinePersistenceError(AipMemoryPipelineStoreError):
    code = "AIP_MEMORY_PIPELINE_PERSISTENCE_ERROR"


class AipMemoryPipelineStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create_schedule(
        self,
        scope: TenantScope,
        request: CreateKnowledgePipelineScheduleRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> KnowledgePipelineSchedule:
        self._validate_command(scope, idempotency_key, actor)
        request_hash = self._command_hash(request, actor)
        try:
            with self._connect(scope) as conn:
                self._idempotency_lock(conn, scope, "schedule", idempotency_key)
                replay = self._schedule_row_by_idempotency(conn, scope, idempotency_key)
                if replay is not None:
                    if replay["request_hash"] != request_hash:
                        raise AipMemoryPipelineConflict(
                            "schedule idempotency key was reused for different content"
                        )
                    return self._schedule_from_row(scope, replay)
                existing = self._schedule_row(conn, scope, request.schedule_id)
                if existing is not None:
                    raise AipMemoryPipelineConflict("schedule id already exists")
                row = conn.execute(
                    """INSERT INTO aip_memory_pipeline_schedule (
                       org_id,project_id,schedule_id,pipeline_kind,trigger,config_ref,
                       schedule_spec,status,checkpoint_version,next_run_at,
                       idempotency_key,request_hash,version,created_by,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,0,NULL,%s,%s,1,%s,%s,%s)
                       RETURNING *""",
                    (
                        *scope.key,
                        request.schedule_id,
                        request.pipeline_kind.value,
                        request.trigger.value,
                        self._json(request.config),
                        request.schedule_spec,
                        request.initial_status.value,
                        idempotency_key,
                        request_hash,
                        actor.strip(),
                        occurred_at,
                        occurred_at,
                    ),
                ).fetchone()
                event = self._schedule_event(
                    scope,
                    schedule_id=request.schedule_id,
                    sequence=1,
                    event_type="created",
                    from_status=None,
                    to_status=request.initial_status,
                    schedule_version=1,
                    reason_code="created",
                    dependency_review=None,
                    actor=actor,
                    occurred_at=occurred_at,
                )
                self._insert_schedule_event(conn, scope, event)
                conn.commit()
                return self._schedule_from_row(scope, row)
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline schedule persistence failed"
            ) from exc

    def get_schedule(
        self, scope: TenantScope, schedule_id: str
    ) -> KnowledgePipelineSchedule:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._schedule_row(conn, scope, schedule_id)
                if row is None:
                    raise AipMemoryPipelineNotFound("knowledge pipeline schedule not found")
                return self._schedule_from_row(scope, row)
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline schedule read failed"
            ) from exc

    def list_schedules(
        self, scope: TenantScope, *, limit: int = 100
    ) -> list[KnowledgePipelineSchedule]:
        self._require_scope(scope)
        self._validate_limit(limit)
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_memory_pipeline_schedule
                       WHERE org_id=%s AND project_id=%s
                       ORDER BY updated_at DESC,schedule_id LIMIT %s""",
                    (*scope.key, limit),
                ).fetchall()
                return [self._schedule_from_row(scope, row) for row in rows]
        except (AipMemoryPipelineStoreError, ValueError):
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline schedule list failed"
            ) from exc

    def transition_schedule(
        self,
        scope: TenantScope,
        schedule_id: str,
        request: TransitionKnowledgePipelineScheduleRequest,
        *,
        actor: str,
        occurred_at: datetime,
    ) -> tuple[KnowledgePipelineSchedule, KnowledgePipelineScheduleEvent]:
        self._validate_command(scope, schedule_id, actor)
        try:
            with self._connect(scope) as conn:
                row = self._schedule_row(conn, scope, schedule_id, for_update=True)
                if row is None:
                    raise AipMemoryPipelineNotFound("knowledge pipeline schedule not found")
                if int(row["version"]) != request.expected_version:
                    raise AipMemoryPipelineConflict("schedule version changed")
                current = KnowledgePipelineScheduleStatus(row["status"])
                if current is not request.from_status:
                    raise AipMemoryPipelineConflict("schedule status changed")
                updated = conn.execute(
                    """UPDATE aip_memory_pipeline_schedule
                       SET status=%s,version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND schedule_id=%s
                         AND version=%s AND status=%s RETURNING *""",
                    (
                        request.to_status.value,
                        occurred_at,
                        *scope.key,
                        schedule_id,
                        request.expected_version,
                        request.from_status.value,
                    ),
                ).fetchone()
                if updated is None:
                    raise AipMemoryPipelineConflict("schedule changed concurrently")
                event = self._schedule_event(
                    scope,
                    schedule_id=schedule_id,
                    sequence=self._next_schedule_event_sequence(conn, scope, schedule_id),
                    event_type="transitioned",
                    from_status=request.from_status,
                    to_status=request.to_status,
                    schedule_version=int(updated["version"]),
                    reason_code=request.reason_code,
                    dependency_review=request.dependency_review,
                    actor=actor,
                    occurred_at=occurred_at,
                )
                self._insert_schedule_event(conn, scope, event)
                conn.commit()
                return self._schedule_from_row(scope, updated), event
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline schedule transition failed"
            ) from exc

    def list_schedule_events(
        self, scope: TenantScope, schedule_id: str
    ) -> list[KnowledgePipelineScheduleEvent]:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_memory_pipeline_schedule_event
                       WHERE org_id=%s AND project_id=%s AND schedule_id=%s
                       ORDER BY sequence""",
                    (*scope.key, schedule_id),
                ).fetchall()
                return [self._schedule_event_from_row(scope, row) for row in rows]
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline schedule event read failed"
            ) from exc

    def start_run(
        self,
        scope: TenantScope,
        request: StartKnowledgePipelineRunRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> KnowledgePipelineRun:
        self._validate_command(scope, idempotency_key, actor)
        request_hash = self._command_hash(request, actor)
        try:
            with self._connect(scope) as conn:
                self._idempotency_lock(conn, scope, "run", idempotency_key)
                replay = self._run_row_by_idempotency(conn, scope, idempotency_key)
                if replay is not None:
                    if replay["request_hash"] != request_hash:
                        raise AipMemoryPipelineConflict(
                            "run idempotency key was reused for different content"
                        )
                    return self._run_from_row(scope, replay)
                if self._run_row(conn, scope, request.pipeline_run_id) is not None:
                    raise AipMemoryPipelineConflict("pipeline run id already exists")
                schedule = self._schedule_row(
                    conn, scope, request.schedule_id, for_update=True
                )
                if schedule is None:
                    raise AipMemoryPipelineNotFound("knowledge pipeline schedule not found")
                self._validate_schedule_trigger(schedule, request.trigger)
                if int(schedule["checkpoint_version"]) != request.expected_checkpoint_version:
                    raise AipMemoryPipelineConflict("pipeline checkpoint version changed")
                self._require_task_run(
                    conn, scope, request.task_id, request.run_id
                )
                attempt = 1
                if request.retry_of_run_id is not None:
                    retried = self._run_row(
                        conn, scope, request.retry_of_run_id, for_update=True
                    )
                    if retried is None:
                        raise AipMemoryPipelineNotFound("retried pipeline run not found")
                    if (
                        KnowledgePipelineRunStatus(retried["status"])
                        not in TERMINAL_PIPELINE_RUN_STATUSES
                    ):
                        raise AipMemoryPipelineTransitionBlocked(
                            "only terminal pipeline runs can be retried"
                        )
                    if (
                        retried["schedule_id"] != request.schedule_id
                        or retried["task_id"] != request.task_id
                        or retried["run_id"] != request.run_id
                    ):
                        raise AipMemoryPipelineConflict(
                            "retry must preserve schedule and AIP task/run binding"
                        )
                    attempt = int(retried["attempt"]) + 1
                row = conn.execute(
                    """INSERT INTO aip_memory_pipeline_run (
                       org_id,project_id,pipeline_run_id,schedule_id,task_id,run_id,
                       trigger,status,attempt,retry_of_run_id,expected_checkpoint_version,
                       idempotency_key,request_hash,version,scheduled_for,created_by,
                       created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s,%s,%s,%s,1,%s,%s,%s,%s)
                       RETURNING *""",
                    (
                        *scope.key,
                        request.pipeline_run_id,
                        request.schedule_id,
                        request.task_id,
                        request.run_id,
                        request.trigger.value,
                        attempt,
                        request.retry_of_run_id,
                        request.expected_checkpoint_version,
                        idempotency_key,
                        request_hash,
                        request.scheduled_for,
                        actor.strip(),
                        occurred_at,
                        occurred_at,
                    ),
                ).fetchone()
                event = self._run_event(
                    scope,
                    pipeline_run_id=request.pipeline_run_id,
                    sequence=1,
                    event_type="enqueued",
                    from_status=None,
                    to_status=KnowledgePipelineRunStatus.QUEUED,
                    run_version=1,
                    reason_code="enqueued",
                    lease_owner=None,
                    actor=actor,
                    occurred_at=occurred_at,
                )
                self._insert_run_event(conn, scope, event)
                conn.commit()
                return self._run_from_row(scope, row)
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline run persistence failed"
            ) from exc

    def get_run(self, scope: TenantScope, pipeline_run_id: str) -> KnowledgePipelineRun:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._run_row(conn, scope, pipeline_run_id)
                if row is None:
                    raise AipMemoryPipelineNotFound("knowledge pipeline run not found")
                return self._run_from_row(scope, row)
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline run read failed"
            ) from exc

    def list_runs(
        self,
        scope: TenantScope,
        *,
        schedule_id: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgePipelineRun]:
        self._require_scope(scope)
        self._validate_limit(limit)
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_memory_pipeline_run
                       WHERE org_id=%s AND project_id=%s
                         AND (%s::text IS NULL OR schedule_id=%s)
                       ORDER BY scheduled_for DESC,pipeline_run_id LIMIT %s""",
                    (*scope.key, schedule_id, schedule_id, limit),
                ).fetchall()
                return [self._run_from_row(scope, row) for row in rows]
        except (AipMemoryPipelineStoreError, ValueError):
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline run list failed"
            ) from exc

    def claim_run(
        self,
        scope: TenantScope,
        pipeline_run_id: str,
        request: ClaimKnowledgePipelineRunRequest,
        *,
        occurred_at: datetime,
    ) -> KnowledgePipelineRun:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._run_row(conn, scope, pipeline_run_id, for_update=True)
                if row is None:
                    raise AipMemoryPipelineNotFound("knowledge pipeline run not found")
                if int(row["version"]) != request.expected_version:
                    raise AipMemoryPipelineConflict("pipeline run version changed")
                if (
                    KnowledgePipelineRunStatus(row["status"])
                    is not KnowledgePipelineRunStatus.QUEUED
                ):
                    raise AipMemoryPipelineTransitionBlocked(
                        "only queued pipeline runs can be claimed"
                    )
                if row["scheduled_for"] > occurred_at:
                    raise AipMemoryPipelineTransitionBlocked(
                        "pipeline run cannot be claimed before its scheduled time"
                    )
                updated = conn.execute(
                    """UPDATE aip_memory_pipeline_run SET status='running',
                       lease_owner=%s,lease_expires_at=%s,
                       started_at=COALESCE(started_at,%s),version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s
                         AND version=%s AND status='queued' RETURNING *""",
                    (
                        request.lease_owner,
                        occurred_at + timedelta(seconds=request.lease_seconds),
                        occurred_at,
                        occurred_at,
                        *scope.key,
                        pipeline_run_id,
                        request.expected_version,
                    ),
                ).fetchone()
                if updated is None:
                    raise AipMemoryPipelineConflict("pipeline run changed concurrently")
                event = self._run_event(
                    scope,
                    pipeline_run_id=pipeline_run_id,
                    sequence=self._next_run_event_sequence(conn, scope, pipeline_run_id),
                    event_type="claimed",
                    from_status=KnowledgePipelineRunStatus.QUEUED,
                    to_status=KnowledgePipelineRunStatus.RUNNING,
                    run_version=int(updated["version"]),
                    reason_code="claimed",
                    lease_owner=request.lease_owner,
                    actor=request.lease_owner,
                    occurred_at=occurred_at,
                )
                self._insert_run_event(conn, scope, event)
                conn.commit()
                return self._run_from_row(scope, updated)
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline run claim failed"
            ) from exc

    def transition_run(
        self,
        scope: TenantScope,
        pipeline_run_id: str,
        request: TransitionKnowledgePipelineRunRequest,
        *,
        actor: str,
        occurred_at: datetime,
    ) -> KnowledgePipelineRun:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._run_row(conn, scope, pipeline_run_id, for_update=True)
                if row is None:
                    raise AipMemoryPipelineNotFound("knowledge pipeline run not found")
                if int(row["version"]) != request.expected_version:
                    raise AipMemoryPipelineConflict("pipeline run version changed")
                current = KnowledgePipelineRunStatus(row["status"])
                if current is not request.from_status:
                    raise AipMemoryPipelineConflict("pipeline run status changed")
                updated = conn.execute(
                    """UPDATE aip_memory_pipeline_run SET status=%s,
                       lease_owner=NULL,lease_expires_at=NULL,
                       version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s
                         AND version=%s AND status=%s RETURNING *""",
                    (
                        request.to_status.value,
                        occurred_at,
                        *scope.key,
                        pipeline_run_id,
                        request.expected_version,
                        request.from_status.value,
                    ),
                ).fetchone()
                if updated is None:
                    raise AipMemoryPipelineConflict("pipeline run changed concurrently")
                event = self._run_event(
                    scope,
                    pipeline_run_id=pipeline_run_id,
                    sequence=self._next_run_event_sequence(conn, scope, pipeline_run_id),
                    event_type=(
                        "paused"
                        if request.to_status is KnowledgePipelineRunStatus.PAUSED
                        else "resumed"
                    ),
                    from_status=request.from_status,
                    to_status=request.to_status,
                    run_version=int(updated["version"]),
                    reason_code=request.reason_code,
                    lease_owner=None,
                    actor=actor,
                    occurred_at=occurred_at,
                )
                self._insert_run_event(conn, scope, event)
                conn.commit()
                return self._run_from_row(scope, updated)
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline run transition failed"
            ) from exc

    def complete_run(
        self,
        scope: TenantScope,
        pipeline_run_id: str,
        request: CompleteKnowledgePipelineRunRequest,
        *,
        actor: str,
        occurred_at: datetime,
    ) -> KnowledgePipelineReceipt:
        self._validate_command(scope, pipeline_run_id, actor)
        try:
            with self._connect(scope) as conn:
                row = self._run_row(conn, scope, pipeline_run_id, for_update=True)
                if row is None:
                    raise AipMemoryPipelineNotFound("knowledge pipeline run not found")
                replay_row = self._receipt_row_for_run(conn, scope, pipeline_run_id)
                if replay_row is not None:
                    replay = self._receipt_from_row(conn, scope, replay_row)
                    if self._completion_matches(conn, scope, replay, request):
                        return replay
                    raise AipMemoryPipelineConflict(
                        "terminal pipeline run was replayed with different evidence"
                    )
                if int(row["version"]) != request.expected_run_version:
                    raise AipMemoryPipelineConflict("pipeline run version changed")
                if (
                    KnowledgePipelineRunStatus(row["status"])
                    is not KnowledgePipelineRunStatus.RUNNING
                ):
                    raise AipMemoryPipelineTransitionBlocked(
                        "only running pipeline runs can complete"
                    )
                if row["lease_owner"] != actor.strip():
                    raise AipMemoryPipelineTransitionBlocked(
                        "pipeline run completion requires the current lease owner"
                    )
                if (
                    row["lease_expires_at"] is None
                    or row["lease_expires_at"] <= occurred_at
                ):
                    raise AipMemoryPipelineTransitionBlocked(
                        "pipeline run lease expired before completion"
                    )
                try:
                    self._validate_candidate_refs(conn, scope, row, request.candidate_refs)
                except AipMemoryPipelineConflict:
                    self._insert_alert(
                        conn,
                        scope,
                        row,
                        code="candidate_binding_conflict",
                        severity=KnowledgePipelineAlertSeverity.ERROR,
                        occurred_at=occurred_at,
                    )
                    conn.commit()
                    raise
                schedule = self._schedule_row(
                    conn, scope, row["schedule_id"], for_update=True
                )
                before = int(schedule["checkpoint_version"])
                expected = int(row["expected_checkpoint_version"])
                if before != expected:
                    self._insert_alert(
                        conn,
                        scope,
                        row,
                        code="checkpoint_conflict",
                        severity=KnowledgePipelineAlertSeverity.ERROR,
                        occurred_at=occurred_at,
                    )
                    conn.commit()
                    raise AipMemoryPipelineConflict("pipeline checkpoint version changed")
                after = before + 1 if request.checkpoint is not None else before
                receipt = self._build_receipt(
                    scope,
                    row,
                    request,
                    checkpoint_before=before,
                    checkpoint_after=after,
                    occurred_at=occurred_at,
                )
                self._insert_receipt(conn, scope, receipt)
                for sequence, candidate in enumerate(request.candidate_refs, start=1):
                    conn.execute(
                        """INSERT INTO aip_memory_pipeline_receipt_candidate (
                           org_id,project_id,receipt_id,sequence,candidate_id,
                           candidate_revision,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            *scope.key,
                            receipt.receipt_id,
                            sequence,
                            candidate.resource_id,
                            int(candidate.revision or "0"),
                            occurred_at,
                        ),
                    )
                if request.checkpoint is not None:
                    checkpoint = KnowledgePipelineCheckpointRevision(
                        tenant=self._tenant(scope),
                        schedule_id=row["schedule_id"],
                        revision=after,
                        pipeline_run_id=pipeline_run_id,
                        receipt_id=receipt.receipt_id,
                        checkpoint=request.checkpoint,
                        checkpoint_hash=request.checkpoint.content_hash or "",
                        created_at=occurred_at,
                    )
                    conn.execute(
                        """INSERT INTO aip_memory_pipeline_checkpoint_revision (
                           org_id,project_id,schedule_id,revision,pipeline_run_id,
                           receipt_id,checkpoint_ref,checkpoint_hash,created_by,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                        (
                            *scope.key,
                            checkpoint.schedule_id,
                            checkpoint.revision,
                            pipeline_run_id,
                            receipt.receipt_id,
                            self._json(checkpoint.checkpoint),
                            checkpoint.checkpoint_hash,
                            actor.strip(),
                            occurred_at,
                        ),
                    )
                    updated_schedule = conn.execute(
                        """UPDATE aip_memory_pipeline_schedule
                           SET checkpoint_version=%s,version=version+1,updated_at=%s
                           WHERE org_id=%s AND project_id=%s AND schedule_id=%s
                             AND checkpoint_version=%s RETURNING schedule_id""",
                        (
                            after,
                            occurred_at,
                            *scope.key,
                            row["schedule_id"],
                            before,
                        ),
                    ).fetchone()
                    if updated_schedule is None:
                        raise AipMemoryPipelineConflict(
                            "pipeline checkpoint changed concurrently"
                        )
                updated_run = conn.execute(
                    """UPDATE aip_memory_pipeline_run SET status=%s,
                       lease_owner=NULL,lease_expires_at=NULL,finished_at=%s,
                       version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s
                         AND version=%s AND status='running' RETURNING pipeline_run_id""",
                    (
                        request.status.value,
                        occurred_at,
                        occurred_at,
                        *scope.key,
                        pipeline_run_id,
                        request.expected_run_version,
                    ),
                ).fetchone()
                if updated_run is None:
                    raise AipMemoryPipelineConflict("pipeline run changed concurrently")
                event = self._run_event(
                    scope,
                    pipeline_run_id=pipeline_run_id,
                    sequence=self._next_run_event_sequence(conn, scope, pipeline_run_id),
                    event_type="completed",
                    from_status=KnowledgePipelineRunStatus.RUNNING,
                    to_status=request.status,
                    run_version=request.expected_run_version + 1,
                    reason_code=(request.error_codes[0] if request.error_codes else "completed"),
                    lease_owner=actor.strip(),
                    actor=actor,
                    occurred_at=occurred_at,
                )
                self._insert_run_event(conn, scope, event)
                alert_codes = request.error_codes or (
                    ["pipeline_run_unknown"]
                    if request.status is KnowledgePipelineRunStatus.UNKNOWN
                    else []
                )
                severity = (
                    KnowledgePipelineAlertSeverity.CRITICAL
                    if request.status is KnowledgePipelineRunStatus.UNKNOWN
                    else KnowledgePipelineAlertSeverity.ERROR
                )
                for code in alert_codes:
                    self._insert_alert(
                        conn,
                        scope,
                        row,
                        code=code,
                        severity=severity,
                        occurred_at=occurred_at,
                        receipt=receipt,
                    )
                conn.commit()
                return receipt
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline completion persistence failed"
            ) from exc

    def expire_run_lease(
        self,
        scope: TenantScope,
        pipeline_run_id: str,
        *,
        expected_version: int,
        occurred_at: datetime,
    ) -> KnowledgePipelineReceipt:
        """Record an expired worker lease as unknown without retry assumptions."""
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._run_row(conn, scope, pipeline_run_id, for_update=True)
                if row is None:
                    raise AipMemoryPipelineNotFound("knowledge pipeline run not found")
                replay_row = self._receipt_row_for_run(conn, scope, pipeline_run_id)
                if replay_row is not None:
                    replay = self._receipt_from_row(conn, scope, replay_row)
                    if (
                        replay.status is KnowledgePipelineRunStatus.UNKNOWN
                        and replay.error_codes == ["lease_expired"]
                    ):
                        return replay
                    raise AipMemoryPipelineConflict(
                        "pipeline run already has different terminal evidence"
                    )
                if int(row["version"]) != expected_version:
                    raise AipMemoryPipelineConflict("pipeline run version changed")
                if (
                    KnowledgePipelineRunStatus(row["status"])
                    is not KnowledgePipelineRunStatus.RUNNING
                ):
                    raise AipMemoryPipelineTransitionBlocked(
                        "only a running pipeline lease can expire"
                    )
                if (
                    row["lease_expires_at"] is None
                    or row["lease_expires_at"] > occurred_at
                ):
                    raise AipMemoryPipelineTransitionBlocked(
                        "pipeline run lease is not expired"
                    )
                schedule = self._schedule_row(
                    conn, scope, row["schedule_id"], for_update=True
                )
                checkpoint_version = int(schedule["checkpoint_version"])
                completion = CompleteKnowledgePipelineRunRequest(
                    expected_run_version=expected_version,
                    status=KnowledgePipelineRunStatus.UNKNOWN,
                    input_hash=row["request_hash"],
                    output_hash=self._hash(
                        {
                            "pipelineRunId": pipeline_run_id,
                            "status": "unknown",
                            "code": "lease_expired",
                        }
                    ),
                    candidate_refs=[],
                    checkpoint=None,
                    produced_count=0,
                    failed_count=0,
                    error_codes=["lease_expired"],
                )
                receipt = self._build_receipt(
                    scope,
                    row,
                    completion,
                    checkpoint_before=checkpoint_version,
                    checkpoint_after=checkpoint_version,
                    occurred_at=occurred_at,
                )
                self._insert_receipt(conn, scope, receipt)
                updated = conn.execute(
                    """UPDATE aip_memory_pipeline_run SET status='unknown',
                       lease_owner=NULL,lease_expires_at=NULL,finished_at=%s,
                       version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s
                         AND version=%s AND status='running' RETURNING pipeline_run_id""",
                    (
                        occurred_at,
                        occurred_at,
                        *scope.key,
                        pipeline_run_id,
                        expected_version,
                    ),
                ).fetchone()
                if updated is None:
                    raise AipMemoryPipelineConflict("pipeline run changed concurrently")
                event = self._run_event(
                    scope,
                    pipeline_run_id=pipeline_run_id,
                    sequence=self._next_run_event_sequence(conn, scope, pipeline_run_id),
                    event_type="lease_expired",
                    from_status=KnowledgePipelineRunStatus.RUNNING,
                    to_status=KnowledgePipelineRunStatus.UNKNOWN,
                    run_version=expected_version + 1,
                    reason_code="lease_expired",
                    lease_owner=row["lease_owner"],
                    actor="system:lease-monitor",
                    occurred_at=occurred_at,
                )
                self._insert_run_event(conn, scope, event)
                self._insert_alert(
                    conn,
                    scope,
                    row,
                    code="lease_expired",
                    severity=KnowledgePipelineAlertSeverity.CRITICAL,
                    occurred_at=occurred_at,
                    receipt=receipt,
                )
                conn.commit()
                return receipt
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline lease expiry persistence failed"
            ) from exc

    def get_receipt_for_run(
        self,
        scope: TenantScope,
        pipeline_run_id: str,
        *,
        required: bool = True,
    ) -> KnowledgePipelineReceipt | None:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = self._receipt_row_for_run(conn, scope, pipeline_run_id)
                if row is None:
                    if required:
                        raise AipMemoryPipelineNotFound(
                            "knowledge pipeline receipt not found"
                        )
                    return None
                return self._receipt_from_row(conn, scope, row)
        except AipMemoryPipelineStoreError:
            raise
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline receipt read failed"
            ) from exc

    def get_checkpoint(
        self, scope: TenantScope, schedule_id: str
    ) -> KnowledgePipelineCheckpointRevision | None:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                row = conn.execute(
                    """SELECT * FROM aip_memory_pipeline_checkpoint_revision
                       WHERE org_id=%s AND project_id=%s AND schedule_id=%s
                       ORDER BY revision DESC LIMIT 1""",
                    (*scope.key, schedule_id),
                ).fetchone()
                return None if row is None else self._checkpoint_from_row(scope, row)
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline checkpoint read failed"
            ) from exc

    def list_alerts(
        self, scope: TenantScope, pipeline_run_id: str
    ) -> list[KnowledgePipelineAlert]:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_memory_pipeline_alert
                       WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s
                       ORDER BY created_at,alert_id""",
                    (*scope.key, pipeline_run_id),
                ).fetchall()
                return [self._alert_from_row(scope, row) for row in rows]
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline alert read failed"
            ) from exc

    def list_run_events(
        self, scope: TenantScope, pipeline_run_id: str
    ) -> list[KnowledgePipelineRunEvent]:
        self._require_scope(scope)
        try:
            with self._connect(scope) as conn:
                rows = conn.execute(
                    """SELECT * FROM aip_memory_pipeline_run_event
                       WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s
                       ORDER BY sequence""",
                    (*scope.key, pipeline_run_id),
                ).fetchall()
                return [self._run_event_from_row(scope, row) for row in rows]
        except Exception as exc:
            raise AipMemoryPipelinePersistenceError(
                "knowledge pipeline run event read failed"
            ) from exc

    @staticmethod
    def _require_scope(scope: TenantScope) -> None:
        if not scope.org_id.strip() or not scope.project_id.strip():
            raise ValueError("tenant scope is required")

    @classmethod
    def _validate_command(
        cls, scope: TenantScope, stable_identifier: str, actor: str
    ) -> None:
        cls._require_scope(scope)
        if not stable_identifier.strip() or not actor.strip():
            raise ValueError("stable identifier and actor are required")

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit < 1 or limit > 200:
            raise ValueError("list limit must be between 1 and 200")

    def _connect(self, scope: TenantScope):
        return self._connect_factory(scope)

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    @classmethod
    def _hash(cls, value: Any) -> str:
        return hashlib.sha256(cls._json(value).encode()).hexdigest()

    @classmethod
    def _command_hash(cls, value: Any, actor: str) -> str:
        return cls._hash(
            {
                "actor": actor.strip(),
                "request": value.model_dump(mode="json", by_alias=True),
            }
        )

    @staticmethod
    def _idempotency_lock(
        conn: Any, scope: TenantScope, resource: str, key: str
    ) -> None:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"aip-memory-pipeline:{scope.org_id}:{scope.project_id}:{resource}:{key}",),
        )

    @staticmethod
    def _schedule_row(
        conn: Any, scope: TenantScope, schedule_id: str, *, for_update: bool = False
    ):
        suffix = " FOR UPDATE" if for_update else ""
        return conn.execute(
            """SELECT * FROM aip_memory_pipeline_schedule
               WHERE org_id=%s AND project_id=%s AND schedule_id=%s""" + suffix,
            (*scope.key, schedule_id),
        ).fetchone()

    @staticmethod
    def _schedule_row_by_idempotency(
        conn: Any, scope: TenantScope, idempotency_key: str
    ):
        return conn.execute(
            """SELECT * FROM aip_memory_pipeline_schedule
               WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
            (*scope.key, idempotency_key),
        ).fetchone()

    @staticmethod
    def _run_row(
        conn: Any,
        scope: TenantScope,
        pipeline_run_id: str,
        *,
        for_update: bool = False,
    ):
        suffix = " FOR UPDATE" if for_update else ""
        return conn.execute(
            """SELECT * FROM aip_memory_pipeline_run
               WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s""" + suffix,
            (*scope.key, pipeline_run_id),
        ).fetchone()

    @staticmethod
    def _run_row_by_idempotency(
        conn: Any, scope: TenantScope, idempotency_key: str
    ):
        return conn.execute(
            """SELECT * FROM aip_memory_pipeline_run
               WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
            (*scope.key, idempotency_key),
        ).fetchone()

    @staticmethod
    def _receipt_row_for_run(
        conn: Any, scope: TenantScope, pipeline_run_id: str
    ):
        return conn.execute(
            """SELECT * FROM aip_memory_pipeline_receipt
               WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s""",
            (*scope.key, pipeline_run_id),
        ).fetchone()

    @staticmethod
    def _require_task_run(
        conn: Any, scope: TenantScope, task_id: str, run_id: str
    ) -> None:
        row = conn.execute(
            """SELECT task_id FROM aip_task_run
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, run_id),
        ).fetchone()
        if row is None or row["task_id"] != task_id:
            raise AipMemoryPipelineNotFound("AIP task/run binding not found in scope")

    @staticmethod
    def _validate_schedule_trigger(row: Any, trigger: KnowledgePipelineTrigger) -> None:
        status = KnowledgePipelineScheduleStatus(row["status"])
        if status is KnowledgePipelineScheduleStatus.DISABLED:
            raise AipMemoryPipelineTransitionBlocked("disabled schedule cannot start runs")
        if status is KnowledgePipelineScheduleStatus.PAUSED:
            if trigger is not KnowledgePipelineTrigger.MANUAL:
                raise AipMemoryPipelineTransitionBlocked(
                    "paused schedule only permits an authorized manual run"
                )
            return
        if trigger.value != row["trigger"]:
            raise AipMemoryPipelineTransitionBlocked(
                "active schedule only accepts its declared trigger"
            )

    @staticmethod
    def _validate_candidate_refs(
        conn: Any, scope: TenantScope, run_row: Any, refs: list[ResourceRef]
    ) -> None:
        for ref in refs:
            row = conn.execute(
                """SELECT task_id,run_id,version FROM aip_memory_candidate
                   WHERE org_id=%s AND project_id=%s AND candidate_id=%s""",
                (*scope.key, ref.resource_id),
            ).fetchone()
            if row is None:
                raise AipMemoryPipelineConflict("pipeline candidate is missing")
            if (
                row["task_id"] != run_row["task_id"]
                or row["run_id"] != run_row["run_id"]
                or str(row["version"]) != ref.revision
            ):
                raise AipMemoryPipelineConflict(
                    "pipeline candidate task/run/revision drifted"
                )

    @classmethod
    def _completion_matches(
        cls,
        conn: Any,
        scope: TenantScope,
        receipt: KnowledgePipelineReceipt,
        request: CompleteKnowledgePipelineRunRequest,
    ) -> bool:
        checkpoint_row = conn.execute(
            """SELECT checkpoint_ref FROM aip_memory_pipeline_checkpoint_revision
               WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s""",
            (*scope.key, receipt.pipeline_run_id),
        ).fetchone()
        checkpoint_matches = (
            checkpoint_row is None
            if request.checkpoint is None
            else checkpoint_row is not None
            and ArtifactRef.model_validate(checkpoint_row["checkpoint_ref"])
            == request.checkpoint
        )
        return (
            receipt.status is request.status
            and receipt.input_hash == request.input_hash
            and receipt.output_hash == request.output_hash
            and receipt.candidate_refs == request.candidate_refs
            and receipt.produced_count == request.produced_count
            and receipt.failed_count == request.failed_count
            and receipt.error_codes == request.error_codes
            and checkpoint_matches
        )

    def _build_receipt(
        self,
        scope: TenantScope,
        run_row: Any,
        request: CompleteKnowledgePipelineRunRequest,
        *,
        checkpoint_before: int,
        checkpoint_after: int,
        occurred_at: datetime,
    ) -> KnowledgePipelineReceipt:
        stable = {
            "pipelineRunId": run_row["pipeline_run_id"],
            "status": request.status.value,
            "inputHash": request.input_hash,
            "outputHash": request.output_hash,
            "candidateRefs": [
                item.model_dump(mode="json", by_alias=True)
                for item in request.candidate_refs
            ],
            "checkpointBeforeVersion": checkpoint_before,
            "checkpointAfterVersion": checkpoint_after,
            "checkpoint": (
                request.checkpoint.model_dump(mode="json", by_alias=True)
                if request.checkpoint
                else None
            ),
            "producedCount": request.produced_count,
            "failedCount": request.failed_count,
            "errorCodes": request.error_codes,
        }
        receipt_hash = self._hash(stable)
        return KnowledgePipelineReceipt(
            tenant=self._tenant(scope),
            receipt_id=f"pipeline-receipt-{receipt_hash[:24]}",
            pipeline_run_id=run_row["pipeline_run_id"],
            status=request.status,
            input_hash=request.input_hash,
            output_hash=request.output_hash,
            candidate_refs=request.candidate_refs,
            checkpoint_before_version=checkpoint_before,
            checkpoint_after_version=checkpoint_after,
            produced_count=request.produced_count,
            failed_count=request.failed_count,
            error_codes=request.error_codes,
            receipt_hash=receipt_hash,
            created_at=occurred_at,
        )

    def _insert_receipt(
        self, conn: Any, scope: TenantScope, receipt: KnowledgePipelineReceipt
    ) -> None:
        conn.execute(
            """INSERT INTO aip_memory_pipeline_receipt (
               org_id,project_id,receipt_id,pipeline_run_id,status,input_hash,
               output_hash,checkpoint_before_version,checkpoint_after_version,
               produced_count,failed_count,error_codes,receipt_hash,created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (
                *scope.key,
                receipt.receipt_id,
                receipt.pipeline_run_id,
                receipt.status.value,
                receipt.input_hash,
                receipt.output_hash,
                receipt.checkpoint_before_version,
                receipt.checkpoint_after_version,
                receipt.produced_count,
                receipt.failed_count,
                self._json(receipt.error_codes),
                receipt.receipt_hash,
                receipt.created_at,
            ),
        )

    def _insert_alert(
        self,
        conn: Any,
        scope: TenantScope,
        run_row: Any,
        *,
        code: str,
        severity: KnowledgePipelineAlertSeverity,
        occurred_at: datetime,
        receipt: KnowledgePipelineReceipt | None = None,
    ) -> KnowledgePipelineAlert:
        evidence = ResourceRef(
            resource_type=(
                "aip.memory_pipeline_receipt"
                if receipt is not None
                else "aip.memory_pipeline_run"
            ),
            resource_id=(
                receipt.receipt_id if receipt is not None else run_row["pipeline_run_id"]
            ),
            revision=str(int(run_row["version"])),
            authority="postgresql",
        )
        stable = {
            "pipelineRunId": run_row["pipeline_run_id"],
            "code": code,
            "severity": severity.value,
            "evidenceRef": evidence.model_dump(mode="json", by_alias=True),
        }
        alert_hash = self._hash(stable)
        alert = KnowledgePipelineAlert(
            tenant=self._tenant(scope),
            alert_id=f"pipeline-alert-{alert_hash[:24]}",
            pipeline_run_id=run_row["pipeline_run_id"],
            code=code,
            severity=severity,
            evidence_ref=evidence,
            alert_hash=alert_hash,
            created_at=occurred_at,
        )
        conn.execute(
            """INSERT INTO aip_memory_pipeline_alert (
               org_id,project_id,alert_id,pipeline_run_id,code,severity,
               evidence_ref,alert_hash,created_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
               ON CONFLICT (org_id,project_id,alert_id) DO NOTHING""",
            (
                *scope.key,
                alert.alert_id,
                alert.pipeline_run_id,
                alert.code,
                alert.severity.value,
                self._json(alert.evidence_ref),
                alert.alert_hash,
                alert.created_at,
            ),
        )
        return alert

    @staticmethod
    def _next_schedule_event_sequence(
        conn: Any, scope: TenantScope, schedule_id: str
    ) -> int:
        row = conn.execute(
            """SELECT COALESCE(MAX(sequence),0)+1 AS sequence
               FROM aip_memory_pipeline_schedule_event
               WHERE org_id=%s AND project_id=%s AND schedule_id=%s""",
            (*scope.key, schedule_id),
        ).fetchone()
        return int(row["sequence"])

    def _schedule_event(
        self,
        scope: TenantScope,
        *,
        schedule_id: str,
        sequence: int,
        event_type: str,
        from_status: KnowledgePipelineScheduleStatus | None,
        to_status: KnowledgePipelineScheduleStatus,
        schedule_version: int,
        reason_code: str,
        dependency_review: ResourceRef | None,
        actor: str,
        occurred_at: datetime,
    ) -> KnowledgePipelineScheduleEvent:
        stable = {
            "scheduleId": schedule_id,
            "sequence": sequence,
            "eventType": event_type,
            "fromStatus": from_status.value if from_status else None,
            "toStatus": to_status.value,
            "scheduleVersion": schedule_version,
            "reasonCode": reason_code,
            "dependencyReview": (
                dependency_review.model_dump(mode="json", by_alias=True)
                if dependency_review
                else None
            ),
            "actor": actor.strip(),
            "occurredAt": occurred_at.isoformat(),
        }
        event_hash = self._hash(stable)
        return KnowledgePipelineScheduleEvent(
            tenant=self._tenant(scope),
            event_id=f"pipeline-schedule-event-{event_hash[:24]}",
            schedule_id=schedule_id,
            sequence=sequence,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            schedule_version=schedule_version,
            reason_code=reason_code,
            dependency_review=dependency_review,
            event_hash=event_hash,
            actor=actor.strip(),
            occurred_at=occurred_at,
        )

    def _insert_schedule_event(
        self,
        conn: Any,
        scope: TenantScope,
        event: KnowledgePipelineScheduleEvent,
    ) -> None:
        conn.execute(
            """INSERT INTO aip_memory_pipeline_schedule_event (
               org_id,project_id,event_id,schedule_id,sequence,event_type,
               from_status,to_status,schedule_version,reason_code,
               dependency_review_ref,event_hash,actor,occurred_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
            (
                *scope.key,
                event.event_id,
                event.schedule_id,
                event.sequence,
                event.event_type,
                event.from_status.value if event.from_status else None,
                event.to_status.value,
                event.schedule_version,
                event.reason_code,
                self._json(event.dependency_review),
                event.event_hash,
                event.actor,
                event.occurred_at,
            ),
        )

    @staticmethod
    def _next_run_event_sequence(
        conn: Any, scope: TenantScope, pipeline_run_id: str
    ) -> int:
        row = conn.execute(
            """SELECT COALESCE(MAX(sequence),0)+1 AS sequence
               FROM aip_memory_pipeline_run_event
               WHERE org_id=%s AND project_id=%s AND pipeline_run_id=%s""",
            (*scope.key, pipeline_run_id),
        ).fetchone()
        return int(row["sequence"])

    def _run_event(
        self,
        scope: TenantScope,
        *,
        pipeline_run_id: str,
        sequence: int,
        event_type: str,
        from_status: KnowledgePipelineRunStatus | None,
        to_status: KnowledgePipelineRunStatus,
        run_version: int,
        reason_code: str,
        lease_owner: str | None,
        actor: str,
        occurred_at: datetime,
    ) -> KnowledgePipelineRunEvent:
        stable = {
            "pipelineRunId": pipeline_run_id,
            "sequence": sequence,
            "eventType": event_type,
            "fromStatus": from_status.value if from_status else None,
            "toStatus": to_status.value,
            "runVersion": run_version,
            "reasonCode": reason_code,
            "leaseOwner": lease_owner,
            "actor": actor.strip(),
            "occurredAt": occurred_at.isoformat(),
        }
        event_hash = self._hash(stable)
        return KnowledgePipelineRunEvent(
            tenant=self._tenant(scope),
            event_id=f"pipeline-run-event-{event_hash[:24]}",
            pipeline_run_id=pipeline_run_id,
            sequence=sequence,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            run_version=run_version,
            reason_code=reason_code,
            lease_owner=lease_owner,
            event_hash=event_hash,
            actor=actor.strip(),
            occurred_at=occurred_at,
        )

    def _insert_run_event(
        self, conn: Any, scope: TenantScope, event: KnowledgePipelineRunEvent
    ) -> None:
        conn.execute(
            """INSERT INTO aip_memory_pipeline_run_event (
               org_id,project_id,event_id,pipeline_run_id,sequence,event_type,
               from_status,to_status,run_version,reason_code,lease_owner,
               event_hash,actor,occurred_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                event.event_id,
                event.pipeline_run_id,
                event.sequence,
                event.event_type,
                event.from_status.value if event.from_status else None,
                event.to_status.value,
                event.run_version,
                event.reason_code,
                event.lease_owner,
                event.event_hash,
                event.actor,
                event.occurred_at,
            ),
        )

    def _schedule_from_row(
        self, scope: TenantScope, row: Any
    ) -> KnowledgePipelineSchedule:
        return KnowledgePipelineSchedule(
            tenant=self._tenant(scope),
            schedule_id=row["schedule_id"],
            pipeline_kind=row["pipeline_kind"],
            trigger=row["trigger"],
            config=ArtifactRef.model_validate(row["config_ref"]),
            status=row["status"],
            schedule_spec=row["schedule_spec"],
            checkpoint_version=row["checkpoint_version"],
            version=row["version"],
            next_run_at=row["next_run_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _run_from_row(self, scope: TenantScope, row: Any) -> KnowledgePipelineRun:
        return KnowledgePipelineRun(
            tenant=self._tenant(scope),
            pipeline_run_id=row["pipeline_run_id"],
            schedule_id=row["schedule_id"],
            task_id=row["task_id"],
            run_id=row["run_id"],
            trigger=row["trigger"],
            status=row["status"],
            attempt=row["attempt"],
            retry_of_run_id=row["retry_of_run_id"],
            expected_checkpoint_version=row["expected_checkpoint_version"],
            idempotency_key=row["idempotency_key"],
            request_hash=row["request_hash"],
            version=row["version"],
            scheduled_for=row["scheduled_for"],
            lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _receipt_from_row(
        self, conn: Any, scope: TenantScope, row: Any
    ) -> KnowledgePipelineReceipt:
        candidates = conn.execute(
            """SELECT candidate_id,candidate_revision
               FROM aip_memory_pipeline_receipt_candidate
               WHERE org_id=%s AND project_id=%s AND receipt_id=%s
               ORDER BY sequence""",
            (*scope.key, row["receipt_id"]),
        ).fetchall()
        return KnowledgePipelineReceipt(
            tenant=self._tenant(scope),
            receipt_id=row["receipt_id"],
            pipeline_run_id=row["pipeline_run_id"],
            status=row["status"],
            input_hash=row["input_hash"],
            output_hash=row["output_hash"],
            candidate_refs=[
                ResourceRef(
                    resource_type="aip.memory_candidate",
                    resource_id=item["candidate_id"],
                    revision=str(item["candidate_revision"]),
                    authority="postgresql",
                )
                for item in candidates
            ],
            checkpoint_before_version=row["checkpoint_before_version"],
            checkpoint_after_version=row["checkpoint_after_version"],
            produced_count=row["produced_count"],
            failed_count=row["failed_count"],
            error_codes=row["error_codes"],
            receipt_hash=row["receipt_hash"],
            created_at=row["created_at"],
        )

    def _schedule_event_from_row(
        self, scope: TenantScope, row: Any
    ) -> KnowledgePipelineScheduleEvent:
        return KnowledgePipelineScheduleEvent(
            tenant=self._tenant(scope),
            event_id=row["event_id"],
            schedule_id=row["schedule_id"],
            sequence=row["sequence"],
            event_type=row["event_type"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            schedule_version=row["schedule_version"],
            reason_code=row["reason_code"],
            dependency_review=row["dependency_review_ref"],
            event_hash=row["event_hash"],
            actor=row["actor"],
            occurred_at=row["occurred_at"],
        )

    def _checkpoint_from_row(
        self, scope: TenantScope, row: Any
    ) -> KnowledgePipelineCheckpointRevision:
        return KnowledgePipelineCheckpointRevision(
            tenant=self._tenant(scope),
            schedule_id=row["schedule_id"],
            revision=row["revision"],
            pipeline_run_id=row["pipeline_run_id"],
            receipt_id=row["receipt_id"],
            checkpoint=ArtifactRef.model_validate(row["checkpoint_ref"]),
            checkpoint_hash=row["checkpoint_hash"],
            created_at=row["created_at"],
        )

    def _run_event_from_row(
        self, scope: TenantScope, row: Any
    ) -> KnowledgePipelineRunEvent:
        return KnowledgePipelineRunEvent(
            tenant=self._tenant(scope),
            event_id=row["event_id"],
            pipeline_run_id=row["pipeline_run_id"],
            sequence=row["sequence"],
            event_type=row["event_type"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            run_version=row["run_version"],
            reason_code=row["reason_code"],
            lease_owner=row["lease_owner"],
            event_hash=row["event_hash"],
            actor=row["actor"],
            occurred_at=row["occurred_at"],
        )

    def _alert_from_row(
        self, scope: TenantScope, row: Any
    ) -> KnowledgePipelineAlert:
        return KnowledgePipelineAlert(
            tenant=self._tenant(scope),
            alert_id=row["alert_id"],
            pipeline_run_id=row["pipeline_run_id"],
            code=row["code"],
            severity=row["severity"],
            evidence_ref=row["evidence_ref"],
            alert_hash=row["alert_hash"],
            created_at=row["created_at"],
        )


__all__ = [
    "AipMemoryPipelineConflict",
    "AipMemoryPipelineNotFound",
    "AipMemoryPipelinePersistenceError",
    "AipMemoryPipelineStore",
    "AipMemoryPipelineStoreError",
    "AipMemoryPipelineTransitionBlocked",
]
