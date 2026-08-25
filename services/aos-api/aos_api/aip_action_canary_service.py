"""Canonical W5-07 Action Kill and bounded Canary control authority."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from aos_api.aip_action_canary_models import (
    CanaryPlanSnapshot,
    DecideCanaryPlanRequest,
    DecideKillPolicyRequest,
    EffectiveKillDecision,
    EvaluateKillPolicyRequest,
    KillDrillReceiptSnapshot,
    KillPolicyRevisionSnapshot,
    ProposeCanaryPlanRequest,
    ProposeKillPolicyRequest,
    SimulateKillDrillRequest,
)
from aos_api.aip_action_store import canonical_hash
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class AipActionCanaryError(Exception):
    code = "AIP_ACTION_CANARY_INVALID"
    status_code = 422


class AipActionCanaryConflict(AipActionCanaryError):
    code = "AIP_ACTION_CANARY_CONFLICT"
    status_code = 409


class AipActionCanaryForbidden(AipActionCanaryError):
    code = "AIP_ACTION_CANARY_FORBIDDEN"
    status_code = 403


class AipActionCanaryNotFound(AipActionCanaryError):
    code = "AIP_ACTION_CANARY_NOT_FOUND"
    status_code = 404


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _dump(value: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    return value.model_dump(mode="json", by_alias=True, exclude=exclude or set())


class AipActionCanaryService:
    @staticmethod
    def _require_policy_admin(principal: Principal) -> None:
        roles = {role.lower() for role in principal.roles}
        if not roles.intersection({"admin", "aip_policy_admin"}):
            raise AipActionCanaryForbidden("Action policy administrator role required")

    @staticmethod
    def _scope(principal: Principal) -> TenantScope:
        return TenantScope(principal.org_id, principal.project_id)

    def propose_kill_policy(
        self,
        principal: Principal,
        idempotency_key: str,
        body: ProposeKillPolicyRequest,
    ) -> KillPolicyRevisionSnapshot:
        self._require_policy_admin(principal)
        scope = self._scope(principal)
        request = _dump(body)
        request_hash = canonical_hash(request)
        content = _dump(body, exclude={"expected_head_version"})
        content_hash = canonical_hash(content)
        with connect(scope) as conn:
            self._lock(conn, scope, "kill-propose-idem", idempotency_key)
            self._lock(conn, scope, "kill-policy", body.policy_id)
            existing = self._command_receipt(conn, scope, "propose", idempotency_key)
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise AipActionCanaryConflict("idempotency key was used for another proposal")
                ref = existing["result_ref"]
                return self._policy_snapshot(conn, scope, ref["resourceId"], int(ref["revision"]))
            conn.execute(
                """INSERT INTO aip_action_kill_policy_head
                   (org_id,project_id,policy_id,version) VALUES (%s,%s,%s,0)
                   ON CONFLICT (org_id,project_id,policy_id) DO NOTHING""",
                (*scope.key, body.policy_id),
            )
            head = conn.execute(
                """SELECT * FROM aip_action_kill_policy_head
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s FOR UPDATE""",
                (*scope.key, body.policy_id),
            ).fetchone()
            if int(head["version"]) != body.expected_head_version:
                raise AipActionCanaryConflict("kill policy head version changed")
            duplicate = conn.execute(
                """SELECT revision FROM aip_action_kill_policy_revision
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s AND content_hash=%s""",
                (*scope.key, body.policy_id, content_hash),
            ).fetchone()
            if duplicate is not None:
                raise AipActionCanaryConflict("identical kill policy revision already exists")
            revision = int(
                conn.execute(
                    """SELECT COALESCE(MAX(revision),0)+1 AS revision
                       FROM aip_action_kill_policy_revision
                       WHERE org_id=%s AND project_id=%s AND policy_id=%s""",
                    (*scope.key, body.policy_id),
                ).fetchone()["revision"]
            )
            conn.execute(
                """INSERT INTO aip_action_kill_policy_revision
                   (org_id,project_id,policy_id,revision,content_hash,level,kill_enabled,
                    reason_code,account_binding_ref,adapter_revision_ref,capability_binding_ref,
                    action_type_id,valid_from,expires_at,proposed_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s)""",
                (
                    *scope.key,
                    body.policy_id,
                    revision,
                    content_hash,
                    body.level,
                    body.kill_enabled,
                    body.reason_code,
                    _json(content.get("accountBindingRef")) if content.get("accountBindingRef") else None,
                    _json(content.get("adapterRevisionRef")) if content.get("adapterRevisionRef") else None,
                    _json(content.get("capabilityBindingRef")) if content.get("capabilityBindingRef") else None,
                    body.action_type_id,
                    body.valid_from,
                    body.expires_at,
                    principal.subject,
                ),
            )
            self._insert_command_receipt(
                conn,
                scope,
                "propose",
                idempotency_key,
                request_hash,
                self._policy_ref(body.policy_id, revision, content_hash),
                principal.subject,
            )
            return self._policy_snapshot(conn, scope, body.policy_id, revision)

    def decide_kill_policy(
        self,
        principal: Principal,
        policy_id: str,
        revision: int,
        idempotency_key: str,
        body: DecideKillPolicyRequest,
    ) -> KillPolicyRevisionSnapshot:
        self._require_policy_admin(principal)
        scope = self._scope(principal)
        request_hash = canonical_hash({"policyId": policy_id, "revision": revision, **_dump(body)})
        command_type = "approve" if body.decision == "approved" else "reject"
        with connect(scope) as conn:
            self._lock(conn, scope, f"kill-{command_type}-idem", idempotency_key)
            self._lock(conn, scope, "kill-policy", policy_id)
            existing = self._command_receipt(conn, scope, command_type, idempotency_key)
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise AipActionCanaryConflict("idempotency key was used for another decision")
                return self._policy_snapshot(conn, scope, policy_id, revision)
            head = conn.execute(
                """SELECT * FROM aip_action_kill_policy_head
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s FOR UPDATE""",
                (*scope.key, policy_id),
            ).fetchone()
            row = conn.execute(
                """SELECT * FROM aip_action_kill_policy_revision
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s""",
                (*scope.key, policy_id, revision),
            ).fetchone()
            if head is None or row is None:
                raise AipActionCanaryNotFound("kill policy revision not found")
            if int(head["version"]) != body.expected_head_version:
                raise AipActionCanaryConflict("kill policy head version changed")
            if row["content_hash"] != body.expected_content_hash:
                raise AipActionCanaryConflict("kill policy content hash changed")
            if row["proposed_by"] == principal.subject:
                raise AipActionCanaryForbidden("maker cannot decide own kill policy")
            decided = conn.execute(
                """SELECT 1 FROM aip_action_kill_policy_approval_event
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s""",
                (*scope.key, policy_id, revision),
            ).fetchone()
            if decided is not None:
                raise AipActionCanaryConflict("kill policy revision already decided")
            event_id = f"kill-approval-{uuid.uuid4().hex}"
            conn.execute(
                """INSERT INTO aip_action_kill_policy_approval_event
                   (org_id,project_id,approval_event_id,policy_id,revision,content_hash,
                    decision,actor_id,reason,expected_head_version)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, event_id, policy_id, revision, row["content_hash"], body.decision,
                 principal.subject, body.reason, body.expected_head_version),
            )
            active_revision = revision if body.decision == "approved" else head["active_revision"]
            conn.execute(
                """UPDATE aip_action_kill_policy_head
                   SET active_revision=%s,version=version+1,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s AND version=%s""",
                (active_revision, *scope.key, policy_id, body.expected_head_version),
            )
            self._insert_command_receipt(
                conn, scope, command_type, idempotency_key, request_hash,
                self._policy_ref(policy_id, revision, row["content_hash"]), principal.subject,
            )
            return self._policy_snapshot(conn, scope, policy_id, revision)

    def evaluate(
        self, principal: Principal, body: EvaluateKillPolicyRequest
    ) -> EffectiveKillDecision:
        scope = self._scope(principal)
        with connect(scope) as conn:
            return self.evaluate_in_connection(conn, scope, body)

    @classmethod
    def evaluate_in_connection(
        cls, conn: Any, scope: TenantScope, body: EvaluateKillPolicyRequest
    ) -> EffectiveKillDecision:
        now = datetime.now(timezone.utc)
        rows = conn.execute(
            """SELECT r.* FROM aip_action_kill_policy_head h
               JOIN aip_action_kill_policy_revision r
                 ON r.org_id=h.org_id AND r.project_id=h.project_id
                AND r.policy_id=h.policy_id AND r.revision=h.active_revision
               WHERE h.org_id=%s AND h.project_id=%s AND r.kill_enabled=TRUE
                 AND r.valid_from<=%s AND (r.expires_at IS NULL OR r.expires_at>%s)
               ORDER BY r.policy_id,r.revision""",
            (*scope.key, now, now),
        ).fetchall()
        request = _dump(body)
        matches: list[Any] = []
        for row in rows:
            level = row["level"]
            applies = level in {"org", "project"}
            if level == "account":
                applies = row["account_binding_ref"] == request.get("accountBindingRef")
            elif level == "adapter":
                applies = row["adapter_revision_ref"] == request.get("adapterRevisionRef")
            elif level == "capability":
                applies = row["capability_binding_ref"] == request.get("capabilityBindingRef")
            elif level == "action_type":
                applies = row["action_type_id"] == body.action_type_id
            if applies:
                matches.append(row)
        reasons = [row["reason_code"] for row in matches]
        if os.getenv("AIP_ACTION_PLATFORM_KILL_SWITCH", "").strip().lower() in {"1", "true", "yes", "on"}:
            reasons.insert(0, "PLATFORM_ENVIRONMENT_KILL_SWITCH")
        return EffectiveKillDecision(
            blocked=bool(reasons),
            reasonCodes=list(dict.fromkeys(reasons)),
            policyRefs=[
                ExactRevisionRef.model_validate(cls._policy_ref(row["policy_id"], int(row["revision"]), row["content_hash"]))
                for row in matches
            ],
            evaluatedAt=now,
        )

    def propose_canary_plan(
        self, principal: Principal, idempotency_key: str, body: ProposeCanaryPlanRequest
    ) -> CanaryPlanSnapshot:
        self._require_policy_admin(principal)
        scope = self._scope(principal)
        content = _dump(body)
        request_hash = canonical_hash(content)
        content_hash = request_hash
        with connect(scope) as conn:
            self._lock(conn, scope, "canary-propose-idem", idempotency_key)
            self._lock(conn, scope, "canary-plan", body.plan_id)
            existing = conn.execute(
                """SELECT plan_id,revision,request_hash FROM aip_action_canary_plan_revision
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise AipActionCanaryConflict("idempotency key was used for another Canary plan")
                return self._canary_snapshot(conn, scope, existing["plan_id"], int(existing["revision"]))
            duplicate = conn.execute(
                """SELECT revision FROM aip_action_canary_plan_revision
                   WHERE org_id=%s AND project_id=%s AND plan_id=%s AND content_hash=%s""",
                (*scope.key, body.plan_id, content_hash),
            ).fetchone()
            if duplicate is not None:
                raise AipActionCanaryConflict("identical Canary plan revision already exists")
            revision = int(conn.execute(
                """SELECT COALESCE(MAX(revision),0)+1 AS revision
                   FROM aip_action_canary_plan_revision
                   WHERE org_id=%s AND project_id=%s AND plan_id=%s""",
                (*scope.key, body.plan_id),
            ).fetchone()["revision"])
            conn.execute(
                """INSERT INTO aip_action_canary_plan_revision
                   (org_id,project_id,plan_id,revision,content_hash,action_type_revision_ref,
                    capability_binding_ref,account_binding_ref,adapter_revision_ref,object_ref,
                    max_quantity,max_budget,currency,window_starts_at,window_ends_at,operator_id,
                    stop_conditions,idempotency_key,request_hash,proposed_by)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                           %s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)""",
                (*scope.key, body.plan_id, revision, content_hash,
                 _json(content["actionTypeRevisionRef"]), _json(content["capabilityBindingRef"]),
                 _json(content["accountBindingRef"]), _json(content["adapterRevisionRef"]),
                 _json(content["objectRef"]), body.max_quantity, body.max_budget, body.currency,
                 body.window_starts_at, body.window_ends_at, body.operator_id,
                 _json(body.stop_conditions), idempotency_key, request_hash, principal.subject),
            )
            return self._canary_snapshot(conn, scope, body.plan_id, revision)

    def decide_canary_plan(
        self, principal: Principal, plan_id: str, revision: int,
        idempotency_key: str, body: DecideCanaryPlanRequest,
    ) -> CanaryPlanSnapshot:
        self._require_policy_admin(principal)
        scope = self._scope(principal)
        request_hash = canonical_hash({"planId": plan_id, "revision": revision, **_dump(body)})
        with connect(scope) as conn:
            self._lock(conn, scope, "canary-decision-idem", idempotency_key)
            self._lock(conn, scope, "canary-plan", plan_id)
            existing = conn.execute(
                """SELECT plan_id,revision,request_hash FROM aip_action_canary_plan_approval_event
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise AipActionCanaryConflict("idempotency key was used for another Canary decision")
                return self._canary_snapshot(conn, scope, existing["plan_id"], int(existing["revision"]))
            row = conn.execute(
                """SELECT * FROM aip_action_canary_plan_revision
                   WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s""",
                (*scope.key, plan_id, revision),
            ).fetchone()
            if row is None:
                raise AipActionCanaryNotFound("Canary plan revision not found")
            if row["content_hash"] != body.expected_content_hash:
                raise AipActionCanaryConflict("Canary plan content hash changed")
            if row["proposed_by"] == principal.subject:
                raise AipActionCanaryForbidden("maker cannot decide own Canary plan")
            decided = conn.execute(
                """SELECT 1 FROM aip_action_canary_plan_approval_event
                   WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s""",
                (*scope.key, plan_id, revision),
            ).fetchone()
            if decided is not None:
                raise AipActionCanaryConflict("Canary plan revision already decided")
            conn.execute(
                """INSERT INTO aip_action_canary_plan_approval_event
                   (org_id,project_id,approval_event_id,plan_id,revision,content_hash,decision,
                    actor_id,reason,idempotency_key,request_hash)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, f"canary-approval-{uuid.uuid4().hex}", plan_id, revision,
                 row["content_hash"], body.decision, principal.subject, body.reason,
                 idempotency_key, request_hash),
            )
            return self._canary_snapshot(conn, scope, plan_id, revision)

    def simulate_kill_drill(
        self, principal: Principal, idempotency_key: str, body: SimulateKillDrillRequest
    ) -> KillDrillReceiptSnapshot:
        self._require_policy_admin(principal)
        scope = self._scope(principal)
        request_hash = canonical_hash(_dump(body))
        ref = body.policy_ref
        if ref.resource_type != "KillPolicyRevision":
            raise AipActionCanaryError("drill requires an exact KillPolicyRevision ref")
        with connect(scope) as conn:
            self._lock(conn, scope, "kill-drill-idem", idempotency_key)
            existing = conn.execute(
                """SELECT * FROM aip_action_kill_drill_receipt
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise AipActionCanaryConflict("idempotency key was used for another drill")
                return self._drill_snapshot(existing)
            policy = conn.execute(
                """SELECT r.* FROM aip_action_kill_policy_revision r
                   JOIN aip_action_kill_policy_head h ON h.org_id=r.org_id AND h.project_id=r.project_id
                    AND h.policy_id=r.policy_id AND h.active_revision=r.revision
                   WHERE r.org_id=%s AND r.project_id=%s AND r.policy_id=%s AND r.revision=%s""",
                (*scope.key, ref.resource_id, ref.revision),
            ).fetchone()
            now = datetime.now(timezone.utc)
            if (policy is None or policy["content_hash"] != ref.content_hash or not policy["kill_enabled"]
                    or policy["valid_from"] > now or (policy["expires_at"] and policy["expires_at"] <= now)):
                raise AipActionCanaryConflict("drill policy is not the exact active Kill revision")
            inflight: list[str] = []
            if body.inflight_attempt_ids:
                rows = conn.execute(
                    """SELECT attempt_id,status FROM aip_action_execution_attempt
                       WHERE org_id=%s AND project_id=%s AND attempt_id=ANY(%s)""",
                    (*scope.key, body.inflight_attempt_ids),
                ).fetchall()
                found = {row["attempt_id"]: row["status"] for row in rows}
                if set(found) != set(body.inflight_attempt_ids):
                    raise AipActionCanaryNotFound("in-flight attempt was not found in tenant scope")
                if any(status not in {"dispatch_claimed", "accepted", "unknown"} for status in found.values()):
                    raise AipActionCanaryConflict("drill accepts only reconcile-required in-flight attempts")
                inflight = list(body.inflight_attempt_ids)
            invariants = {
                "newDispatchAttemptRowsCreated": False,
                "inflightClaimedCancelled": False,
                "reconcileRequiredCount": len(inflight),
                "externalProviderCalled": False,
                "reservationOrUsageMutated": False,
            }
            receipt_id = f"kill-drill-{uuid.uuid4().hex}"
            conn.execute(
                """INSERT INTO aip_action_kill_drill_receipt
                   (org_id,project_id,receipt_id,policy_ref,simulation_only,
                    blocked_new_dispatches,inflight_reconcile_attempts,invariants,result,
                    idempotency_key,request_hash,actor_id)
                   VALUES (%s,%s,%s,%s::jsonb,TRUE,%s::jsonb,%s::jsonb,%s::jsonb,'passed',%s,%s,%s)""",
                (*scope.key, receipt_id, _json(_dump(ref)), _json(body.synthetic_new_dispatch_ids),
                 _json(inflight), _json(invariants), idempotency_key, request_hash, principal.subject),
            )
            row = conn.execute(
                """SELECT * FROM aip_action_kill_drill_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                (*scope.key, receipt_id),
            ).fetchone()
            return self._drill_snapshot(row)

    @staticmethod
    def _lock(conn: Any, scope: TenantScope, family: str, key: str) -> None:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"w5-07:{scope.org_id}:{scope.project_id}:{family}:{key}",),
        )

    @staticmethod
    def _command_receipt(conn: Any, scope: TenantScope, command: str, key: str) -> Any | None:
        return conn.execute(
            """SELECT * FROM aip_action_kill_policy_command_receipt
               WHERE org_id=%s AND project_id=%s AND command_type=%s AND idempotency_key=%s""",
            (*scope.key, command, key),
        ).fetchone()

    @staticmethod
    def _insert_command_receipt(
        conn: Any, scope: TenantScope, command: str, key: str, request_hash: str,
        result_ref: dict[str, Any], actor_id: str,
    ) -> None:
        conn.execute(
            """INSERT INTO aip_action_kill_policy_command_receipt
               (org_id,project_id,receipt_id,command_type,idempotency_key,request_hash,result_ref,actor_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
            (*scope.key, f"kill-command-{uuid.uuid4().hex}", command, key, request_hash,
             _json(result_ref), actor_id),
        )

    @staticmethod
    def _policy_ref(policy_id: str, revision: int, content_hash: str) -> dict[str, Any]:
        return {"resourceType": "KillPolicyRevision", "resourceId": policy_id,
                "revision": revision, "contentHash": content_hash}

    @staticmethod
    def _policy_snapshot(conn: Any, scope: TenantScope, policy_id: str, revision: int) -> KillPolicyRevisionSnapshot:
        row = conn.execute(
            """SELECT r.*,h.version AS head_version,h.active_revision,a.decision
               FROM aip_action_kill_policy_revision r
               JOIN aip_action_kill_policy_head h ON h.org_id=r.org_id AND h.project_id=r.project_id
                AND h.policy_id=r.policy_id
               LEFT JOIN aip_action_kill_policy_approval_event a ON a.org_id=r.org_id
                AND a.project_id=r.project_id AND a.policy_id=r.policy_id AND a.revision=r.revision
               WHERE r.org_id=%s AND r.project_id=%s AND r.policy_id=%s AND r.revision=%s""",
            (*scope.key, policy_id, revision),
        ).fetchone()
        if row is None:
            raise AipActionCanaryNotFound("kill policy revision not found")
        return KillPolicyRevisionSnapshot(
            policyId=row["policy_id"], revision=row["revision"], headVersion=row["head_version"],
            contentHash=row["content_hash"], level=row["level"], killEnabled=row["kill_enabled"],
            reasonCode=row["reason_code"], accountBindingRef=row["account_binding_ref"],
            adapterRevisionRef=row["adapter_revision_ref"], capabilityBindingRef=row["capability_binding_ref"],
            actionTypeId=row["action_type_id"], validFrom=row["valid_from"], expiresAt=row["expires_at"],
            proposedBy=row["proposed_by"], active=row["active_revision"] == row["revision"],
            decision=row["decision"], createdAt=row["created_at"],
        )

    @staticmethod
    def _canary_snapshot(conn: Any, scope: TenantScope, plan_id: str, revision: int) -> CanaryPlanSnapshot:
        row = conn.execute(
            """SELECT p.*,a.decision FROM aip_action_canary_plan_revision p
               LEFT JOIN aip_action_canary_plan_approval_event a ON a.org_id=p.org_id
                AND a.project_id=p.project_id AND a.plan_id=p.plan_id AND a.revision=p.revision
               WHERE p.org_id=%s AND p.project_id=%s AND p.plan_id=%s AND p.revision=%s""",
            (*scope.key, plan_id, revision),
        ).fetchone()
        if row is None:
            raise AipActionCanaryNotFound("Canary plan revision not found")
        return CanaryPlanSnapshot(
            planId=row["plan_id"], revision=row["revision"], contentHash=row["content_hash"],
            status=row["decision"] or "awaiting_approval",
            exactScope={"actionTypeRevisionRef": row["action_type_revision_ref"],
                        "capabilityBindingRef": row["capability_binding_ref"],
                        "accountBindingRef": row["account_binding_ref"],
                        "adapterRevisionRef": row["adapter_revision_ref"],
                        "objectRef": row["object_ref"]},
            maxQuantity=row["max_quantity"], maxBudget=row["max_budget"], currency=row["currency"],
            windowStartsAt=row["window_starts_at"], windowEndsAt=row["window_ends_at"],
            operatorId=row["operator_id"], stopConditions=row["stop_conditions"],
            proposedBy=row["proposed_by"], createdAt=row["created_at"],
        )

    @staticmethod
    def _drill_snapshot(row: Any) -> KillDrillReceiptSnapshot:
        return KillDrillReceiptSnapshot(
            receiptId=row["receipt_id"], policyRef=row["policy_ref"], simulationOnly=True,
            blockedNewDispatches=row["blocked_new_dispatches"],
            inflightReconcileAttempts=row["inflight_reconcile_attempts"], invariants=row["invariants"],
            result=row["result"], actorId=row["actor_id"], createdAt=row["created_at"],
        )
