"""PostgreSQL authority for AIP Task, PlanRevision and TaskRun."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.aip_contracts import ActorRef, TaskRunStatus
from aos_api.aip_task_models import (
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
    PlanRevisionSnapshot,
    TaskRunSnapshot,
    TaskSnapshot,
    TaskTimeline,
)
from aos_api.db import connect as db_connect
from aos_api.public_contracts import ContractViolation, TaskStatus, transition_task_status
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipTaskStoreError(RuntimeError):
    code = "AIP_TASK_STORE_ERROR"


class AipTaskNotFound(AipTaskStoreError):
    code = "AIP_RESOURCE_NOT_FOUND"


class AipTaskVersionConflict(AipTaskStoreError):
    code = "AIP_VERSION_CONFLICT"


class AipTaskIdempotencyConflict(AipTaskStoreError):
    code = "AIP_IDEMPOTENCY_CONFLICT"


class AipTaskTransitionBlocked(AipTaskStoreError):
    code = "AIP_INVALID_TRANSITION"


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AipTaskStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create_task(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        body: CreateTaskRequest,
    ) -> TaskSnapshot:
        request_hash = _canonical_hash(body.model_dump(mode="json", by_alias=True))
        task_id = f"task-{uuid.uuid4().hex[:20]}"
        with self._connect(scope) as conn:
            row = conn.execute(
                """INSERT INTO aip_task (
                     org_id,project_id,task_id,task_type,title,description,status,priority,
                     goal,selection_ref,policy_revision,idempotency_key,request_hash,
                     version,created_by,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,'pending',%s,%s::jsonb,%s::jsonb,%s,%s,%s,1,%s,NOW(),NOW())
                   ON CONFLICT (org_id,project_id,idempotency_key) DO NOTHING
                   RETURNING *""",
                (
                    scope.org_id,
                    scope.project_id,
                    task_id,
                    body.type,
                    body.title,
                    body.description,
                    body.priority,
                    self._json(body.goal),
                    self._json(body.selection_ref.model_dump(mode="json", by_alias=True))
                    if body.selection_ref
                    else None,
                    body.policy_revision,
                    idempotency_key,
                    request_hash,
                    actor,
                ),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                    (scope.org_id, scope.project_id, idempotency_key),
                ).fetchone()
                if row is None or row["request_hash"] != request_hash:
                    raise AipTaskIdempotencyConflict(
                        "idempotency key was reused for a different Task request"
                    )
            conn.commit()
            return self._task(row)

    def list_tasks(
        self, scope: TenantScope, *, status: TaskStatus | None = None, limit: int = 100
    ) -> list[TaskSnapshot]:
        with self._connect(scope) as conn:
            params: list[Any] = [scope.org_id, scope.project_id]
            where = ""
            if status is not None:
                where = "AND status=%s"
                params.append(status.value)
            params.append(limit)
            rows = conn.execute(
                f"""SELECT * FROM aip_task
                    WHERE org_id=%s AND project_id=%s {where}
                    ORDER BY updated_at DESC,task_id DESC LIMIT %s""",
                params,
            ).fetchall()
        return [self._task(row) for row in rows]

    def get_task(self, scope: TenantScope, task_id: str) -> TaskSnapshot:
        with self._connect(scope) as conn:
            row = self._task_row(conn, scope, task_id)
        if row is None:
            raise AipTaskNotFound("task not found in scope")
        return self._task(row)

    def create_plan(
        self,
        scope: TenantScope,
        actor: str,
        task_id: str,
        idempotency_key: str,
        body: CreatePlanRevisionRequest,
    ) -> PlanRevisionSnapshot:
        payload = {
            "steps": [step.model_dump(mode="json", by_alias=True) for step in body.steps],
            "dependencies": body.dependencies,
            "risk": body.risk,
        }
        content_hash = _canonical_hash(payload)
        request_hash = _canonical_hash(
            {**payload, "expectedTaskVersion": body.expected_task_version}
        )
        with self._connect(scope) as conn:
            replay = conn.execute(
                """SELECT * FROM aip_plan_revision
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND idempotency_key=%s""",
                (scope.org_id, scope.project_id, task_id, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise AipTaskIdempotencyConflict(
                        "idempotency key was reused for a different Plan request"
                    )
                return self._plan(replay)

            task = self._task_row(conn, scope, task_id, for_update=True)
            if task is None:
                raise AipTaskNotFound("task not found in scope")
            self._expect_version(task, body.expected_task_version)
            status = TaskStatus(task["status"])
            if status not in {
                TaskStatus.PENDING,
                TaskStatus.PLANNING,
                TaskStatus.AWAITING_APPROVAL,
            }:
                raise AipTaskTransitionBlocked(
                    f"cannot create a plan while task is {status.value}"
                )
            revision = int(
                conn.execute(
                    """SELECT COALESCE(MAX(revision),0)+1 AS next_revision
                       FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND task_id=%s""",
                    (scope.org_id, scope.project_id, task_id),
                ).fetchone()["next_revision"]
            )
            plan_id = f"plan-{uuid.uuid4().hex[:20]}"
            row = conn.execute(
                """INSERT INTO aip_plan_revision (
                     org_id,project_id,plan_revision_id,task_id,revision,content_hash,steps,
                     dependencies,risk,approval_status,idempotency_key,request_hash,created_by,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,'draft',%s,%s,%s,NOW())
                   RETURNING *""",
                (
                    scope.org_id,
                    scope.project_id,
                    plan_id,
                    task_id,
                    revision,
                    content_hash,
                    self._json(payload["steps"]),
                    self._json(body.dependencies),
                    self._json(body.risk),
                    idempotency_key,
                    request_hash,
                    actor,
                ),
            ).fetchone()
            next_status = (
                transition_task_status(status, TaskStatus.PLANNING).value
                if status is TaskStatus.PENDING
                else status.value
            )
            conn.execute(
                """UPDATE aip_task SET status=%s,current_plan_revision_id=%s,
                     version=version+1,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s""",
                (
                    next_status,
                    plan_id,
                    scope.org_id,
                    scope.project_id,
                    task_id,
                    body.expected_task_version,
                ),
            )
            conn.commit()
            return self._plan(row)

    def approve_plan(
        self,
        scope: TenantScope,
        actor: str,
        task_id: str,
        revision: int,
        expected_task_version: int,
        expected_content_hash: str,
    ) -> PlanRevisionSnapshot:
        with self._connect(scope) as conn:
            task = self._task_row(conn, scope, task_id, for_update=True)
            if task is None:
                raise AipTaskNotFound("task not found in scope")
            plan = conn.execute(
                """SELECT * FROM aip_plan_revision
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND revision=%s FOR UPDATE""",
                (scope.org_id, scope.project_id, task_id, revision),
            ).fetchone()
            if plan is None:
                raise AipTaskNotFound("plan revision not found in scope")
            if (
                plan["approval_status"] == "approved"
                and plan["content_hash"] == expected_content_hash
            ):
                return self._plan(plan)
            self._expect_version(task, expected_task_version)
            if task["current_plan_revision_id"] != plan["plan_revision_id"]:
                raise AipTaskVersionConflict("only the current plan revision can be approved")
            if plan["content_hash"] != expected_content_hash:
                raise AipTaskVersionConflict("plan content hash changed before approval")
            try:
                status = TaskStatus(task["status"])
                if status is TaskStatus.PLANNING:
                    status = transition_task_status(status, TaskStatus.AWAITING_APPROVAL)
                status = transition_task_status(status, TaskStatus.APPROVED)
            except ContractViolation as exc:
                raise AipTaskTransitionBlocked(exc.message) from exc
            conn.execute(
                """UPDATE aip_plan_revision SET approval_status='approved',approved_by=%s,
                     approved_at=NOW() WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
                (actor, scope.org_id, scope.project_id, plan["plan_revision_id"]),
            )
            conn.execute(
                """UPDATE aip_plan_revision SET approval_status='superseded'
                   WHERE org_id=%s AND project_id=%s AND task_id=%s
                     AND plan_revision_id<>%s AND approval_status='draft'""",
                (scope.org_id, scope.project_id, task_id, plan["plan_revision_id"]),
            )
            conn.execute(
                """UPDATE aip_task SET status=%s,version=version+1,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s""",
                (
                    status.value,
                    scope.org_id,
                    scope.project_id,
                    task_id,
                    expected_task_version,
                ),
            )
            plan = conn.execute(
                "SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s",
                (scope.org_id, scope.project_id, plan["plan_revision_id"]),
            ).fetchone()
            conn.commit()
            return self._plan(plan)

    def create_run(
        self,
        scope: TenantScope,
        actor: str,
        task_id: str,
        idempotency_key: str,
        body: CreateTaskRunRequest,
    ) -> TaskRunSnapshot:
        request_hash = _canonical_hash(body.model_dump(mode="json", by_alias=True))
        with self._connect(scope) as conn:
            replay = conn.execute(
                """SELECT * FROM aip_task_run
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND idempotency_key=%s""",
                (scope.org_id, scope.project_id, task_id, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise AipTaskIdempotencyConflict(
                        "idempotency key was reused for a different Run request"
                    )
                return self._run(replay)
            task = self._task_row(conn, scope, task_id, for_update=True)
            if task is None:
                raise AipTaskNotFound("task not found in scope")
            self._expect_version(task, body.expected_task_version)
            if TaskStatus(task["status"]) is not TaskStatus.APPROVED:
                raise AipTaskTransitionBlocked("task must be approved before creating a run")
            if task["current_plan_revision_id"] != body.plan_revision_id:
                raise AipTaskVersionConflict("run must bind the current approved plan")
            plan = conn.execute(
                """SELECT approval_status FROM aip_plan_revision
                   WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
                (scope.org_id, scope.project_id, body.plan_revision_id),
            ).fetchone()
            if plan is None or plan["approval_status"] != "approved":
                raise AipTaskTransitionBlocked("plan revision is not approved")
            run_id = f"run-{uuid.uuid4().hex[:20]}"
            row = conn.execute(
                """INSERT INTO aip_task_run (
                     org_id,project_id,run_id,task_id,plan_revision_id,logic_graph_id,
                     logic_revision,status,idempotency_key,request_hash,version,created_by,
                     created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s,1,%s,NOW(),NOW())
                   RETURNING *""",
                (
                    scope.org_id,
                    scope.project_id,
                    run_id,
                    task_id,
                    body.plan_revision_id,
                    body.logic_graph_id,
                    body.logic_revision,
                    idempotency_key,
                    request_hash,
                    actor,
                ),
            ).fetchone()
            conn.commit()
            return self._run(row)

    def get_run(self, scope: TenantScope, run_id: str) -> TaskRunSnapshot:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (scope.org_id, scope.project_id, run_id),
            ).fetchone()
        if row is None:
            raise AipTaskNotFound("task run not found in scope")
        return self._run(row)

    def timeline(self, scope: TenantScope, run_id: str) -> TaskTimeline:
        with self._connect(scope) as conn:
            run = conn.execute(
                "SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (scope.org_id, scope.project_id, run_id),
            ).fetchone()
            if run is None:
                raise AipTaskNotFound("task run not found in scope")
            task = self._task_row(conn, scope, str(run["task_id"]))
            plan = conn.execute(
                "SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s",
                (scope.org_id, scope.project_id, run["plan_revision_id"]),
            ).fetchone()
            steps = conn.execute(
                "SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s ORDER BY created_at,step_run_id",
                (scope.org_id, scope.project_id, run_id),
            ).fetchall()
            checkpoints = conn.execute(
                "SELECT * FROM aip_checkpoint WHERE org_id=%s AND project_id=%s AND run_id=%s ORDER BY sequence",
                (scope.org_id, scope.project_id, run_id),
            ).fetchall()
            artifacts = conn.execute(
                "SELECT * FROM aip_artifact WHERE org_id=%s AND project_id=%s AND run_id=%s ORDER BY created_at,artifact_id",
                (scope.org_id, scope.project_id, run_id),
            ).fetchall()
            evidence = conn.execute(
                "SELECT * FROM aip_evidence WHERE org_id=%s AND project_id=%s AND run_id=%s ORDER BY created_at,evidence_id",
                (scope.org_id, scope.project_id, run_id),
            ).fetchall()
        return TaskTimeline(
            task=self._task(task),
            plan=self._plan(plan),
            run=self._run(run),
            steps=[dict(row) for row in steps],
            checkpoints=[dict(row) for row in checkpoints],
            artifacts=[dict(row) for row in artifacts],
            evidence=[dict(row) for row in evidence],
        )

    def _connect(self, scope: TenantScope):
        try:
            return self._connect_factory(scope)
        except TypeError:
            return self._connect_factory()

    @staticmethod
    def _task_row(conn: Any, scope: TenantScope, task_id: str, *, for_update: bool = False):
        suffix = " FOR UPDATE" if for_update else ""
        return conn.execute(
            "SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s" + suffix,
            (scope.org_id, scope.project_id, task_id),
        ).fetchone()

    @staticmethod
    def _expect_version(row: Any, expected: int) -> None:
        current = int(row["version"])
        if current != expected:
            raise AipTaskVersionConflict(
                f"expected task version {expected}, current version is {current}"
            )

    @staticmethod
    def _task(row: Any) -> TaskSnapshot:
        return TaskSnapshot(
            id=str(row["task_id"]),
            type=str(row["task_type"]),
            title=str(row["title"]),
            description=str(row["description"]),
            status=TaskStatus(row["status"]),
            priority=int(row["priority"]),
            goal=dict(row["goal"] or {}),
            selection_ref=row["selection_ref"],
            policy_revision=row["policy_revision"],
            created_by=ActorRef(actor_type="user", actor_id=str(row["created_by"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            current_plan_revision_id=row["current_plan_revision_id"],
            version=int(row["version"]),
        )

    @staticmethod
    def _plan(row: Any) -> PlanRevisionSnapshot:
        return PlanRevisionSnapshot(
            id=str(row["plan_revision_id"]),
            task_id=str(row["task_id"]),
            revision=int(row["revision"]),
            content_hash=str(row["content_hash"]),
            steps=list(row["steps"] or []),
            dependencies=list(row["dependencies"] or []),
            risk=dict(row["risk"] or {}),
            approval_status=str(row["approval_status"]),
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            created_by=ActorRef(actor_type="user", actor_id=str(row["created_by"])),
            created_at=row["created_at"],
        )

    @staticmethod
    def _run(row: Any) -> TaskRunSnapshot:
        return TaskRunSnapshot(
            id=str(row["run_id"]),
            task_id=str(row["task_id"]),
            plan_revision_id=str(row["plan_revision_id"]),
            status=TaskRunStatus(row["status"]),
            logic_graph_id=row["logic_graph_id"],
            logic_revision=row["logic_revision"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            last_checkpoint_id=row["last_checkpoint_id"],
            version=int(row["version"]),
            created_by=ActorRef(actor_type="user", actor_id=str(row["created_by"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
