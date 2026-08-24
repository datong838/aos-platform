"""PostgreSQL authority for W3-08 dispatch intent and task priority."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_dispatch_control import (
    ConfirmDispatchIntentRequest,
    CreateDispatchIntentRequest,
    DecideTaskPriorityRequest,
    DispatchBlocker,
    DispatchCommandKind,
    DispatchCommandTarget,
    DispatchConfirmationReceipt,
    DispatchControlObservation,
    DispatchIntentRevision,
    DispatchIntentStatus,
    TaskPriorityDecisionRevision,
)
from aos_api.aip_responsibility_assignment import RuntimeAuthorityRef
from aos_api.db import connect as db_connect
from aos_api.public_contracts import TERMINAL_TASK_STATUSES, TaskStatus
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class DispatchControlError(RuntimeError):
    code = "DISPATCH_CONTROL_FAILED"


class DispatchControlNotFound(DispatchControlError):
    code = "DISPATCH_CONTROL_NOT_FOUND"


class DispatchControlConflict(DispatchControlError):
    code = "DISPATCH_CONTROL_CONFLICT"


class DispatchControlBlocked(DispatchControlError):
    code = "DISPATCH_CONTROL_BLOCKED"


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _identifier(prefix: str, scope: TenantScope, digest: str) -> str:
    return f"{prefix}-{_hash([scope.org_id, scope.project_id, digest])[:20]}"


_COMMANDS = {
    DispatchCommandKind.MODULE_HANDOFF: DispatchCommandTarget(
        commandKind="module_handoff", routeIdentity="aip.module-handoff.issue",
        routePath="/v1/aip/handoffs", requiredPermission="aip.handoff.issue",
    ),
    DispatchCommandKind.RESPONSIBILITY_SUCCESSOR: DispatchCommandTarget(
        commandKind="responsibility_successor", routeIdentity="aip.responsibility.successor",
        routePath="/v1/aip/responsibility-assignments/successors", requiredPermission="aip.responsibility.write",
    ),
    DispatchCommandKind.RUNTIME_TAKEOVER: DispatchCommandTarget(
        commandKind="runtime_takeover", routeIdentity="aip.responsibility.takeover",
        routePath="/v1/aip/responsibility-assignments/takeovers", requiredPermission="aip.responsibility.write",
    ),
}


class AipDispatchControlStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create_intent(self, scope: TenantScope, body: CreateDispatchIntentRequest, *, actor: str, idempotency_key: str, now: datetime | None = None) -> DispatchIntentRevision:
        now = now or datetime.now(UTC)
        request = body.model_dump(mode="json", by_alias=True)
        request_hash = _hash(request)
        with self._connect_factory(scope) as conn:
            replay = conn.execute("SELECT * FROM aip_dispatch_intent_revision WHERE org_id=%s AND project_id=%s AND idempotency_key=%s", (*scope.key, idempotency_key)).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise DispatchControlConflict("idempotency key was reused for a different dispatch intent")
                return self._intent(scope, replay)
            task = conn.execute("SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s", (*scope.key, body.task_ref.resource_id)).fetchone()
            if task is None:
                raise DispatchControlNotFound("task not found in scope")
            blockers: list[DispatchBlocker] = []
            if int(task["version"]) != body.task_ref.version:
                blockers.append(self._blocker("TASK_VERSION_DRIFTED", "Task", "refresh the Task exact version"))
            if TaskStatus(task["status"]) in TERMINAL_TASK_STATUSES:
                blockers.append(self._blocker("TASK_TERMINAL", "Task", "terminal Task cannot be dispatched"))
            if body.task_run_ref:
                run = conn.execute("SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s", (*scope.key, body.task_run_ref.resource_id)).fetchone()
                if run is None or str(run["task_id"]) != body.task_ref.resource_id:
                    blockers.append(self._blocker("TASK_RUN_NOT_FOUND", "TaskRun", "resolve a TaskRun belonging to the exact Task"))
                elif int(run["version"]) != body.task_run_ref.version:
                    blockers.append(self._blocker("TASK_RUN_VERSION_DRIFTED", "TaskRun", "refresh the TaskRun exact version"))
            if body.step_run_ref:
                step = conn.execute("SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND step_run_id=%s", (*scope.key, body.step_run_ref.resource_id)).fetchone()
                if step is None or not body.task_run_ref or str(step["run_id"]) != body.task_run_ref.resource_id:
                    blockers.append(self._blocker("STEP_RUN_NOT_FOUND", "StepRun", "resolve a StepRun belonging to the exact TaskRun"))
                elif int(step["attempt"]) != body.step_run_ref.version:
                    blockers.append(self._blocker("STEP_RUN_ATTEMPT_DRIFTED", "StepRun", "refresh the exact StepRun attempt"))
                if step and (step.get("status") == "unknown" or (step.get("action_ref") and not step.get("verify_ref"))):
                    blockers.append(self._blocker("PROVIDER_OUTCOME_UNKNOWN", "StepRun", "reconcile provider outcome before takeover"))
                if step and step.get("lease_expires_at") and step["lease_expires_at"] > now:
                    blockers.append(self._blocker("ACTIVE_EXECUTION_LEASE", "StepRun", "wait for or explicitly close the active lease"))
            if body.responsibility_plan_ref:
                plan = conn.execute(
                    """SELECT content_hash,lifecycle FROM aip_responsibility_plan_revision
                       WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s""",
                    (*scope.key, body.responsibility_plan_ref.resource_id, body.responsibility_plan_ref.revision),
                ).fetchone()
                if plan is None:
                    blockers.append(self._blocker("RESPONSIBILITY_PLAN_NOT_FOUND", "ResponsibilityPlanRevision", "resolve the exact responsibility plan revision"))
                elif plan["content_hash"] != body.responsibility_plan_ref.content_hash:
                    blockers.append(self._blocker("RESPONSIBILITY_PLAN_HASH_DRIFTED", "ResponsibilityPlanRevision", "refresh the exact responsibility plan hash"))
                elif plan["lifecycle"] != "frozen":
                    blockers.append(self._blocker("RESPONSIBILITY_PLAN_NOT_FROZEN", "ResponsibilityPlanRevision", "freeze the responsibility plan before dispatch"))
            if body.expected_fence is not None and body.task_run_ref and body.step_run_ref:
                assignment = conn.execute(
                    """SELECT current_fence FROM aip_execution_assignment_head
                       WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_run_id=%s AND attempt=%s""",
                    (*scope.key, body.task_run_ref.resource_id, body.step_run_ref.resource_id, body.step_run_ref.version),
                ).fetchone()
                actual_fence = 0 if assignment is None else int(assignment["current_fence"])
                if actual_fence != body.expected_fence:
                    blockers.append(self._blocker("ASSIGNMENT_FENCE_DRIFTED", "ExecutionAssignment", "refresh the current execution fence"))
            diff = {"identity": {"from": body.source_identity, "to": body.target_identity}, "slot": {"from": body.source_slot_id, "to": body.target_slot_id}}
            payload = {**request, "diff": diff, "blockers": [item.model_dump(mode="json", by_alias=True) for item in blockers]}
            content_hash = _hash(payload)
            intent_id = _identifier("dispatch-intent", scope, content_hash)
            readiness = DispatchIntentStatus.BLOCKED if blockers else DispatchIntentStatus.READY
            row = conn.execute(
                """INSERT INTO aip_dispatch_intent_revision
                   (org_id,project_id,intent_id,revision,task_ref,task_run_ref,step_run_ref,responsibility_plan_ref,
                    command_kind,source_identity,target_identity,source_slot_id,target_slot_id,expected_fence,
                    reason_code,policy_ref,diff,impact,readiness,blockers,maker,idempotency_key,request_hash,content_hash,created_at)
                   VALUES (%s,%s,%s,1,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s,%s) RETURNING *""",
                (*scope.key, intent_id, self._json(request["taskRef"]), self._nullable_json(request.get("taskRunRef")), self._nullable_json(request.get("stepRunRef")), self._nullable_json(request.get("responsibilityPlanRef")), body.command_kind.value, body.source_identity, body.target_identity, body.source_slot_id, body.target_slot_id, body.expected_fence, body.reason_code, self._json(request["policyRef"]), self._json(diff), self._json(body.impact), readiness.value, self._json(payload["blockers"]), actor, idempotency_key, request_hash, content_hash, now),
            ).fetchone()
            conn.commit()
            return self._intent(scope, row)

    def confirm_intent(self, scope: TenantScope, intent_id: str, body: ConfirmDispatchIntentRequest, *, actor: str, idempotency_key: str, now: datetime | None = None) -> DispatchConfirmationReceipt:
        now = now or datetime.now(UTC)
        request_hash = _hash({"intentId": intent_id, **body.model_dump(mode="json", by_alias=True)})
        with self._connect_factory(scope) as conn:
            replay = conn.execute("SELECT * FROM aip_dispatch_confirmation_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key=%s", (*scope.key, idempotency_key)).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise DispatchControlConflict("idempotency key was reused for a different confirmation")
                return self._confirmation(scope, replay)
            intent = conn.execute("SELECT * FROM aip_dispatch_intent_revision WHERE org_id=%s AND project_id=%s AND intent_id=%s FOR UPDATE", (*scope.key, intent_id)).fetchone()
            if intent is None:
                raise DispatchControlNotFound("dispatch intent not found in scope")
            if int(intent["revision"]) != body.expected_revision or intent["content_hash"] != body.expected_content_hash:
                raise DispatchControlConflict("dispatch intent exact revision drifted")
            if intent["readiness"] != "ready" or intent["blockers"]:
                raise DispatchControlBlocked("dispatch intent is not ready")
            if intent["maker"] == actor:
                raise DispatchControlBlocked("maker-checker separation required")
            task_ref = self._load(intent["task_ref"])
            task = conn.execute("SELECT version,status FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s", (*scope.key, task_ref["resourceId"])).fetchone()
            if task is None or int(task["version"]) != int(task_ref["version"]) or TaskStatus(task["status"]) in TERMINAL_TASK_STATUSES:
                raise DispatchControlConflict("Task drifted after intent creation")
            revalidation = self._revalidate_intent_dependencies(conn, scope, intent, now=now)
            if revalidation:
                codes = {item.code for item in revalidation}
                if codes & {"PROVIDER_OUTCOME_UNKNOWN", "ACTIVE_EXECUTION_LEASE"}:
                    raise DispatchControlBlocked("dispatch safety state changed after intent creation")
                raise DispatchControlConflict("dispatch dependency drifted after intent creation")
            content_hash = _hash({"intentId": intent_id, "intentHash": intent["content_hash"], "checker": actor, "state": "canonical_command_required"})
            confirmation_id = _identifier("dispatch-confirmation", scope, content_hash)
            row = conn.execute(
                """INSERT INTO aip_dispatch_confirmation_receipt
                   (org_id,project_id,confirmation_id,intent_id,intent_revision,intent_content_hash,command_kind,
                    invocation_state,checker,idempotency_key,request_hash,content_hash,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'canonical_command_required',%s,%s,%s,%s,%s) RETURNING *""",
                (*scope.key, confirmation_id, intent_id, intent["revision"], intent["content_hash"], intent["command_kind"], actor, idempotency_key, request_hash, content_hash, now),
            ).fetchone()
            conn.commit()
            return self._confirmation(scope, row)

    def decide_priority(self, scope: TenantScope, body: DecideTaskPriorityRequest, *, actor: str, idempotency_key: str, now: datetime | None = None) -> TaskPriorityDecisionRevision:
        now = now or datetime.now(UTC)
        request = body.model_dump(mode="json", by_alias=True)
        request_hash = _hash(request)
        with self._connect_factory(scope) as conn:
            replay = conn.execute("SELECT * FROM aip_task_priority_decision_revision WHERE org_id=%s AND project_id=%s AND idempotency_key=%s", (*scope.key, idempotency_key)).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise DispatchControlConflict("idempotency key was reused for a different priority decision")
                return self._priority(scope, replay)
            task = conn.execute("SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s FOR UPDATE", (*scope.key, body.task_ref.resource_id)).fetchone()
            if task is None:
                raise DispatchControlNotFound("task not found in scope")
            if int(task["version"]) != body.task_ref.version:
                raise DispatchControlConflict("Task version drifted")
            if int(task["priority"]) != body.old_priority:
                raise DispatchControlConflict("Task priority drifted")
            if TaskStatus(task["status"]) in TERMINAL_TASK_STATUSES:
                raise DispatchControlBlocked("terminal Task cannot be reprioritized")
            after_ref = RuntimeAuthorityRef(resourceType="Task", resourceId=body.task_ref.resource_id, version=body.task_ref.version + 1)
            content_hash = _hash({**request, "taskRefAfter": after_ref.model_dump(mode="json", by_alias=True), "actor": actor})
            decision_id = _identifier("task-priority", scope, content_hash)
            row = conn.execute(
                """INSERT INTO aip_task_priority_decision_revision
                   (org_id,project_id,decision_id,revision,task_ref_before,task_ref_after,old_priority,new_priority,
                    reason_code,policy_ref,actor,idempotency_key,request_hash,content_hash,created_at)
                   VALUES (%s,%s,%s,1,%s::jsonb,%s::jsonb,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s) RETURNING *""",
                (*scope.key, decision_id, self._json(request["taskRef"]), self._json(after_ref.model_dump(mode="json", by_alias=True)), body.old_priority, body.new_priority, body.reason_code, self._json(request["policyRef"]), actor, idempotency_key, request_hash, content_hash, now),
            ).fetchone()
            updated = conn.execute("UPDATE aip_task SET priority=%s,version=version+1,updated_at=%s WHERE org_id=%s AND project_id=%s AND task_id=%s AND version=%s RETURNING version", (body.new_priority, now, *scope.key, body.task_ref.resource_id, body.task_ref.version)).fetchone()
            if updated is None or int(updated["version"]) != after_ref.version:
                raise DispatchControlConflict("Task priority CAS failed")
            conn.commit()
            return self._priority(scope, row)

    def observe_task(self, scope: TenantScope, task_id: str, *, now: datetime | None = None) -> DispatchControlObservation:
        now = now or datetime.now(UTC)
        with self._connect_factory(scope) as conn:
            task = conn.execute("SELECT task_id,version FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s", (*scope.key, task_id)).fetchone()
            if task is None:
                raise DispatchControlNotFound("task not found in scope")
            intents = conn.execute("SELECT * FROM aip_dispatch_intent_revision WHERE org_id=%s AND project_id=%s AND task_ref->>'resourceId'=%s ORDER BY created_at,intent_id", (*scope.key, task_id)).fetchall()
            confirmations = conn.execute(
                """SELECT confirmation.* FROM aip_dispatch_confirmation_receipt confirmation
                   JOIN aip_dispatch_intent_revision intent ON intent.org_id=confirmation.org_id
                    AND intent.project_id=confirmation.project_id AND intent.intent_id=confirmation.intent_id
                    AND intent.revision=confirmation.intent_revision
                   WHERE confirmation.org_id=%s AND confirmation.project_id=%s
                    AND intent.task_ref->>'resourceId'=%s ORDER BY confirmation.created_at,confirmation.confirmation_id""",
                (*scope.key, task_id),
            ).fetchall()
            priorities = conn.execute("SELECT * FROM aip_task_priority_decision_revision WHERE org_id=%s AND project_id=%s AND task_ref_after->>'resourceId'=%s ORDER BY created_at,decision_id", (*scope.key, task_id)).fetchall()
        return DispatchControlObservation(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            taskRef={"resourceType": "Task", "resourceId": task_id, "version": int(task["version"])},
            dispatchIntents=[self._intent(scope, row) for row in intents],
            confirmations=[self._confirmation(scope, row) for row in confirmations],
            priorityDecisions=[self._priority(scope, row) for row in priorities],
            evaluatedAt=now,
        )

    @staticmethod
    def _blocker(code: str, dependency: str, action: str) -> DispatchBlocker:
        return DispatchBlocker(code=code, dependency=dependency, requiredAction=action)

    def _revalidate_intent_dependencies(
        self, conn: Any, scope: TenantScope, intent: Any, *, now: datetime
    ) -> list[DispatchBlocker]:
        blockers: list[DispatchBlocker] = []
        task_ref = self._load(intent["task_ref"])
        run_ref = self._load(intent["task_run_ref"])
        step_ref = self._load(intent["step_run_ref"])
        plan_ref = self._load(intent["responsibility_plan_ref"])
        if run_ref:
            run = conn.execute(
                "SELECT task_id,version FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (*scope.key, run_ref["resourceId"]),
            ).fetchone()
            if run is None or str(run["task_id"]) != task_ref["resourceId"]:
                blockers.append(self._blocker("TASK_RUN_NOT_FOUND", "TaskRun", "resolve a TaskRun belonging to the exact Task"))
            elif int(run["version"]) != int(run_ref["version"]):
                blockers.append(self._blocker("TASK_RUN_VERSION_DRIFTED", "TaskRun", "refresh the TaskRun exact version"))
        if step_ref:
            step = conn.execute(
                "SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND step_run_id=%s",
                (*scope.key, step_ref["resourceId"]),
            ).fetchone()
            if step is None or not run_ref or str(step["run_id"]) != run_ref["resourceId"]:
                blockers.append(self._blocker("STEP_RUN_NOT_FOUND", "StepRun", "resolve a StepRun belonging to the exact TaskRun"))
            elif int(step["attempt"]) != int(step_ref["version"]):
                blockers.append(self._blocker("STEP_RUN_ATTEMPT_DRIFTED", "StepRun", "refresh the exact StepRun attempt"))
            if step and (step.get("status") == "unknown" or (step.get("action_ref") and not step.get("verify_ref"))):
                blockers.append(self._blocker("PROVIDER_OUTCOME_UNKNOWN", "StepRun", "reconcile provider outcome before takeover"))
            if step and step.get("lease_expires_at") and step["lease_expires_at"] > now:
                blockers.append(self._blocker("ACTIVE_EXECUTION_LEASE", "StepRun", "wait for or explicitly close the active lease"))
        if plan_ref:
            plan = conn.execute(
                """SELECT content_hash,lifecycle FROM aip_responsibility_plan_revision
                   WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s""",
                (*scope.key, plan_ref["resourceId"], plan_ref["revision"]),
            ).fetchone()
            if plan is None:
                blockers.append(self._blocker("RESPONSIBILITY_PLAN_NOT_FOUND", "ResponsibilityPlanRevision", "resolve the exact responsibility plan revision"))
            elif plan["content_hash"] != plan_ref["contentHash"]:
                blockers.append(self._blocker("RESPONSIBILITY_PLAN_HASH_DRIFTED", "ResponsibilityPlanRevision", "refresh the exact responsibility plan hash"))
            elif plan["lifecycle"] != "frozen":
                blockers.append(self._blocker("RESPONSIBILITY_PLAN_NOT_FROZEN", "ResponsibilityPlanRevision", "freeze the responsibility plan before dispatch"))
        expected_fence = intent["expected_fence"]
        if expected_fence is not None and run_ref and step_ref:
            assignment = conn.execute(
                """SELECT current_fence FROM aip_execution_assignment_head
                   WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_run_id=%s AND attempt=%s""",
                (*scope.key, run_ref["resourceId"], step_ref["resourceId"], step_ref["version"]),
            ).fetchone()
            actual_fence = 0 if assignment is None else int(assignment["current_fence"])
            if actual_fence != int(expected_fence):
                blockers.append(self._blocker("ASSIGNMENT_FENCE_DRIFTED", "ExecutionAssignment", "refresh the current execution fence"))
        return blockers

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def _nullable_json(cls, value: Any) -> str | None:
        return None if value is None else cls._json(value)

    @staticmethod
    def _load(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @classmethod
    def _intent(cls, scope: TenantScope, row: Any) -> DispatchIntentRevision:
        return DispatchIntentRevision(tenant={"orgId": scope.org_id, "projectId": scope.project_id}, intentId=row["intent_id"], revision=row["revision"], taskRef=cls._load(row["task_ref"]), taskRunRef=cls._load(row["task_run_ref"]), stepRunRef=cls._load(row["step_run_ref"]), responsibilityPlanRef=cls._load(row["responsibility_plan_ref"]), command=_COMMANDS[DispatchCommandKind(row["command_kind"])], sourceIdentity=row["source_identity"], targetIdentity=row["target_identity"], sourceSlotId=row["source_slot_id"], targetSlotId=row["target_slot_id"], expectedFence=row["expected_fence"], reasonCode=row["reason_code"], policyRef=cls._load(row["policy_ref"]), diff=cls._load(row["diff"]), impact=cls._load(row["impact"]), readiness=row["readiness"], blockers=cls._load(row["blockers"]), maker=row["maker"], createdAt=row["created_at"], contentHash=row["content_hash"])

    @classmethod
    def _confirmation(cls, scope: TenantScope, row: Any) -> DispatchConfirmationReceipt:
        return DispatchConfirmationReceipt(tenant={"orgId": scope.org_id, "projectId": scope.project_id}, confirmationId=row["confirmation_id"], intentId=row["intent_id"], intentRevision=row["intent_revision"], intentContentHash=row["intent_content_hash"], command=_COMMANDS[DispatchCommandKind(row["command_kind"])], invocationState=row["invocation_state"], checker=row["checker"], createdAt=row["created_at"], contentHash=row["content_hash"])

    @classmethod
    def _priority(cls, scope: TenantScope, row: Any) -> TaskPriorityDecisionRevision:
        return TaskPriorityDecisionRevision(tenant={"orgId": scope.org_id, "projectId": scope.project_id}, decisionId=row["decision_id"], revision=row["revision"], taskRefBefore=cls._load(row["task_ref_before"]), taskRefAfter=cls._load(row["task_ref_after"]), oldPriority=row["old_priority"], newPriority=row["new_priority"], reasonCode=row["reason_code"], policyRef=cls._load(row["policy_ref"]), actor=row["actor"], createdAt=row["created_at"], contentHash=row["content_hash"])
