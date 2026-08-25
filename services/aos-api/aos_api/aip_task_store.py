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
            risk = dict(plan["risk"] or {})
            production_contract = risk.get("productionContract")
            if (
                isinstance(production_contract, dict)
                and production_contract.get("productionStartGateRequired") is True
            ):
                # W2-C can compile a production-shaped draft Plan, but W2-D owns
                # the exact Impact/start gate authority.  Until that authority is
                # implemented and verified here, fail closed rather than trusting
                # a client-provided risk field as proof of approval.
                raise AipTaskTransitionBlocked(
                    "production start gate authority is required before plan approval"
                )
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

    def create_run_from_production_start_gate(
        self,
        conn: Any,
        scope: TenantScope,
        *,
        actor: str,
        decision_id: str,
        task_id: str,
        expected_task_version: int,
        plan_revision_id: str,
        plan_content_hash: str,
        logic_graph_id: str,
        logic_revision: int,
    ) -> TaskRunSnapshot:
        """Approve a W2-C plan and create its sole TaskRun in the caller transaction."""
        task = self._task_row(conn, scope, task_id, for_update=True)
        if task is None:
            raise AipTaskNotFound("task not found in scope")
        self._expect_version(task, expected_task_version)
        if task["current_plan_revision_id"] != plan_revision_id:
            raise AipTaskVersionConflict("start gate must bind the current plan")
        plan = conn.execute(
            """SELECT * FROM aip_plan_revision
               WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s FOR UPDATE""",
            (*scope.key, plan_revision_id),
        ).fetchone()
        if plan is None or plan["task_id"] != task_id:
            raise AipTaskNotFound("plan revision not found for task")
        if plan["content_hash"] != plan_content_hash:
            raise AipTaskVersionConflict("plan content hash changed before start")
        if plan["approval_status"] != "draft":
            raise AipTaskTransitionBlocked("production plan is not awaiting start approval")
        if TaskStatus(task["status"]) not in {
            TaskStatus.PLANNING,
            TaskStatus.AWAITING_APPROVAL,
        }:
            raise AipTaskTransitionBlocked("task is not awaiting production start")
        production_contract = dict(plan["risk"] or {}).get("productionContract")
        if not isinstance(production_contract, dict) or not (
            production_contract.get("compilerVersion") in {"w2c.v1", "w7c.v1"}
            and production_contract.get("productionStartGateRequired") is True
            and production_contract.get("productionStartGateRef") is None
        ):
            raise AipTaskTransitionBlocked("plan is not a sealed W2-C production draft")
        if production_contract.get("compilerVersion") == "w7c.v1":
            input_hash = production_contract.get("inputHash")
            governed = production_contract.get("governedDependencies")
            expected_input_hash = _canonical_hash(
                {
                    "compilerVersion": production_contract.get("compilerVersion"),
                    "templateRef": production_contract.get("stageTemplateRef"),
                    "responsibilityPlanRef": production_contract.get(
                        "responsibilityPlanRef"
                    ),
                    "productionContextRef": production_contract.get(
                        "productionContextRef"
                    ),
                    "governedDependencies": governed,
                    "normalizedStageIds": production_contract.get(
                        "normalizedStageIds"
                    ),
                }
            )
            expected = _canonical_hash(
                {
                    "inputHash": input_hash,
                    "steps": plan["steps"],
                    "dependencies": plan["dependencies"],
                }
            )
            if not (
                isinstance(input_hash, str)
                and input_hash == expected_input_hash
                and production_contract.get("compilationHash") == expected
                and isinstance(governed, list)
                and len(governed) >= 7
            ):
                raise AipTaskTransitionBlocked(
                    "W7 production plan compilation envelope drifted"
                )
        run_key = f"w2d-start:{decision_id}"
        request_hash = _canonical_hash(
            {
                "decisionId": decision_id,
                "taskId": task_id,
                "planRevisionId": plan_revision_id,
                "planContentHash": plan_content_hash,
                "logicGraphId": logic_graph_id,
                "logicRevision": logic_revision,
            }
        )
        run_id = f"run-{uuid.uuid4().hex[:20]}"
        row = conn.execute(
            """INSERT INTO aip_task_run (
                 org_id,project_id,run_id,task_id,plan_revision_id,logic_graph_id,
                 logic_revision,status,idempotency_key,request_hash,version,created_by,
                 created_at,updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s,1,%s,NOW(),NOW())
               RETURNING *""",
            (
                *scope.key,
                run_id,
                task_id,
                plan_revision_id,
                logic_graph_id,
                logic_revision,
                run_key,
                request_hash,
                actor,
            ),
        ).fetchone()
        conn.execute(
            """UPDATE aip_plan_revision SET approval_status='approved',approved_by=%s,
                 approved_at=NOW() WHERE org_id=%s AND project_id=%s
                 AND plan_revision_id=%s AND approval_status='draft'""",
            (actor, *scope.key, plan_revision_id),
        )
        conn.execute(
            """UPDATE aip_task SET status='approved',version=version+1,updated_at=NOW()
               WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s""",
            (*scope.key, task_id, expected_task_version),
        )
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
            plan = conn.execute(
                """SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s
                   AND plan_revision_id=%s""",
                (*scope.key, run["plan_revision_id"]),
            ).fetchone()
            dependency_snapshot_hash = self._runtime_dependency_snapshot_hash(run, plan)
            task_status = transition_task_status(TaskStatus.APPROVED, TaskStatus.EXECUTING)
            conn.execute(
                """UPDATE aip_task_run SET status='running',started_at=NOW(),
                     dependency_snapshot_hash=%s,version=version+1,
                     updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s AND version=%s""",
                (dependency_snapshot_hash, scope.org_id, scope.project_id, run_id, expected_run_version),
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
        with self._connect(scope) as conn:
            run, task = self._locked_run_and_task(conn, scope, run_id)
            request = self._control_request("pause", expected_run_version, expected_task_version, reason)
            replay = self._control_replay(conn, scope, run_id, str(task["task_id"]), "pause", idempotency_key, request)
            if replay is not None:
                return replay
            self._expect_run_version(run, expected_run_version)
            self._expect_version(task, expected_task_version)
            if run["status"] != "running" or TaskStatus(task["status"]) is not TaskStatus.EXECUTING:
                raise AipTaskTransitionBlocked("run/task state does not allow pause")
            active = conn.execute(
                """SELECT 1 FROM aip_step_run WHERE org_id=%s AND project_id=%s
                   AND run_id=%s AND status='running' AND lease_expires_at>NOW() LIMIT 1""",
                (*scope.key, run_id),
            ).fetchone()
            run_status = "pausing" if active is not None else "paused"
            target = transition_task_status(TaskStatus.EXECUTING, TaskStatus.PAUSED)
            conn.execute(
                """UPDATE aip_task_run SET status=%s,pause_requested_at=NOW(),pause_reason=%s,
                   version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s
                   AND run_id=%s AND version=%s""",
                (run_status, reason, *scope.key, run_id, expected_run_version),
            )
            conn.execute(
                """UPDATE aip_task SET status=%s,version=version+1,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s""",
                (target.value, *scope.key, task["task_id"], expected_task_version),
            )
            self._record_control_receipt(conn, scope, run_id, actor, "pause", idempotency_key, request)
            result = self._control_result(conn, scope, run_id, str(task["task_id"]))
            conn.commit()
            return result

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
        with self._connect(scope) as conn:
            run, task = self._locked_run_and_task(conn, scope, run_id)
            request = self._control_request("resume", expected_run_version, expected_task_version, reason)
            replay = self._control_replay(conn, scope, run_id, str(task["task_id"]), "resume", idempotency_key, request)
            if replay is not None:
                return replay
            prior_decision = conn.execute(
                """SELECT decision,request_hash FROM aip_run_resume_decision_revision
                   WHERE org_id=%s AND project_id=%s AND run_id=%s AND idempotency_key=%s""",
                (*scope.key, run_id, idempotency_key),
            ).fetchone()
            if prior_decision is not None:
                if prior_decision["request_hash"] != _canonical_hash(request):
                    raise AipTaskIdempotencyConflict(
                        "idempotency key was reused for a different resume request"
                    )
                if prior_decision["decision"] == "invalidated":
                    raise AipTaskVersionConflict("resume dependency snapshot drifted")
                raise AipTaskTransitionBlocked(
                    "resume decision exists without its canonical control receipt"
                )
            self._expect_run_version(run, expected_run_version)
            self._expect_version(task, expected_task_version)
            if run["status"] != "paused" or TaskStatus(task["status"]) is not TaskStatus.PAUSED:
                raise AipTaskTransitionBlocked("only a quiesced paused run can resume")
            plan = conn.execute(
                """SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s
                   AND plan_revision_id=%s""",
                (*scope.key, run["plan_revision_id"]),
            ).fetchone()
            observed_dependency_hash = self._runtime_dependency_snapshot_hash(run, plan)
            checkpoint = conn.execute(
                """SELECT * FROM aip_checkpoint WHERE org_id=%s AND project_id=%s AND run_id=%s
                   ORDER BY sequence DESC LIMIT 1""",
                (*scope.key, run_id),
            ).fetchone()
            expected_dependency_hash = run["dependency_snapshot_hash"]
            expected_input_hash = checkpoint["input_hash"] if checkpoint is not None else None
            observed_input_hash: str | None = None
            reasons: list[str] = []
            if expected_dependency_hash is None:
                reasons.append("LEGACY_DEPENDENCY_SNAPSHOT_MISSING")
            elif expected_dependency_hash != observed_dependency_hash:
                reasons.append("DEPENDENCY_SNAPSHOT_DRIFTED")
            if checkpoint is not None:
                checkpoint_step_key = checkpoint["step_key"]
                checkpoint_attempt = checkpoint["attempt"]
                plan_step = next(
                    (
                        item
                        for item in plan["steps"]
                        if item.get("stepKey") == checkpoint_step_key
                    ),
                    None,
                )
                if (
                    expected_input_hash is None
                    or checkpoint_attempt is None
                    or plan_step is None
                ):
                    reasons.append("CHECKPOINT_INPUT_SNAPSHOT_MISSING")
                else:
                    observed_input_hash = self._step_input_hash(
                        run, plan, plan_step, int(checkpoint_attempt)
                    )
                    if expected_input_hash != observed_input_hash:
                        reasons.append("CHECKPOINT_INPUT_HASH_DRIFTED")
            decision = "reuse" if not reasons else "invalidated"
            decision_payload = {
                "runId": run_id,
                "runVersion": expected_run_version,
                "checkpointId": checkpoint["checkpoint_id"] if checkpoint is not None else None,
                "decision": decision,
                "reasonCodes": reasons,
                "expectedDependencySnapshotHash": expected_dependency_hash,
                "observedDependencySnapshotHash": observed_dependency_hash,
                "expectedInputHash": expected_input_hash,
                "observedInputHash": observed_input_hash,
                "reason": reason,
            }
            request_hash = _canonical_hash(request)
            content_hash = _canonical_hash(decision_payload)
            decision_id = f"resume-decision-{content_hash[:20]}"
            conn.execute(
                """INSERT INTO aip_run_resume_decision_revision
                   (org_id,project_id,decision_id,run_id,revision,checkpoint_id,decision,
                    reason_codes,expected_dependency_snapshot_hash,observed_dependency_snapshot_hash,
                    expected_input_hash,observed_input_hash,actor,idempotency_key,request_hash,
                    content_hash,created_at)
                   VALUES(%s,%s,%s,%s,1,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,NOW())""",
                (*scope.key, decision_id, run_id, decision_payload["checkpointId"], decision,
                 self._json(reasons), expected_dependency_hash, observed_dependency_hash,
                 expected_input_hash, observed_input_hash, actor, idempotency_key,
                 request_hash, content_hash),
            )
            if reasons:
                conn.commit()
                raise AipTaskVersionConflict("resume dependency snapshot drifted")
            target = transition_task_status(TaskStatus.PAUSED, TaskStatus.EXECUTING)
            conn.execute(
                """UPDATE aip_task_run SET status='running',pause_requested_at=NULL,pause_reason=NULL,
                   version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s
                   AND run_id=%s AND version=%s""",
                (*scope.key, run_id, expected_run_version),
            )
            conn.execute(
                """UPDATE aip_task SET status=%s,version=version+1,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s""",
                (target.value, *scope.key, task["task_id"], expected_task_version),
            )
            self._record_control_receipt(conn, scope, run_id, actor, "resume", idempotency_key, request)
            result = self._control_result(conn, scope, run_id, str(task["task_id"]))
            conn.commit()
            return result

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
            if run["status"] not in {"queued", "running", "pausing", "paused"}:
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
                "SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s",
                (scope.org_id, scope.project_id, run["plan_revision_id"]),
            ).fetchone()
            plan_steps = {str(step.get("stepKey")): step for step in plan["steps"]} if plan else {}
            if plan is None or step_key not in plan_steps:
                raise AipTaskNotFound("plan step not found in scope")
            row = conn.execute(
                """SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s
                   AND step_key=%s ORDER BY attempt DESC LIMIT 1 FOR UPDATE""",
                (scope.org_id, scope.project_id, run_id, step_key),
            ).fetchone()
            now = datetime.now(timezone.utc)
            expires = now + timedelta(seconds=lease_seconds)
            attempt = 1 if row is None else int(row["attempt"])
            input_hash = self._step_input_hash(run, plan, plan_steps[step_key], attempt)
            provider_fingerprint = _canonical_hash(
                {"runId": run_id, "stepKey": step_key, "attempt": attempt, "inputHash": input_hash}
            )
            assignment = conn.execute(
                """SELECT * FROM aip_execution_assignment_head WHERE org_id=%s AND project_id=%s
                   AND step_run_id=%s AND attempt=%s FOR UPDATE""",
                (*scope.key, row["step_run_id"], attempt),
            ).fetchone() if row is not None else None
            fence = (0 if assignment is None else int(assignment["current_fence"])) + 1
            assignment_lease_id = f"execution-lease-{uuid.uuid4().hex[:20]}"
            if row is None:
                step_run_id = f"step-run-{uuid.uuid4().hex[:20]}"
                row = conn.execute(
                    """INSERT INTO aip_step_run (
                         org_id,project_id,step_run_id,run_id,step_key,attempt,status,
                         lease_owner,lease_expires_at,heartbeat_at,fence,assignment_lease_id,
                         input_hash,provider_request_fingerprint,safe_point,reconcile_required,
                         created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,1,'running',%s,%s,%s,%s,%s,%s,%s,FALSE,FALSE,
                         NOW(),NOW()) RETURNING *""",
                    (scope.org_id, scope.project_id, step_run_id, run_id, step_key, worker_id,
                     expires, now, fence, assignment_lease_id, input_hash, provider_fingerprint),
                ).fetchone()
            else:
                lease_expires = row["lease_expires_at"]
                if row["status"] == "running" and lease_expires and lease_expires > now:
                    raise AipTaskVersionConflict("step already has an active lease")
                if row["status"] == "running" and row["action_ref"] is not None:
                    conn.execute(
                        """UPDATE aip_step_run SET status='unknown',reconcile_required=TRUE,
                           error=%s::jsonb,updated_at=NOW()
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
                         heartbeat_at=%s,fence=%s,assignment_lease_id=%s,input_hash=%s,
                         provider_request_fingerprint=%s,safe_point=FALSE,reconcile_required=FALSE,
                         updated_at=NOW() WHERE org_id=%s AND project_id=%s AND step_run_id=%s
                       RETURNING *""",
                    (worker_id, expires, now, fence, assignment_lease_id, input_hash,
                     provider_fingerprint, scope.org_id, scope.project_id, row["step_run_id"]),
                ).fetchone()
            owner = self._json({"kind": "tool_binding", "resourceId": worker_id, "version": 1})
            if assignment is None:
                conn.execute(
                    """INSERT INTO aip_execution_assignment_head
                       (org_id,project_id,run_id,step_run_id,attempt,owner,current_fence,
                        lease_id,lease_expires_at,version,updated_at)
                       VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,1,%s)""",
                    (*scope.key, run_id, row["step_run_id"], int(row["attempt"]), owner,
                     fence, assignment_lease_id, expires, now),
                )
            else:
                conn.execute(
                    """UPDATE aip_execution_assignment_head SET owner=%s::jsonb,current_fence=%s,
                       lease_id=%s,lease_expires_at=%s,version=version+1,updated_at=%s
                       WHERE org_id=%s AND project_id=%s AND step_run_id=%s AND attempt=%s""",
                    (owner, fence, assignment_lease_id, expires, now, *scope.key,
                     row["step_run_id"], int(row["attempt"])),
                )
            conn.commit()
            return StepLease(
                step_run_id=str(row["step_run_id"]),
                run_id=run_id,
                step_key=step_key,
                attempt=int(row["attempt"]),
                worker_id=worker_id,
                fence=fence,
                assignment_lease_id=assignment_lease_id,
                input_hash=input_hash,
                provider_request_fingerprint=provider_fingerprint,
                lease_expires_at=row["lease_expires_at"],
            )

    def heartbeat_step(
        self, scope: TenantScope, step_run_id: str, worker_id: str, fence: int, *, lease_seconds: int
    ) -> StepLease:
        expires = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        with self._connect(scope) as conn:
            row = conn.execute(
                """UPDATE aip_step_run SET heartbeat_at=NOW(),lease_expires_at=%s,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND step_run_id=%s AND status='running'
                     AND lease_owner=%s AND fence=%s AND lease_expires_at>NOW()
                     AND EXISTS (SELECT 1 FROM aip_execution_assignment_head head
                       WHERE head.org_id=aip_step_run.org_id AND head.project_id=aip_step_run.project_id
                         AND head.step_run_id=aip_step_run.step_run_id AND head.attempt=aip_step_run.attempt
                         AND head.current_fence=%s AND head.lease_id=aip_step_run.assignment_lease_id
                         AND head.lease_expires_at>NOW()) RETURNING *""",
                (expires, scope.org_id, scope.project_id, step_run_id, worker_id, fence, fence),
            ).fetchone()
            if row is None:
                raise AipTaskVersionConflict("step lease is missing, expired, or owned by another worker")
            conn.execute(
                """UPDATE aip_execution_assignment_head SET lease_expires_at=%s,
                   version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s
                   AND step_run_id=%s AND attempt=%s AND current_fence=%s
                   AND lease_id=%s AND lease_expires_at>NOW()""",
                (expires, *scope.key, step_run_id, int(row["attempt"]), fence,
                 row["assignment_lease_id"]),
            )
            conn.commit()
            return StepLease(
                step_run_id=step_run_id,
                run_id=str(row["run_id"]),
                step_key=str(row["step_key"]),
                attempt=int(row["attempt"]),
                worker_id=worker_id,
                fence=int(row["fence"]),
                assignment_lease_id=str(row["assignment_lease_id"]),
                input_hash=str(row["input_hash"]),
                provider_request_fingerprint=str(row["provider_request_fingerprint"]),
                lease_expires_at=row["lease_expires_at"],
            )

    def record_step_phase(
        self,
        scope: TenantScope,
        step_run_id: str,
        worker_id: str,
        fence: int,
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
            if step is None or int(step["fence"] or 0) != fence or not self._assignment_fence_current(conn, scope, step, fence):
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
        if not (
            isinstance(content_hash, str)
            and len(content_hash) == 64
            and all(character in "0123456789abcdef" for character in content_hash)
        ):
            raise AipTaskTransitionBlocked("artifact contentHash must be exact sha256")
        family_id: str | None = None
        family_revision: int | None = None
        family_role: str | None = None
        profile: str | None = None
        platform: str | None = None
        rendition_spec: dict[str, Any] | None = None
        rendition_spec_hash: str | None = None
        lineage_refs: list[dict[str, Any]] | None = None
        family = metadata.get("artifactFamily") if isinstance(metadata, dict) else None
        if family is not None:
            if not isinstance(family, dict):
                raise AipTaskTransitionBlocked("artifactFamily metadata must be an object")
            family_id = family.get("familyId")
            family_revision = family.get("familyRevision")
            family_role = family.get("role")
            profile = family.get("profile")
            platform = family.get("platform")
            rendition_spec = family.get("renditionSpec")
            lineage_refs = family.get("lineageRefs")
            if not (
                isinstance(family_id, str) and family_id.strip()
                and isinstance(family_revision, int) and not isinstance(family_revision, bool)
                and family_revision >= 1
                and family_role in {"family_manifest", "preview", "draft", "master", "variant"}
                and isinstance(profile, str) and profile.strip()
                and isinstance(platform, str) and platform.strip()
                and isinstance(rendition_spec, dict)
                and isinstance(lineage_refs, list) and lineage_refs
            ):
                raise AipTaskTransitionBlocked("artifactFamily metadata is incomplete")
            for ref in lineage_refs:
                if not (
                    isinstance(ref, dict)
                    and isinstance(ref.get("resourceType"), str) and ref["resourceType"]
                    and isinstance(ref.get("resourceId"), str) and ref["resourceId"]
                    and isinstance(ref.get("revision"), int)
                    and not isinstance(ref.get("revision"), bool)
                    and ref["revision"] >= 1
                    and isinstance(ref.get("contentHash"), str)
                    and len(ref["contentHash"]) == 64
                    and all(
                        character in "0123456789abcdef"
                        for character in ref["contentHash"]
                    )
                ):
                    raise AipTaskTransitionBlocked(
                        "artifactFamily lineageRefs must be exact revision refs"
                    )
            rendition_spec_hash = _canonical_hash(rendition_spec)
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
                     source,evidence_refs,marking,content_hash,metadata,created_by,created_at,
                     family_id,family_revision,family_role,profile,platform,rendition_spec,
                     rendition_spec_hash,lineage_refs)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,
                     %s,NOW(),%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb)""",
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
                    family_id,
                    family_revision,
                    family_role,
                    profile,
                    platform,
                    self._json(rendition_spec) if rendition_spec is not None else None,
                    rendition_spec_hash,
                    self._json(lineage_refs) if lineage_refs is not None else None,
                ),
            )
            conn.commit()
        return artifact_id

    def complete_step(
        self, scope: TenantScope, step_run_id: str, worker_id: str, fence: int, actor: str
    ) -> str:
        with self._connect(scope) as conn:
            step = conn.execute(
                """SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND step_run_id=%s
                   AND status='running' AND lease_owner=%s AND lease_expires_at>NOW() FOR UPDATE""",
                (scope.org_id, scope.project_id, step_run_id, worker_id),
            ).fetchone()
            if step is None or int(step["fence"] or 0) != fence or not self._assignment_fence_current(conn, scope, step, fence):
                raise AipTaskVersionConflict("step completion requires an active owned lease")
            if any(step[name] is None for name in ("think_ref", "action_ref", "verify_ref", "observe_ref")):
                raise AipTaskTransitionBlocked("all four TAOR evidence phases are required")
            sequence = int(
                conn.execute(
                    "SELECT COALESCE(MAX(sequence),0)+1 AS seq FROM aip_checkpoint WHERE org_id=%s AND project_id=%s AND run_id=%s",
                    (scope.org_id, scope.project_id, step["run_id"]),
                ).fetchone()["seq"]
            )
            run = conn.execute(
                """SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s
                   FOR UPDATE""",
                (*scope.key, step["run_id"]),
            ).fetchone()
            plan = conn.execute(
                """SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s
                   AND plan_revision_id=%s""",
                (*scope.key, run["plan_revision_id"]),
            ).fetchone()
            plan_step = next(item for item in plan["steps"] if item.get("stepKey") == step["step_key"])
            dependency_snapshot = self._runtime_dependency_snapshot(run, plan)
            dependency_hash = _canonical_hash(dependency_snapshot)
            checkpoint_policy = dict(plan_step.get("checkpointPolicy") or {})
            artifact_refs = list(step["output_refs"] or [])
            receipt_refs = [value for value in (step["action_ref"], step["verify_ref"]) if value]
            lineage = {
                "taskRunRef": {"resourceType": "TaskRun", "resourceId": step["run_id"], "version": int(run["version"])},
                "stepRunRef": {"resourceType": "StepRun", "resourceId": step_run_id, "version": int(step["attempt"])},
                "planRevisionRef": {"resourceType": "PlanRevision", "resourceId": run["plan_revision_id"], "revision": int(plan["revision"]), "contentHash": plan["content_hash"]},
                "assignment": {"leaseId": step["assignment_lease_id"], "owner": worker_id, "fence": fence},
            }
            checkpoint_id = f"checkpoint-{uuid.uuid4().hex[:20]}"
            state = {
                "stepRunId": step_run_id,
                "stepKey": step["step_key"],
                "attempt": int(step["attempt"]),
                "status": "succeeded",
                "inputHash": step["input_hash"],
                "providerRequestFingerprint": step["provider_request_fingerprint"],
                "dependencySnapshotHash": dependency_hash,
                "artifactRefs": artifact_refs,
                "lineage": lineage,
            }
            conn.execute(
                """INSERT INTO aip_checkpoint (
                     org_id,project_id,checkpoint_id,run_id,sequence,schema_version,step_key,
                     state_hash,state_snapshot_ref,artifact_refs,attempt,plan_revision_id,input_hash,
                     provider_request_fingerprint,dependency_snapshot,dependency_snapshot_hash,
                     checkpoint_policy,usage_refs,receipt_refs,lineage,created_by,created_at)
                   VALUES (%s,%s,%s,%s,%s,2,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,
                     %s::jsonb,%s,%s::jsonb,'[]'::jsonb,%s::jsonb,%s::jsonb,%s,NOW())""",
                (
                    scope.org_id,
                    scope.project_id,
                    checkpoint_id,
                    step["run_id"],
                    sequence,
                    step["step_key"],
                    _canonical_hash(state),
                    self._json(state),
                    self._json(artifact_refs),
                    int(step["attempt"]),
                    run["plan_revision_id"],
                    step["input_hash"],
                    step["provider_request_fingerprint"],
                    self._json(dependency_snapshot),
                    dependency_hash,
                    self._json(checkpoint_policy),
                    self._json(receipt_refs),
                    self._json(lineage),
                    actor,
                ),
            )
            conn.execute(
                """UPDATE aip_step_run SET status='succeeded',lease_owner=NULL,lease_expires_at=NULL,
                     heartbeat_at=NULL,safe_point=TRUE,updated_at=NOW()
                     WHERE org_id=%s AND project_id=%s AND step_run_id=%s""",
                (scope.org_id, scope.project_id, step_run_id),
            )
            remaining_active = conn.execute(
                """SELECT 1 FROM aip_step_run WHERE org_id=%s AND project_id=%s
                   AND run_id=%s AND status='running' LIMIT 1""",
                (*scope.key, step["run_id"]),
            ).fetchone()
            run_status = (
                "paused"
                if run["status"] == "pausing" and remaining_active is None
                else run["status"]
            )
            conn.execute(
                """UPDATE aip_task_run SET last_checkpoint_id=%s,status=%s,version=version+1,
                   updated_at=NOW() WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (checkpoint_id, run_status, scope.org_id, scope.project_id, step["run_id"]),
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
            # W-L14 / W4-04: only the latest attempt per stepKey counts as current.
            # A historical succeeded attempt must not hide a newer queued/running rework.
            succeeded = {
                str(row["step_key"])
                for row in conn.execute(
                    """SELECT step_key FROM (
                         SELECT DISTINCT ON (step_key) step_key, status
                         FROM aip_step_run
                         WHERE org_id=%s AND project_id=%s AND run_id=%s
                         ORDER BY step_key, attempt DESC
                       ) latest
                       WHERE status='succeeded'""",
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
        self, scope: TenantScope, step_run_id: str, worker_id: str, fence: int,
        actor: str, error: dict[str, Any]
    ) -> RunControlResult:
        with self._connect(scope) as conn:
            step = conn.execute(
                """SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND step_run_id=%s
                   AND status='running' AND lease_owner=%s AND lease_expires_at>NOW() FOR UPDATE""",
                (scope.org_id, scope.project_id, step_run_id, worker_id),
            ).fetchone()
            if step is None or int(step["fence"] or 0) != fence or not self._assignment_fence_current(conn, scope, step, fence):
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

    @staticmethod
    def _runtime_dependency_snapshot(run: Any, plan: Any) -> dict[str, Any]:
        if plan is None:
            raise AipTaskNotFound("approved plan revision not found in scope")
        production_contract = dict(plan["risk"] or {}).get("productionContract")
        return {
            "runId": str(run["run_id"]),
            "planRevisionId": str(plan["plan_revision_id"]),
            "planRevision": int(plan["revision"]),
            "planContentHash": str(plan["content_hash"]),
            "steps": list(plan["steps"] or []),
            "dependencies": list(plan["dependencies"] or []),
            "productionContract": production_contract if isinstance(production_contract, dict) else None,
            "logicGraphId": run["logic_graph_id"],
            "logicRevision": run["logic_revision"],
        }

    @classmethod
    def _runtime_dependency_snapshot_hash(cls, run: Any, plan: Any) -> str:
        return _canonical_hash(cls._runtime_dependency_snapshot(run, plan))

    @classmethod
    def _step_input_hash(cls, run: Any, plan: Any, plan_step: dict[str, Any], attempt: int) -> str:
        return _canonical_hash(
            {
                "dependencySnapshotHash": cls._runtime_dependency_snapshot_hash(run, plan),
                "step": plan_step,
                "attempt": attempt,
            }
        )

    @staticmethod
    def _assignment_fence_current(
        conn: Any, scope: TenantScope, step: Any, fence: int
    ) -> bool:
        row = conn.execute(
            """SELECT 1 FROM aip_execution_assignment_head WHERE org_id=%s AND project_id=%s
               AND step_run_id=%s AND attempt=%s AND current_fence=%s AND lease_id=%s
               AND lease_expires_at>NOW()""",
            (*scope.key, step["step_run_id"], int(step["attempt"]), fence,
             step["assignment_lease_id"]),
        ).fetchone()
        return row is not None

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
            dependency_snapshot_hash=row.get("dependency_snapshot_hash"),
            pause_requested_at=row.get("pause_requested_at"),
            pause_reason=row.get("pause_reason"),
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
