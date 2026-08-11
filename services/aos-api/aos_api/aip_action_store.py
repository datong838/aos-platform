"""PostgreSQL authority for AIP Action Proposal, Draft and Approval."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any

from aos_api.aip_action_models import (
    ActionDraftBundle,
    ActionProposalSnapshot,
    ActionProposalTimeline,
    CreateActionProposalRequest,
    DecideActionProposalRequest,
    actor,
)
from aos_api.aip_action_policy import RiskDecision
from aos_api.aip_contracts import (
    ActionProposalStatus,
    ActionRiskLevel,
    ActionTypeRevisionRef,
    ApprovalDecision,
    ApprovalEvent,
    DraftSnapshot,
    ResourceRef,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipActionStoreError(RuntimeError):
    code = "AIP_ACTION_STORE_ERROR"


class AipActionNotFound(AipActionStoreError):
    code = "AIP_RESOURCE_NOT_FOUND"


class AipActionConflict(AipActionStoreError):
    code = "AIP_VERSION_CONFLICT"


class AipActionIdempotencyConflict(AipActionStoreError):
    code = "AIP_IDEMPOTENCY_CONFLICT"


class AipActionTransitionBlocked(AipActionStoreError):
    code = "AIP_INVALID_TRANSITION"


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


class AipActionStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def action_type_snapshot(self, scope: TenantScope, action_type_id: str) -> dict[str, Any]:
        with self._connect(scope) as conn:
            row = conn.execute(
                "SELECT id,name,object_type,parameters,required_markings,submission_criteria FROM meta_action_type WHERE id=%s",
                (action_type_id,),
            ).fetchone()
        if row is None:
            raise AipActionNotFound("action type not found")
        snapshot = {
            "id": row["id"], "name": row["name"], "objectType": row["object_type"],
            "parameters": row["parameters"], "requiredMarkings": row["required_markings"],
            "submissionCriteria": row["submission_criteria"],
        }
        snapshot["revisionHash"] = canonical_hash(snapshot)
        return snapshot

    def create_proposal(
        self,
        scope: TenantScope,
        actor_id: str,
        idempotency_key: str,
        body: CreateActionProposalRequest,
        action_snapshot: dict[str, Any],
        risk: RiskDecision,
    ) -> ActionDraftBundle:
        expires_at = body.effective_expiry()
        if expires_at <= datetime.now(timezone.utc):
            raise AipActionTransitionBlocked("proposal expiry must be in the future")
        stable = {
            "tenantScope": {"orgId": scope.org_id, "projectId": scope.project_id},
            "createdBy": actor_id,
            "actionType": action_snapshot,
            "taskId": body.task_id,
            "runId": body.run_id,
            "objectRef": body.object_ref.model_dump(mode="json", by_alias=True) if body.object_ref else None,
            "purpose": body.purpose,
            "riskLevel": risk.level.value,
            "policy": {"floor": risk.floor.value, "reasons": list(risk.reasons), **risk.approval_policy},
            "payload": body.payload,
            "diff": body.diff,
            "evidenceRefs": [item.model_dump(mode="json", by_alias=True) for item in body.evidence_refs],
            "expiresAt": expires_at.isoformat(),
        }
        policy = stable["policy"]
        proposal_hash = canonical_hash(stable)
        request_hash = canonical_hash({
            "request": body.model_dump(mode="json", by_alias=True),
            "actionTypeRevisionHash": action_snapshot["revisionHash"],
            "classifiedRiskLevel": risk.level.value,
            "policy": policy,
        })
        proposal_id = f"proposal-{uuid.uuid4().hex[:20]}"
        draft_id = f"action-draft-{uuid.uuid4().hex[:20]}"
        event_id = f"action-event-{uuid.uuid4().hex[:20]}"
        with self._connect(scope) as conn:
            self._idempotency_lock(conn, scope, "proposal", idempotency_key)
            replay = conn.execute(
                "SELECT proposal_id,request_hash FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                (*scope.key, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise AipActionIdempotencyConflict("idempotency key reused for different proposal")
                return self._bundle(conn, scope, replay["proposal_id"])
            self._validate_task_run(conn, scope, body.task_id, body.run_id)
            conn.execute(
                """INSERT INTO aip_action_proposal (
                   org_id,project_id,proposal_id,action_type_id,action_type_revision_hash,
                   action_type_snapshot,task_id,run_id,object_ref,purpose,client_risk_hint,risk_level,
                   policy_snapshot,payload,diff,evidence_refs,proposal_hash,status,expires_at,
                   idempotency_key,request_hash,version,created_by,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,
                           %s::jsonb,%s::jsonb,%s::jsonb,%s,'drafted',%s,%s,%s,1,%s,NOW(),NOW())""",
                (*scope.key, proposal_id, body.action_type_id, action_snapshot["revisionHash"],
                 self._json(action_snapshot), body.task_id, body.run_id, self._json(stable["objectRef"]),
                 body.purpose, body.risk_hint.value if body.risk_hint else None, risk.level.value,
                 self._json(policy), self._json(body.payload), self._json(body.diff),
                 self._json(stable["evidenceRefs"]), proposal_hash, expires_at, idempotency_key,
                 request_hash, actor_id),
            )
            conn.execute(
                """INSERT INTO aip_action_draft (
                   org_id,project_id,draft_id,proposal_id,proposal_version,proposal_hash,snapshot,diff,
                   evidence_refs,approval_policy,status,created_by,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                           'awaiting_approval',%s,NOW(),NOW())""",
                (*scope.key, draft_id, proposal_id, proposal_hash, self._json(stable),
                 self._json(body.diff), self._json(stable["evidenceRefs"]), self._json(policy), actor_id),
            )
            conn.execute(
                """INSERT INTO aip_action_event
                   (org_id,project_id,event_id,proposal_id,event_type,actor_id,proposal_version,proposal_hash,payload)
                   VALUES (%s,%s,%s,%s,'drafted',%s,1,%s,%s::jsonb)""",
                (*scope.key, event_id, proposal_id, actor_id, proposal_hash, self._json({"draftId": draft_id})),
            )
            conn.commit()
            return self._bundle(conn, scope, proposal_id)

    def list_proposals(self, scope: TenantScope, limit: int = 100) -> list[ActionDraftBundle]:
        with self._connect(scope) as conn:
            rows = conn.execute(
                "SELECT proposal_id FROM aip_action_proposal WHERE org_id=%s AND project_id=%s ORDER BY updated_at DESC,proposal_id DESC LIMIT %s",
                (*scope.key, limit),
            ).fetchall()
            return [self._bundle(conn, scope, row["proposal_id"]) for row in rows]

    def get_proposal(self, scope: TenantScope, proposal_id: str) -> ActionDraftBundle:
        with self._connect(scope) as conn:
            return self._bundle(conn, scope, proposal_id)

    def decide(
        self,
        scope: TenantScope,
        actor_id: str,
        proposal_id: str,
        idempotency_key: str,
        body: DecideActionProposalRequest,
    ) -> ActionDraftBundle:
        request_hash = canonical_hash(body.model_dump(mode="json", by_alias=True))
        with self._connect(scope) as conn:
            self._idempotency_lock(conn, scope, "approval", idempotency_key)
            row = conn.execute(
                "SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR UPDATE",
                (*scope.key, proposal_id),
            ).fetchone()
            if row is None:
                raise AipActionNotFound("proposal not found in scope")
            replay = conn.execute(
                "SELECT proposal_id,request_hash FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                (*scope.key, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash or replay["proposal_id"] != proposal_id:
                    raise AipActionIdempotencyConflict("idempotency key reused for different approval")
                return self._bundle(conn, scope, proposal_id)
            if row["created_by"] == actor_id:
                raise AipActionTransitionBlocked("maker cannot approve or reject own proposal")
            if row["status"] not in {"drafted", "approved"}:
                raise AipActionTransitionBlocked(f"proposal is not reviewable while {row['status']}")
            if row["expires_at"] <= datetime.now(timezone.utc):
                conn.execute("UPDATE aip_action_proposal SET status='expired',version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, proposal_id))
                conn.execute("UPDATE aip_action_draft SET status='expired',updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, proposal_id))
                conn.commit()
                raise AipActionTransitionBlocked("proposal expired")
            if int(row["version"]) != body.expected_proposal_version or row["proposal_hash"] != body.expected_proposal_hash:
                raise AipActionConflict("proposal revision or hash changed before decision")
            if conn.execute(
                "SELECT 1 FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND actor_id=%s AND decision='approved'",
                (*scope.key, proposal_id, actor_id),
            ).fetchone():
                raise AipActionTransitionBlocked("actor already approved this proposal")
            event_id = f"approval-{uuid.uuid4().hex[:20]}"
            conn.execute(
                """INSERT INTO aip_action_approval_event
                   (org_id,project_id,approval_event_id,proposal_id,proposal_version,proposal_hash,
                    decision,actor_id,reason,expires_at,idempotency_key,request_hash)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, event_id, proposal_id, row["version"], row["proposal_hash"],
                 body.decision.value, actor_id, body.reason, body.approval_expires_at,
                 idempotency_key, request_hash),
            )
            next_status = "rejected"
            if body.decision is ApprovalDecision.APPROVED:
                approvals = int(conn.execute(
                    "SELECT COUNT(*) AS n FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND decision='approved'",
                    (*scope.key, proposal_id),
                ).fetchone()["n"])
                minimum = int((row["policy_snapshot"] or {}).get("minimumApprovals", 1))
                next_status = "approved" if approvals >= minimum else "drafted"
            conn.execute(
                "UPDATE aip_action_proposal SET status=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND version=%s",
                (next_status, *scope.key, proposal_id, row["version"]),
            )
            conn.execute(
                "UPDATE aip_action_draft SET status=%s,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                ("awaiting_approval" if next_status == "drafted" else next_status, *scope.key, proposal_id),
            )
            conn.execute(
                """INSERT INTO aip_action_event
                   (org_id,project_id,event_id,proposal_id,event_type,actor_id,proposal_version,proposal_hash,payload)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (*scope.key, f"action-event-{uuid.uuid4().hex[:20]}", proposal_id,
                 body.decision.value, actor_id, int(row["version"]) + 1, row["proposal_hash"],
                 self._json({"reason": body.reason, "status": next_status})),
            )
            conn.commit()
            return self._bundle(conn, scope, proposal_id)

    def timeline(self, scope: TenantScope, proposal_id: str) -> ActionProposalTimeline:
        with self._connect(scope) as conn:
            bundle = self._bundle(conn, scope, proposal_id)
            rows = conn.execute(
                "SELECT event_id,event_type,actor_id,proposal_version,proposal_hash,payload,created_at FROM aip_action_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s ORDER BY created_at,event_id",
                (*scope.key, proposal_id),
            ).fetchall()
        return ActionProposalTimeline(bundle=bundle, events=[dict(row) for row in rows])

    def _bundle(self, conn: Any, scope: TenantScope, proposal_id: str) -> ActionDraftBundle:
        row = conn.execute("SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, proposal_id)).fetchone()
        if row is None:
            raise AipActionNotFound("proposal not found in scope")
        draft = conn.execute("SELECT * FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, proposal_id)).fetchone()
        approvals = conn.execute("SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s ORDER BY created_at,approval_event_id", (*scope.key, proposal_id)).fetchall()
        action = row["action_type_snapshot"]
        proposal = ActionProposalSnapshot(
            id=row["proposal_id"],
            action_type=ActionTypeRevisionRef(action_type_id=row["action_type_id"], revision_hash=row["action_type_revision_hash"], object_type=action["objectType"]),
            task_id=row["task_id"], run_id=row["run_id"],
            object_ref=ResourceRef.model_validate(row["object_ref"]) if row["object_ref"] else None,
            purpose=row["purpose"], risk_level=ActionRiskLevel(row["risk_level"]),
            client_risk_hint=ActionRiskLevel(row["client_risk_hint"]) if row["client_risk_hint"] else None,
            policy_snapshot=row["policy_snapshot"], payload=row["payload"], diff=row["diff"],
            evidence_refs=[ResourceRef.model_validate(item) for item in row["evidence_refs"]],
            proposal_hash=row["proposal_hash"], status=ActionProposalStatus(row["status"]),
            expires_at=row["expires_at"], version=row["version"], created_by=actor(row["created_by"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
        draft_model = DraftSnapshot(
            id=draft["draft_id"], proposal_id=proposal_id, proposal_version=draft["proposal_version"],
            proposal_hash=draft["proposal_hash"], diff=draft["diff"],
            evidence_refs=[ResourceRef.model_validate(item) for item in draft["evidence_refs"]],
            status=draft["status"], created_at=draft["created_at"],
        )
        approval_models = [ApprovalEvent(
            id=item["approval_event_id"], proposal_id=proposal_id,
            proposal_version=item["proposal_version"], proposal_hash=item["proposal_hash"],
            decision=ApprovalDecision(item["decision"]), actor=actor(item["actor_id"]),
            reason=item["reason"], expires_at=item["expires_at"], created_at=item["created_at"],
        ) for item in approvals]
        return ActionDraftBundle(proposal=proposal, draft=draft_model, approvals=approval_models)

    @staticmethod
    def _validate_task_run(conn: Any, scope: TenantScope, task_id: str | None, run_id: str | None) -> None:
        if task_id and conn.execute("SELECT 1 FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s", (*scope.key, task_id)).fetchone() is None:
            raise AipActionNotFound("task not found in scope")
        if run_id:
            row = conn.execute("SELECT task_id FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s", (*scope.key, run_id)).fetchone()
            if row is None or row["task_id"] != task_id:
                raise AipActionNotFound("run not found for task in scope")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    def _connect(self, scope: TenantScope):
        try:
            return self._connect_factory(scope)
        except TypeError:
            return self._connect_factory()

    @staticmethod
    def _idempotency_lock(
        conn: Any,
        scope: TenantScope,
        namespace: str,
        idempotency_key: str,
    ) -> None:
        lock_key = f"aip-action:{namespace}:{scope.org_id}:{scope.project_id}:{idempotency_key}"
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))
