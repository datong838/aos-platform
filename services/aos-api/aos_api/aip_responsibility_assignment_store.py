"""PostgreSQL authority for W3-07 responsibility successor and takeover."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Callable

from aos_api.aip_contracts import TenantContext
from aos_api.aip_production_contracts import AssigneeRef, ExactRevisionRef
from aos_api.aip_responsibility_assignment import (
    AssertAssignmentFenceRequest,
    AssignmentBlocker,
    AssignmentFenceObservation,
    CreateResponsibilitySuccessorRequest,
    CreateTakeoverRequest,
    DecideTakeoverRequest,
    ExecutionAssignmentLease,
    ResponsibilityAssignmentObservation,
    ResponsibilitySuccessorReceipt,
    RuntimeAuthorityRef,
    TakeoverDecisionReceipt,
    TakeoverDecisionValue,
    TakeoverRequestReceipt,
    TakeoverRequestStatus,
    TakeoverSafetyState,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class ResponsibilityAssignmentError(RuntimeError):
    code = "RESPONSIBILITY_ASSIGNMENT_FAILED"


class ResponsibilityAssignmentConflict(ResponsibilityAssignmentError):
    code = "RESPONSIBILITY_ASSIGNMENT_CONFLICT"


class ResponsibilityAssignmentBlocked(ResponsibilityAssignmentError):
    code = "RESPONSIBILITY_ASSIGNMENT_BLOCKED"


class ResponsibilityAssignmentNotFound(ResponsibilityAssignmentError):
    code = "RESPONSIBILITY_ASSIGNMENT_NOT_FOUND"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _identifier(prefix: str, scope: TenantScope, *parts: object) -> str:
    return f"{prefix}-{_hash([*scope.key, *parts])[:24]}"


def _tenant(scope: TenantScope) -> TenantContext:
    return TenantContext(org_id=scope.org_id, project_id=scope.project_id)


def _assignee_payload(value: AssigneeRef) -> dict[str, Any]:
    return value.model_dump(mode="json", by_alias=True)


def _step_safety(
    step: Any, step_run_id: str, observed_at: datetime
) -> tuple[TakeoverSafetyState, list[AssignmentBlocker]]:
    blockers: list[AssignmentBlocker] = []
    if step["status"] in {"succeeded", "failed", "skipped"}:
        safety = TakeoverSafetyState.STEP_TERMINAL
        blockers.append(
            AssignmentBlocker(
                code="STEP_TERMINAL",
                dependency=step_run_id,
                required_action="start an authorized successor attempt",
            )
        )
    elif step["status"] == "unknown" or (
        step["action_ref"] is not None and step["verify_ref"] is None
    ):
        safety = TakeoverSafetyState.PROVIDER_OUTCOME_UNKNOWN
        blockers.append(
            AssignmentBlocker(
                code="PROVIDER_OUTCOME_UNKNOWN",
                dependency=step_run_id,
                required_action="reconcile the provider outcome before takeover",
            )
        )
    elif (
        step["status"] == "running"
        and step["lease_expires_at"]
        and step["lease_expires_at"] > observed_at
    ):
        safety = TakeoverSafetyState.ACTIVE_LEASE
        blockers.append(
            AssignmentBlocker(
                code="ACTIVE_EXECUTION_LEASE",
                dependency=step_run_id,
                required_action="reach a safe checkpoint or let the existing lease expire",
            )
        )
    else:
        safety = TakeoverSafetyState.SAFE_CHECKPOINT
    return safety, blockers


class AipResponsibilityAssignmentStore:
    def __init__(self, connect_factory: Callable[[TenantScope], Any] = connect) -> None:
        self._connect = connect_factory

    @staticmethod
    def _idempotent_row(
        conn: Any, scope: TenantScope, table: str, key: str, request_hash: str
    ) -> Any | None:
        row = conn.execute(
            f"SELECT * FROM {table} WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
            (*scope.key, key),
        ).fetchone()
        if row is not None and row["request_hash"] != request_hash:
            raise ResponsibilityAssignmentConflict("idempotency key payload drifted")
        return row

    @staticmethod
    def _require_resolution(
        conn: Any,
        scope: TenantScope,
        receipt_id: str,
        assignee: AssigneeRef,
    ) -> None:
        row = conn.execute(
            """SELECT kind,resource_id,version,status FROM aip_assignee_resolution_receipt
               WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
            (*scope.key, receipt_id),
        ).fetchone()
        if row is None:
            raise ResponsibilityAssignmentBlocked("ASSIGNEE_RESOLUTION_MISSING")
        if (
            row["kind"] != assignee.kind.value
            or row["resource_id"] != assignee.resource_id
            or int(row["version"]) != assignee.version
        ):
            raise ResponsibilityAssignmentBlocked("ASSIGNEE_RESOLUTION_DRIFTED")
        if row["status"] != "resolved":
            raise ResponsibilityAssignmentBlocked("ASSIGNEE_NOT_OPERATIONAL")

    def create_successor(
        self,
        scope: TenantScope,
        body: CreateResponsibilitySuccessorRequest,
        *,
        actor: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> ResponsibilitySuccessorReceipt:
        observed_at = now or datetime.now(UTC)
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = _hash(payload)
        with self._connect(scope) as conn:
            replay = self._idempotent_row(
                conn, scope, "aip_responsibility_successor", idempotency_key, request_hash
            )
            if replay is not None:
                return self._successor(scope, replay)
            head = conn.execute(
                """SELECT * FROM aip_responsibility_plan_head
                   WHERE org_id=%s AND project_id=%s AND plan_id=%s FOR UPDATE""",
                (*scope.key, body.source_plan_ref.resource_id),
            ).fetchone()
            source = conn.execute(
                """SELECT * FROM aip_responsibility_plan_revision
                   WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s""",
                (*scope.key, body.source_plan_ref.resource_id, body.source_plan_ref.revision),
            ).fetchone()
            if head is None or source is None:
                raise ResponsibilityAssignmentNotFound("source responsibility plan not found")
            if int(head["version"]) != body.expected_source_version:
                raise ResponsibilityAssignmentConflict("source responsibility plan version drifted")
            if (
                source["content_hash"] != body.source_plan_ref.content_hash
                or source["lifecycle"] != "frozen"
            ):
                raise ResponsibilityAssignmentBlocked("SOURCE_PLAN_NOT_EXACT_FROZEN")
            existing_run = conn.execute(
                """SELECT 1 FROM aip_task_run
                   WHERE org_id=%s AND project_id=%s AND task_id=%s LIMIT 1""",
                (*scope.key, body.task_id),
            ).fetchone()
            if existing_run is not None:
                raise ResponsibilityAssignmentBlocked("TASK_RUN_ALREADY_EXISTS_USE_TAKEOVER")
            self._require_resolution(
                conn, scope, body.resolution_receipt_id, body.target_assignee
            )
            slots = list(_load(source["slots"]))
            selected: dict[str, Any] | None = None
            for slot in slots:
                if slot.get("slotId") == body.slot_id:
                    selected = slot
                    break
            if selected is None:
                raise ResponsibilityAssignmentBlocked("RESPONSIBILITY_SLOT_MISSING")
            source_assignee = AssigneeRef.model_validate(selected["assignee"])
            selected["assignee"] = _assignee_payload(body.target_assignee)
            protected = {
                "independent_review",
                "hard_compliance",
                "external_publication_approval",
                "receipt_reconciliation",
            }
            if selected.get("responsibilityType") in protected:
                target = _assignee_payload(body.target_assignee)
                for slot in slots:
                    if slot is not selected and slot.get("responsibilityType") in protected:
                        if slot.get("assignee") == target:
                            raise ResponsibilityAssignmentBlocked(
                                "PROTECTED_RESPONSIBILITY_SEPARATION_VIOLATION"
                            )
            successor_payload = {
                "profile": source["profile"],
                "templateRef": _load(source["template_ref"]),
                "slots": slots,
                "mergeDecisions": _load(source["merge_decisions"]),
            }
            successor_plan_id = _identifier(
                "responsibility-plan-successor",
                scope,
                body.source_plan_ref.model_dump(mode="json", by_alias=True),
                body.slot_id,
                _assignee_payload(body.target_assignee),
                idempotency_key,
            )
            successor_hash = _hash(successor_payload)
            conn.execute(
                """INSERT INTO aip_responsibility_plan_head
                   (org_id,project_id,plan_id,current_revision,version,updated_at)
                   VALUES(%s,%s,%s,1,1,%s)""",
                (*scope.key, successor_plan_id, observed_at),
            )
            conn.execute(
                """INSERT INTO aip_responsibility_plan_revision
                   (org_id,project_id,plan_id,revision,profile,template_ref,slots,
                    merge_decisions,content_hash,lifecycle,created_by,created_at)
                   VALUES(%s,%s,%s,1,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,'frozen',%s,%s)""",
                (
                    *scope.key,
                    successor_plan_id,
                    source["profile"],
                    _json(successor_payload["templateRef"]),
                    _json(slots),
                    _json(successor_payload["mergeDecisions"]),
                    successor_hash,
                    actor,
                    observed_at,
                ),
            )
            successor_ref = ExactRevisionRef(
                resource_type="ResponsibilityPlanRevision",
                resource_id=successor_plan_id,
                revision=1,
                content_hash=successor_hash,
            )
            authority_payload = {
                "taskId": body.task_id,
                "sourcePlanRef": body.source_plan_ref.model_dump(mode="json", by_alias=True),
                "successorPlanRef": successor_ref.model_dump(mode="json", by_alias=True),
                "slotId": body.slot_id,
                "sourceAssignee": _assignee_payload(source_assignee),
                "targetAssignee": _assignee_payload(body.target_assignee),
                "resolutionReceiptId": body.resolution_receipt_id,
                "reasonCode": body.reason_code,
            }
            content_hash = _hash(authority_payload)
            successor_id = _identifier("responsibility-successor", scope, content_hash)
            row = conn.execute(
                """INSERT INTO aip_responsibility_successor
                   (org_id,project_id,successor_id,task_id,source_plan_ref,successor_plan_ref,
                    slot_id,source_assignee,target_assignee,resolution_receipt_id,reason_code,
                    actor,idempotency_key,request_hash,content_hash,created_at)
                   VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,
                    %s,%s,%s,%s,%s) RETURNING *""",
                (
                    *scope.key,
                    successor_id,
                    body.task_id,
                    _json(authority_payload["sourcePlanRef"]),
                    _json(authority_payload["successorPlanRef"]),
                    body.slot_id,
                    _json(authority_payload["sourceAssignee"]),
                    _json(authority_payload["targetAssignee"]),
                    body.resolution_receipt_id,
                    body.reason_code,
                    actor,
                    idempotency_key,
                    request_hash,
                    content_hash,
                    observed_at,
                ),
            ).fetchone()
            conn.commit()
            return self._successor(scope, row)

    def create_takeover_request(
        self,
        scope: TenantScope,
        body: CreateTakeoverRequest,
        *,
        actor: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TakeoverRequestReceipt:
        observed_at = now or datetime.now(UTC)
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = _hash(payload)
        with self._connect(scope) as conn:
            replay = self._idempotent_row(
                conn, scope, "aip_takeover_request", idempotency_key, request_hash
            )
            if replay is not None:
                return self._takeover_request(scope, replay)
            run = conn.execute(
                """SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s
                   AND run_id=%s""",
                (*scope.key, body.task_run_ref.resource_id),
            ).fetchone()
            step = conn.execute(
                """SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s
                   AND step_run_id=%s""",
                (*scope.key, body.step_run_ref.resource_id),
            ).fetchone()
            if run is None or step is None or step["run_id"] != body.task_run_ref.resource_id:
                raise ResponsibilityAssignmentNotFound("exact TaskRun/StepRun not found")
            if int(run["version"]) != body.task_run_ref.version:
                raise ResponsibilityAssignmentConflict("TaskRun version drifted")
            if int(step["attempt"]) != body.attempt or body.step_run_ref.version != body.attempt:
                raise ResponsibilityAssignmentConflict("StepRun attempt drifted")
            self._require_resolution(
                conn, scope, body.resolution_receipt_id, body.target_owner
            )
            safety, blockers = _step_safety(
                step, body.step_run_ref.resource_id, observed_at
            )
            current = conn.execute(
                """SELECT current_fence FROM aip_execution_assignment_head
                   WHERE org_id=%s AND project_id=%s AND step_run_id=%s AND attempt=%s""",
                (*scope.key, body.step_run_ref.resource_id, body.attempt),
            ).fetchone()
            actual_fence = 0 if current is None else int(current["current_fence"])
            if actual_fence != body.expected_fence:
                raise ResponsibilityAssignmentConflict("assignment fence drifted")
            status = TakeoverRequestStatus.PENDING if not blockers else TakeoverRequestStatus.BLOCKED
            authority_payload = {**payload, "safetyState": safety.value, "status": status.value, "blockers": [item.model_dump(mode="json", by_alias=True) for item in blockers], "maker": actor}
            content_hash = _hash(authority_payload)
            request_id = _identifier("takeover-request", scope, content_hash)
            row = conn.execute(
                """INSERT INTO aip_takeover_request
                   (org_id,project_id,request_id,task_run_ref,step_run_ref,attempt,
                    source_owner,target_owner,resolution_receipt_id,expected_fence,reason_code,
                    safety_state,status,blockers,maker,idempotency_key,request_hash,content_hash,created_at)
                   VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s,
                    %s,%s,%s::jsonb,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    *scope.key,
                    request_id,
                    _json(payload["taskRunRef"]),
                    _json(payload["stepRunRef"]),
                    body.attempt,
                    _json(payload["sourceOwner"]),
                    _json(payload["targetOwner"]),
                    body.resolution_receipt_id,
                    body.expected_fence,
                    body.reason_code,
                    safety.value,
                    status.value,
                    _json(authority_payload["blockers"]),
                    actor,
                    idempotency_key,
                    request_hash,
                    content_hash,
                    observed_at,
                ),
            ).fetchone()
            conn.commit()
            return self._takeover_request(scope, row)

    def decide_takeover(
        self,
        scope: TenantScope,
        request_id: str,
        body: DecideTakeoverRequest,
        *,
        actor: str,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> TakeoverDecisionReceipt:
        observed_at = now or datetime.now(UTC)
        payload = {"requestId": request_id, **body.model_dump(mode="json", by_alias=True)}
        request_hash = _hash(payload)
        with self._connect(scope) as conn:
            replay = self._idempotent_row(
                conn, scope, "aip_takeover_decision_revision", idempotency_key, request_hash
            )
            if replay is not None:
                return self._decision(scope, replay)
            request = conn.execute(
                """SELECT * FROM aip_takeover_request WHERE org_id=%s AND project_id=%s
                   AND request_id=%s FOR UPDATE""",
                (*scope.key, request_id),
            ).fetchone()
            if request is None:
                raise ResponsibilityAssignmentNotFound("takeover request not found")
            if request["maker"] == actor:
                raise ResponsibilityAssignmentBlocked("MAKER_CHECKER_REQUIRED")
            existing = conn.execute(
                """SELECT 1 FROM aip_takeover_decision_revision WHERE org_id=%s
                   AND project_id=%s AND request_id=%s""",
                (*scope.key, request_id),
            ).fetchone()
            actual_version = 0 if existing is None else 1
            if actual_version != body.expected_version:
                raise ResponsibilityAssignmentConflict("takeover decision version drifted")
            if body.decision is TakeoverDecisionValue.APPROVED and request["status"] != "pending":
                raise ResponsibilityAssignmentBlocked("TAKEOVER_REQUEST_NOT_READY")
            lease: ExecutionAssignmentLease | None = None
            if body.decision is TakeoverDecisionValue.APPROVED:
                assert body.lease_expires_at is not None
                if body.lease_expires_at <= observed_at:
                    raise ResponsibilityAssignmentBlocked("ASSIGNMENT_LEASE_EXPIRY_INVALID")
                step_ref = RuntimeAuthorityRef.model_validate(_load(request["step_run_ref"]))
                run_ref = RuntimeAuthorityRef.model_validate(_load(request["task_run_ref"]))
                target_owner = AssigneeRef.model_validate(_load(request["target_owner"]))
                step = conn.execute(
                    """SELECT status,lease_expires_at,action_ref,verify_ref
                       FROM aip_step_run WHERE org_id=%s AND project_id=%s
                       AND step_run_id=%s AND attempt=%s FOR UPDATE""",
                    (*scope.key, step_ref.resource_id, int(request["attempt"])),
                ).fetchone()
                if step is None:
                    raise ResponsibilityAssignmentNotFound("exact StepRun not found")
                safety, blockers = _step_safety(
                    step, step_ref.resource_id, observed_at
                )
                if safety is not TakeoverSafetyState.SAFE_CHECKPOINT:
                    raise ResponsibilityAssignmentBlocked(blockers[0].code)
                current = conn.execute(
                    """SELECT * FROM aip_execution_assignment_head WHERE org_id=%s
                       AND project_id=%s AND step_run_id=%s AND attempt=%s FOR UPDATE""",
                    (*scope.key, step_ref.resource_id, int(request["attempt"])),
                ).fetchone()
                current_fence = 0 if current is None else int(current["current_fence"])
                if current_fence != int(request["expected_fence"]):
                    raise ResponsibilityAssignmentConflict("assignment fence advanced")
                if current is not None and current["lease_expires_at"] > observed_at:
                    raise ResponsibilityAssignmentBlocked("ACTIVE_ASSIGNMENT_LEASE")
                fence = current_fence + 1
                lease_id = _identifier("assignment-lease", scope, request_id, fence)
                owner_payload = _assignee_payload(target_owner)
                if current is None:
                    conn.execute(
                        """INSERT INTO aip_execution_assignment_head
                           (org_id,project_id,run_id,step_run_id,attempt,owner,current_fence,
                            lease_id,lease_expires_at,version,updated_at)
                           VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,1,%s)""",
                        (*scope.key, run_ref.resource_id, step_ref.resource_id, int(request["attempt"]), _json(owner_payload), fence, lease_id, body.lease_expires_at, observed_at),
                    )
                else:
                    conn.execute(
                        """UPDATE aip_execution_assignment_head SET owner=%s::jsonb,
                           current_fence=%s,lease_id=%s,lease_expires_at=%s,
                           version=version+1,updated_at=%s WHERE org_id=%s AND project_id=%s
                           AND step_run_id=%s AND attempt=%s""",
                        (_json(owner_payload), fence, lease_id, body.lease_expires_at, observed_at, *scope.key, step_ref.resource_id, int(request["attempt"])),
                    )
                lease = ExecutionAssignmentLease(
                    lease_id=lease_id,
                    task_run_ref=run_ref,
                    step_run_ref=step_ref,
                    attempt=int(request["attempt"]),
                    owner=target_owner,
                    fence=fence,
                    expires_at=body.lease_expires_at,
                )
            authority_payload = {
                **payload,
                "checker": actor,
                "assignmentLease": None if lease is None else lease.model_dump(mode="json", by_alias=True),
            }
            content_hash = _hash(authority_payload)
            decision_id = _identifier("takeover-decision", scope, request_id, content_hash)
            row = conn.execute(
                """INSERT INTO aip_takeover_decision_revision
                   (org_id,project_id,decision_id,request_id,revision,decision,reason_code,
                    checker,assignment_lease,idempotency_key,request_hash,content_hash,created_at)
                   VALUES(%s,%s,%s,%s,1,%s,%s,%s,%s::jsonb,%s,%s,%s,%s) RETURNING *""",
                (*scope.key, decision_id, request_id, body.decision.value, body.reason_code, actor, _json(authority_payload["assignmentLease"]), idempotency_key, request_hash, content_hash, observed_at),
            ).fetchone()
            conn.commit()
            return self._decision(scope, row)

    def assert_fence(
        self,
        scope: TenantScope,
        body: AssertAssignmentFenceRequest,
        *,
        now: datetime | None = None,
    ) -> AssignmentFenceObservation:
        observed_at = now or datetime.now(UTC)
        with self._connect(scope) as conn:
            row = conn.execute(
                """SELECT head.*,run.version AS run_version
                   FROM aip_execution_assignment_head head
                   JOIN aip_task_run run ON run.org_id=head.org_id
                    AND run.project_id=head.project_id AND run.run_id=head.run_id
                   WHERE head.org_id=%s AND head.project_id=%s
                    AND head.step_run_id=%s AND head.attempt=%s""",
                (*scope.key, body.step_run_ref.resource_id, body.attempt),
            ).fetchone()
        blockers: list[AssignmentBlocker] = []
        lease: ExecutionAssignmentLease | None = None
        if row is None:
            blockers.append(AssignmentBlocker(code="ASSIGNMENT_MISSING", dependency=body.step_run_ref.resource_id, required_action="obtain an approved takeover assignment"))
        elif int(row["current_fence"]) != body.fence:
            blockers.append(AssignmentBlocker(code="ASSIGNMENT_FENCE_STALE", dependency=str(row["current_fence"]), required_action="stop the old owner and use the current fence"))
        elif AssigneeRef.model_validate(_load(row["owner"])) != body.owner:
            blockers.append(AssignmentBlocker(code="ASSIGNMENT_OWNER_DRIFTED", dependency=row["lease_id"], required_action="use the current exact owner"))
        elif row["lease_expires_at"] <= observed_at:
            blockers.append(AssignmentBlocker(code="ASSIGNMENT_LEASE_EXPIRED", dependency=row["lease_id"], required_action="obtain a new approved assignment lease"))
        else:
            lease = ExecutionAssignmentLease(
                lease_id=row["lease_id"],
                task_run_ref=RuntimeAuthorityRef(
                    resource_type="TaskRun",
                    resource_id=row["run_id"],
                    version=int(row["run_version"]),
                ),
                step_run_ref=body.step_run_ref,
                attempt=body.attempt,
                owner=body.owner,
                fence=body.fence,
                expires_at=row["lease_expires_at"],
            )
        return AssignmentFenceObservation(tenant=_tenant(scope), allowed=not blockers, lease=lease, blockers=blockers, evaluated_at=observed_at)

    def observe_run(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        now: datetime | None = None,
    ) -> ResponsibilityAssignmentObservation:
        observed_at = now or datetime.now(UTC)
        with self._connect(scope) as conn:
            run = conn.execute(
                """SELECT run_id,version FROM aip_task_run
                   WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*scope.key, run_id),
            ).fetchone()
            if run is None:
                raise ResponsibilityAssignmentNotFound("exact TaskRun not found")
            request_rows = conn.execute(
                """SELECT * FROM aip_takeover_request
                   WHERE org_id=%s AND project_id=%s
                    AND task_run_ref->>'resourceId'=%s
                   ORDER BY created_at,request_id""",
                (*scope.key, run_id),
            ).fetchall()
            decision_rows = conn.execute(
                """SELECT decision.* FROM aip_takeover_decision_revision decision
                   JOIN aip_takeover_request request
                    ON request.org_id=decision.org_id
                    AND request.project_id=decision.project_id
                    AND request.request_id=decision.request_id
                   WHERE decision.org_id=%s AND decision.project_id=%s
                    AND request.task_run_ref->>'resourceId'=%s
                   ORDER BY decision.created_at,decision.decision_id""",
                (*scope.key, run_id),
            ).fetchall()
            assignment_rows = conn.execute(
                """SELECT * FROM aip_execution_assignment_head
                   WHERE org_id=%s AND project_id=%s AND run_id=%s
                   ORDER BY step_run_id,attempt""",
                (*scope.key, run_id),
            ).fetchall()
        run_ref = RuntimeAuthorityRef(
            resource_type="TaskRun",
            resource_id=run["run_id"],
            version=int(run["version"]),
        )
        leases = [
            ExecutionAssignmentLease(
                lease_id=row["lease_id"],
                task_run_ref=run_ref,
                step_run_ref=RuntimeAuthorityRef(
                    resource_type="StepRun",
                    resource_id=row["step_run_id"],
                    version=int(row["attempt"]),
                ),
                attempt=int(row["attempt"]),
                owner=AssigneeRef.model_validate(_load(row["owner"])),
                fence=int(row["current_fence"]),
                expires_at=row["lease_expires_at"],
            )
            for row in assignment_rows
        ]
        return ResponsibilityAssignmentObservation(
            tenant=_tenant(scope),
            run_ref=run_ref,
            takeover_requests=[self._takeover_request(scope, row) for row in request_rows],
            takeover_decisions=[self._decision(scope, row) for row in decision_rows],
            assignment_leases=leases,
            evaluated_at=observed_at,
        )

    @staticmethod
    def _successor(scope: TenantScope, row: Any) -> ResponsibilitySuccessorReceipt:
        return ResponsibilitySuccessorReceipt(
            tenant=_tenant(scope), successor_id=row["successor_id"], task_id=row["task_id"],
            source_plan_ref=ExactRevisionRef.model_validate(_load(row["source_plan_ref"])),
            successor_plan_ref=ExactRevisionRef.model_validate(_load(row["successor_plan_ref"])),
            slot_id=row["slot_id"], source_assignee=AssigneeRef.model_validate(_load(row["source_assignee"])),
            target_assignee=AssigneeRef.model_validate(_load(row["target_assignee"])),
            resolution_receipt_id=row["resolution_receipt_id"], reason_code=row["reason_code"],
            actor=row["actor"], created_at=row["created_at"], content_hash=row["content_hash"],
        )

    @staticmethod
    def _takeover_request(scope: TenantScope, row: Any) -> TakeoverRequestReceipt:
        return TakeoverRequestReceipt(
            tenant=_tenant(scope), request_id=row["request_id"],
            task_run_ref=RuntimeAuthorityRef.model_validate(_load(row["task_run_ref"])),
            step_run_ref=RuntimeAuthorityRef.model_validate(_load(row["step_run_ref"])),
            attempt=int(row["attempt"]), source_owner=AssigneeRef.model_validate(_load(row["source_owner"])),
            target_owner=AssigneeRef.model_validate(_load(row["target_owner"])),
            resolution_receipt_id=row["resolution_receipt_id"], expected_fence=int(row["expected_fence"]),
            reason_code=row["reason_code"], safety_state=row["safety_state"], status=row["status"],
            blockers=[AssignmentBlocker.model_validate(item) for item in _load(row["blockers"])],
            maker=row["maker"], created_at=row["created_at"], content_hash=row["content_hash"],
        )

    @staticmethod
    def _decision(scope: TenantScope, row: Any) -> TakeoverDecisionReceipt:
        lease = _load(row["assignment_lease"])
        return TakeoverDecisionReceipt(
            tenant=_tenant(scope), decision_id=row["decision_id"], request_id=row["request_id"],
            revision=int(row["revision"]), decision=row["decision"], reason_code=row["reason_code"],
            checker=row["checker"], assignment_lease=None if lease is None else ExecutionAssignmentLease.model_validate(lease),
            created_at=row["created_at"], content_hash=row["content_hash"],
        )


__all__ = [
    "AipResponsibilityAssignmentStore",
    "ResponsibilityAssignmentBlocked",
    "ResponsibilityAssignmentConflict",
    "ResponsibilityAssignmentError",
    "ResponsibilityAssignmentNotFound",
]
