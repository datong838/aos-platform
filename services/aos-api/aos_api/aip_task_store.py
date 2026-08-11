"""PostgreSQL authority for AIP Task, PlanRevision and TaskRun."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import Any

from aos_api.aip_contracts import ActorRef, TaskRunStatus
from aos_api.aip_task_models import (
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
    PlanRevisionSnapshot,
    RunControlResult,
    StepLease,
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

    def list_runs(
        self,
        scope: TenantScope,
        *,
        logic_graph_id: str | None = None,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[TaskRunSnapshot]:
        clauses = ["org_id=%s", "project_id=%s"]
        params: list[Any] = [scope.org_id, scope.project_id]
        if logic_graph_id is not None:
            clauses.append("logic_graph_id=%s")
            params.append(logic_graph_id)
        if task_id is not None:
            clauses.append("task_id=%s")
            params.append(task_id)
        params.append(limit)
        with self._connect(scope) as conn:
            rows = conn.execute(
                f"""SELECT * FROM aip_task_run
                    WHERE {' AND '.join(clauses)}
                    ORDER BY updated_at DESC, run_id DESC LIMIT %s""",
                tuple(params),
            ).fetchall()
        return [self._run(row) for row in rows]

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

    def start_run(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_run_version: int,
        expected_task_version: int,
        actor: str,
        idempotency_key: str,
        reason: str = "",
    ) -> RunControlResult:
        with self._connect(scope) as conn:
            run, task = self._locked_run_and_task(conn, scope, run_id)
            request = self._control_request(
                "start", expected_run_version, expected_task_version, reason
            )
            replay = self._control_replay(
                conn, scope, run_id, str(task["task_id"]), "start", idempotency_key, request
            )
            if replay is not None:
                return replay
            self._expect_run_version(run, expected_run_version)
            self._expect_version(task, expected_task_version)
            if run["status"] != "queued" or TaskStatus(task["status"]) is not TaskStatus.APPROVED:
                raise AipTaskTransitionBlocked("only an approved queued run can start")
            task_status = transition_task_status(TaskStatus.APPROVED, TaskStatus.EXECUTING)
            conn.execute(
                """UPDATE aip_task_run SET status='running',started_at=NOW(),version=version+1,
                     updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s AND version=%s""",
                (scope.org_id, scope.project_id, run_id, expected_run_version),
            )
            conn.execute(
                """UPDATE aip_task SET status=%s,version=version+1,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s""",
                (
                    task_status.value,
                    scope.org_id,
                    scope.project_id,
                    task["task_id"],
                    expected_task_version,
                ),
            )
            self._record_control_receipt(
                conn, scope, run_id, actor, "start", idempotency_key, request
            )
            result = self._control_result(conn, scope, run_id, str(task["task_id"]))
            conn.commit()
            return result

    def pause_run(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_run_version: int,
        expected_task_version: int,
        actor: str,
        idempotency_key: str,
        reason: str = "",
    ) -> RunControlResult:
        return self._change_running_task(
            scope,
            run_id,
            expected_run_version=expected_run_version,
            expected_task_version=expected_task_version,
            expected_task_status=TaskStatus.EXECUTING,
            target_task_status=TaskStatus.PAUSED,
            operation="pause",
            actor=actor,
            idempotency_key=idempotency_key,
            reason=reason,
        )

    def resume_run(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_run_version: int,
        expected_task_version: int,
        actor: str,
        idempotency_key: str,
        reason: str = "",
    ) -> RunControlResult:
        return self._change_running_task(
            scope,
            run_id,
            expected_run_version=expected_run_version,
            expected_task_version=expected_task_version,
            expected_task_status=TaskStatus.PAUSED,
            target_task_status=TaskStatus.EXECUTING,
            operation="resume",
            actor=actor,
            idempotency_key=idempotency_key,
            reason=reason,
        )

    def cancel_run(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_run_version: int,
        expected_task_version: int,
        actor: str,
        idempotency_key: str,
        reason: str = "",
    ) -> RunControlResult:
        with self._connect(scope) as conn:
            run, task = self._locked_run_and_task(conn, scope, run_id)
            request = self._control_request(
                "cancel", expected_run_version, expected_task_version, reason
            )
            replay = self._control_replay(
                conn, scope, run_id, str(task["task_id"]), "cancel", idempotency_key, request
            )
            if replay is not None:
                return replay
            self._expect_run_version(run, expected_run_version)
            self._expect_version(task, expected_task_version)
            current = TaskStatus(task["status"])
            if run["status"] not in {"queued", "running"}:
                raise AipTaskTransitionBlocked("terminal run cannot be cancelled")
            try:
                if current is TaskStatus.PAUSED:
                    current = transition_task_status(current, TaskStatus.EXECUTING)
                target = transition_task_status(current, TaskStatus.CANCELLED)
            except ContractViolation as exc:
                raise AipTaskTransitionBlocked(exc.message) from exc
            conn.execute(
                """UPDATE aip_task_run SET status='cancelled',finished_at=NOW(),version=version+1,
                     updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s AND version=%s""",
                (scope.org_id, scope.project_id, run_id, expected_run_version),
            )
            conn.execute(
                """UPDATE aip_task SET status=%s,version=version+1,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s""",
                (target.value, scope.org_id, scope.project_id, task["task_id"], expected_task_version),
            )
            self._record_control_receipt(
                conn, scope, run_id, actor, "cancel", idempotency_key, request
            )
            result = self._control_result(conn, scope, run_id, str(task["task_id"]))
            conn.commit()
            return result

    def rollback_run(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_run_version: int,
        expected_task_version: int,
        actor: str,
        idempotency_key: str,
        reason: str = "",
    ) -> RunControlResult:
        with self._connect(scope) as conn:
            run, task = self._locked_run_and_task(conn, scope, run_id)
            request = self._control_request(
                "rollback", expected_run_version, expected_task_version, reason
            )
            replay = self._control_replay(
                conn, scope, run_id, str(task["task_id"]), "rollback", idempotency_key, request
            )
            if replay is not None:
                return replay
            self._expect_run_version(run, expected_run_version)
            self._expect_version(task, expected_task_version)
            if run["status"] != "succeeded" or TaskStatus(task["status"]) is not TaskStatus.COMPLETED:
                raise AipTaskTransitionBlocked("only a completed run can be rolled back")
            target = transition_task_status(TaskStatus.COMPLETED, TaskStatus.ROLLED_BACK)
            conn.execute(
                """UPDATE aip_task SET status=%s,version=version+1,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s""",
                (target.value, scope.org_id, scope.project_id, task["task_id"], expected_task_version),
            )
            conn.execute(
                "UPDATE aip_task_run SET version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s AND version=%s",
                (scope.org_id, scope.project_id, run_id, expected_run_version),
            )
            self._insert_evidence(
                conn,
                scope,
                run_id,
                actor,
                "rollback",
                {"taskId": task["task_id"], "runId": run_id, "outcome": "rolled_back"},
            )
            self._record_control_receipt(
                conn, scope, run_id, actor, "rollback", idempotency_key, request
            )
            result = self._control_result(conn, scope, run_id, str(task["task_id"]))
            conn.commit()
            return result

    def claim_step(
        self,
        scope: TenantScope,
        run_id: str,
        step_key: str,
        worker_id: str,
        *,
        lease_seconds: int,
    ) -> StepLease:
        with self._connect(scope) as conn:
            run, task = self._locked_run_and_task(conn, scope, run_id)
            if run["status"] != "running" or TaskStatus(task["status"]) is not TaskStatus.EXECUTING:
                raise AipTaskTransitionBlocked("run is not claimable")
            plan = conn.execute(
                "SELECT steps FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s",
                (scope.org_id, scope.project_id, run["plan_revision_id"]),
            ).fetchone()
            if plan is None or step_key not in {str(step.get("stepKey")) for step in plan["steps"]}:
                raise AipTaskNotFound("plan step not found in scope")
            row = conn.execute(
                """SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s
                   AND step_key=%s ORDER BY attempt DESC LIMIT 1 FOR UPDATE""",
                (scope.org_id, scope.project_id, run_id, step_key),
            ).fetchone()
            now = datetime.now(timezone.utc)
            expires = now + timedelta(seconds=lease_seconds)
            if row is None:
                step_run_id = f"step-run-{uuid.uuid4().hex[:20]}"
                row = conn.execute(
                    """INSERT INTO aip_step_run (
                         org_id,project_id,step_run_id,run_id,step_key,attempt,status,
                         lease_owner,lease_expires_at,heartbeat_at,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,1,'running',%s,%s,%s,NOW(),NOW()) RETURNING *""",
                    (scope.org_id, scope.project_id, step_run_id, run_id, step_key, worker_id, expires, now),
                ).fetchone()
            else:
                lease_expires = row["lease_expires_at"]
                if row["status"] == "running" and lease_expires and lease_expires > now:
                    raise AipTaskVersionConflict("step already has an active lease")
                if row["status"] == "running" and row["action_ref"] is not None:
                    conn.execute(
                        """UPDATE aip_step_run SET status='unknown',error=%s::jsonb,updated_at=NOW()
                           WHERE org_id=%s AND project_id=%s AND step_run_id=%s""",
                        (
                            self._json({"code": "AIP_OUTCOME_UNKNOWN", "message": "expired lease after action"}),
                            scope.org_id,
                            scope.project_id,
                            row["step_run_id"],
                        ),
                    )
                    conn.execute(
                        "UPDATE aip_task_run SET status='unknown',finished_at=NOW(),version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s",
                        (scope.org_id, scope.project_id, run_id),
                    )
                    conn.execute(
                        """UPDATE aip_task SET status='paused',version=version+1,updated_at=NOW()
                           WHERE org_id=%s AND project_id=%s AND task_id=%s AND status='executing'""",
                        (scope.org_id, scope.project_id, task["task_id"]),
                    )
                    conn.commit()
                    raise AipTaskTransitionBlocked("expired action lease requires reconcile")
                if row["status"] not in {"queued", "running"}:
                    raise AipTaskTransitionBlocked("step is already terminal")
                row = conn.execute(
                    """UPDATE aip_step_run SET status='running',lease_owner=%s,lease_expires_at=%s,
                         heartbeat_at=%s,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND step_run_id=%s
                       RETURNING *""",
                    (worker_id, expires, now, scope.org_id, scope.project_id, row["step_run_id"]),
                ).fetchone()
            conn.commit()
            return StepLease(
                step_run_id=str(row["step_run_id"]),
                run_id=run_id,
                step_key=step_key,
                attempt=int(row["attempt"]),
                worker_id=worker_id,
                lease_expires_at=row["lease_expires_at"],
            )

    def heartbeat_step(
        self, scope: TenantScope, step_run_id: str, worker_id: str, *, lease_seconds: int
    ) -> StepLease:
        expires = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        with self._connect(scope) as conn:
            row = conn.execute(
                """UPDATE aip_step_run SET heartbeat_at=NOW(),lease_expires_at=%s,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND step_run_id=%s AND status='running'
                     AND lease_owner=%s AND lease_expires_at>NOW() RETURNING *""",
                (expires, scope.org_id, scope.project_id, step_run_id, worker_id),
            ).fetchone()
            if row is None:
                raise AipTaskVersionConflict("step lease is missing, expired, or owned by another worker")
            conn.commit()
            return StepLease(
                step_run_id=step_run_id,
                run_id=str(row["run_id"]),
                step_key=str(row["step_key"]),
                attempt=int(row["attempt"]),
                worker_id=worker_id,
                lease_expires_at=row["lease_expires_at"],
            )

    def record_step_phase(
        self,
        scope: TenantScope,
        step_run_id: str,
        worker_id: str,
        actor: str,
        phase: str,
        payload: dict[str, Any],
    ) -> str:
        columns = {"think": "think_ref", "act": "action_ref", "verify": "verify_ref", "observe": "observe_ref"}
        column = columns.get(phase)
        if column is None:
            raise ValueError("phase must be think, act, verify, or observe")
        with self._connect(scope) as conn:
            step = conn.execute(
                """SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND step_run_id=%s
                   AND status='running' AND lease_owner=%s AND lease_expires_at>NOW() FOR UPDATE""",
                (scope.org_id, scope.project_id, step_run_id, worker_id),
            ).fetchone()
            if step is None:
                raise AipTaskVersionConflict("step phase write requires an active owned lease")
            evidence_id = self._insert_evidence(
                conn,
                scope,
                str(step["run_id"]),
                actor,
                f"taor.{phase}",
                {"stepRunId": step_run_id, "stepKey": step["step_key"], "payload": payload},
            )
            conn.execute(
                f"UPDATE aip_step_run SET {column}=%s::jsonb,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND step_run_id=%s",
                (self._json({"evidenceId": evidence_id}), scope.org_id, scope.project_id, step_run_id),
            )
            conn.commit()
            return evidence_id

    def record_artifact(
        self,
        scope: TenantScope,
        run_id: str,
        actor: str,
        artifact_type: str,
        payload: dict[str, Any],
    ) -> str:
        """Persist an artifact reference without storing opaque provider state or credentials."""
        artifact_id = f"artifact-{uuid.uuid4().hex[:20]}"
        content_ref = payload.get("contentRef")
        schema_ref = payload.get("schemaRef")
        metadata = payload.get("metadata", {})
        source = payload.get("source", {})
        evidence_refs = payload.get("evidenceRefs", [])
        marking = payload.get("marking", [])
        content_hash = payload.get("contentHash") or _canonical_hash(
            {"contentRef": content_ref, "schemaRef": schema_ref, "metadata": metadata}
        )
        with self._connect(scope) as conn:
            exists = conn.execute(
                "SELECT 1 FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (scope.org_id, scope.project_id, run_id),
            ).fetchone()
            if exists is None:
                raise AipTaskNotFound("task run not found in scope")
            conn.execute(
                """INSERT INTO aip_artifact (
                     org_id,project_id,artifact_id,run_id,artifact_type,content_ref,schema_ref,
                     source,evidence_refs,marking,content_hash,metadata,created_by,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s,NOW())""",
                (
                    scope.org_id,
                    scope.project_id,
                    artifact_id,
                    run_id,
                    artifact_type,
                    content_ref,
                    schema_ref,
                    self._json(source),
                    self._json(evidence_refs),
                    self._json(marking),
                    content_hash,
                    self._json(metadata),
                    actor,
                ),
            )
            conn.commit()
        return artifact_id

    def complete_step(
        self, scope: TenantScope, step_run_id: str, worker_id: str, actor: str
    ) -> str:
        with self._connect(scope) as conn:
            step = conn.execute(
                """SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND step_run_id=%s
                   AND status='running' AND lease_owner=%s AND lease_expires_at>NOW() FOR UPDATE""",
                (scope.org_id, scope.project_id, step_run_id, worker_id),
            ).fetchone()
            if step is None:
                raise AipTaskVersionConflict("step completion requires an active owned lease")
            if any(step[name] is None for name in ("think_ref", "action_ref", "verify_ref", "observe_ref")):
                raise AipTaskTransitionBlocked("all four TAOR evidence phases are required")
            sequence = int(
                conn.execute(
                    "SELECT COALESCE(MAX(sequence),0)+1 AS seq FROM aip_checkpoint WHERE org_id=%s AND project_id=%s AND run_id=%s",
                    (scope.org_id, scope.project_id, step["run_id"]),
                ).fetchone()["seq"]
            )
            checkpoint_id = f"checkpoint-{uuid.uuid4().hex[:20]}"
            state = {"stepRunId": step_run_id, "stepKey": step["step_key"], "status": "succeeded"}
            conn.execute(
                """INSERT INTO aip_checkpoint (
                     org_id,project_id,checkpoint_id,run_id,sequence,schema_version,step_key,
                     state_hash,state_snapshot_ref,artifact_refs,created_by,created_at)
                   VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s::jsonb,'[]'::jsonb,%s,NOW())""",
                (
                    scope.org_id,
                    scope.project_id,
                    checkpoint_id,
                    step["run_id"],
                    sequence,
                    step["step_key"],
                    _canonical_hash(state),
                    self._json(state),
                    actor,
                ),
            )
            conn.execute(
                """UPDATE aip_step_run SET status='succeeded',lease_owner=NULL,lease_expires_at=NULL,
                     heartbeat_at=NULL,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND step_run_id=%s""",
                (scope.org_id, scope.project_id, step_run_id),
            )
            conn.execute(
                "UPDATE aip_task_run SET last_checkpoint_id=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (checkpoint_id, scope.org_id, scope.project_id, step["run_id"]),
            )
            conn.commit()
            return checkpoint_id

    def complete_run(self, scope: TenantScope, run_id: str) -> RunControlResult:
        with self._connect(scope) as conn:
            run, task = self._locked_run_and_task(conn, scope, run_id)
            if run["status"] != "running" or TaskStatus(task["status"]) is not TaskStatus.EXECUTING:
                raise AipTaskTransitionBlocked("run is not completable")
            plan = conn.execute(
                "SELECT steps FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s",
                (scope.org_id, scope.project_id, run["plan_revision_id"]),
            ).fetchone()
            required = {str(step["stepKey"]) for step in plan["steps"]}
            succeeded = {
                str(row["step_key"])
                for row in conn.execute(
                    "SELECT step_key FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s AND status='succeeded'",
                    (scope.org_id, scope.project_id, run_id),
                ).fetchall()
            }
            if required != succeeded:
                raise AipTaskTransitionBlocked("all plan steps must succeed before run completion")
            target = transition_task_status(TaskStatus.EXECUTING, TaskStatus.COMPLETED)
            conn.execute(
                "UPDATE aip_task_run SET status='succeeded',finished_at=NOW(),version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (scope.org_id, scope.project_id, run_id),
            )
            conn.execute(
                "UPDATE aip_task SET status=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND task_id=%s",
                (target.value, scope.org_id, scope.project_id, task["task_id"]),
            )
            result = self._control_result(conn, scope, run_id, str(task["task_id"]))
            conn.commit()
            return result

    def fail_step(
        self, scope: TenantScope, step_run_id: str, worker_id: str, actor: str, error: dict[str, Any]
    ) -> RunControlResult:
        with self._connect(scope) as conn:
            step = conn.execute(
                """SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND step_run_id=%s
                   AND status='running' AND lease_owner=%s AND lease_expires_at>NOW() FOR UPDATE""",
                (scope.org_id, scope.project_id, step_run_id, worker_id),
            ).fetchone()
            if step is None:
                raise AipTaskVersionConflict("step failure requires the owned lease")
            run, task = self._locked_run_and_task(conn, scope, str(step["run_id"]))
            self._insert_evidence(conn, scope, str(step["run_id"]), actor, "taor.failure", error)
            conn.execute(
                "UPDATE aip_step_run SET status='failed',error=%s::jsonb,lease_owner=NULL,lease_expires_at=NULL,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND step_run_id=%s",
                (self._json(error), scope.org_id, scope.project_id, step_run_id),
            )
            conn.execute(
                "UPDATE aip_task_run SET status='failed',finished_at=NOW(),version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (scope.org_id, scope.project_id, step["run_id"]),
            )
            target = transition_task_status(TaskStatus(task["status"]), TaskStatus.FAILED)
            conn.execute(
                "UPDATE aip_task SET status=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND task_id=%s",
                (target.value, scope.org_id, scope.project_id, task["task_id"]),
            )
            result = self._control_result(conn, scope, str(step["run_id"]), str(task["task_id"]))
            conn.commit()
            return result

    def _change_running_task(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_run_version: int,
        expected_task_version: int,
        expected_task_status: TaskStatus,
        target_task_status: TaskStatus,
        operation: str,
        actor: str,
        idempotency_key: str,
        reason: str,
    ) -> RunControlResult:
        with self._connect(scope) as conn:
            run, task = self._locked_run_and_task(conn, scope, run_id)
            request = self._control_request(
                operation, expected_run_version, expected_task_version, reason
            )
            replay = self._control_replay(
                conn,
                scope,
                run_id,
                str(task["task_id"]),
                operation,
                idempotency_key,
                request,
            )
            if replay is not None:
                return replay
            self._expect_run_version(run, expected_run_version)
            self._expect_version(task, expected_task_version)
            if run["status"] != "running" or TaskStatus(task["status"]) is not expected_task_status:
                raise AipTaskTransitionBlocked("run/task state does not allow this operation")
            target = transition_task_status(expected_task_status, target_task_status)
            conn.execute(
                "UPDATE aip_task_run SET version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s AND version=%s",
                (scope.org_id, scope.project_id, run_id, expected_run_version),
            )
            conn.execute(
                "UPDATE aip_task SET status=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s",
                (target.value, scope.org_id, scope.project_id, task["task_id"], expected_task_version),
            )
            self._record_control_receipt(
                conn, scope, run_id, actor, operation, idempotency_key, request
            )
            result = self._control_result(conn, scope, run_id, str(task["task_id"]))
            conn.commit()
            return result

    def _locked_run_and_task(self, conn: Any, scope: TenantScope, run_id: str):
        run = conn.execute(
            "SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s FOR UPDATE",
            (scope.org_id, scope.project_id, run_id),
        ).fetchone()
        if run is None:
            raise AipTaskNotFound("task run not found in scope")
        task = self._task_row(conn, scope, str(run["task_id"]), for_update=True)
        if task is None:
            raise AipTaskNotFound("task not found in scope")
        return run, task

    def _control_result(self, conn: Any, scope: TenantScope, run_id: str, task_id: str) -> RunControlResult:
        run = conn.execute(
            "SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s",
            (scope.org_id, scope.project_id, run_id),
        ).fetchone()
        task = self._task_row(conn, scope, task_id)
        return RunControlResult(task=self._task(task), run=self._run(run))

    def _insert_evidence(
        self,
        conn: Any,
        scope: TenantScope,
        run_id: str,
        actor: str,
        evidence_type: str,
        payload: dict[str, Any],
        *,
        source_ref: str | None = None,
    ) -> str:
        evidence_id = f"evidence-{uuid.uuid4().hex[:20]}"
        content_hash = _canonical_hash(payload)
        conn.execute(
            """INSERT INTO aip_evidence (
                 org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,
                 source_type,source_ref,observed_at,freshness_at,content_hash,redaction,
                 payload,created_by,created_at)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb,'aip-runtime',%s,NOW(),NOW(),%s,
                       '{}'::jsonb,%s::jsonb,%s,NOW())""",
            (
                scope.org_id,
                scope.project_id,
                evidence_id,
                run_id,
                evidence_type,
                self._json({"resourceType": "TaskRun", "resourceId": run_id, "authority": "aip-task-runtime"}),
                source_ref or evidence_type,
                content_hash,
                self._json(payload),
                actor,
            ),
        )
        return evidence_id

    @staticmethod
    def _control_request(
        operation: str,
        expected_run_version: int,
        expected_task_version: int,
        reason: str,
    ) -> dict[str, Any]:
        request = {
            "operation": operation,
            "expectedRunVersion": expected_run_version,
            "expectedTaskVersion": expected_task_version,
            "reason": reason,
        }
        return {**request, "requestHash": _canonical_hash(request)}

    def _control_replay(
        self,
        conn: Any,
        scope: TenantScope,
        run_id: str,
        task_id: str,
        operation: str,
        idempotency_key: str,
        request: dict[str, Any],
    ) -> RunControlResult | None:
        source_ref = f"run-control:{operation}:{idempotency_key}"
        receipt = conn.execute(
            """SELECT payload FROM aip_evidence
               WHERE org_id=%s AND project_id=%s AND run_id=%s
                 AND evidence_type='run.control' AND source_ref=%s
               ORDER BY created_at DESC LIMIT 1""",
            (scope.org_id, scope.project_id, run_id, source_ref),
        ).fetchone()
        if receipt is None:
            return None
        if receipt["payload"].get("requestHash") != request["requestHash"]:
            raise AipTaskIdempotencyConflict(
                "run control idempotency key was reused for a different request"
            )
        return self._control_result(conn, scope, run_id, task_id)

    def _record_control_receipt(
        self,
        conn: Any,
        scope: TenantScope,
        run_id: str,
        actor: str,
        operation: str,
        idempotency_key: str,
        request: dict[str, Any],
    ) -> str:
        return self._insert_evidence(
            conn,
            scope,
            run_id,
            actor,
            "run.control",
            request,
            source_ref=f"run-control:{operation}:{idempotency_key}",
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
    def _expect_run_version(row: Any, expected: int) -> None:
        current = int(row["version"])
        if current != expected:
            raise AipTaskVersionConflict(
                f"expected run version {expected}, current version is {current}"
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
