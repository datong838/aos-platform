"""AIP-3B single-attempt execution, immutable Receipt and reconciliation."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from aos_api.aip_action_adapters import ActionAdapterRegistry, AdapterOutcome
from aos_api.aip_action_models import (
    AcquireExecutionLeaseRequest,
    ActionExecutionLeaseSnapshot,
    ActionExecutionView,
    ActionReceiptSnapshot,
    CreateCompensationRequest,
    CreateActionProposalRequest,
)
from aos_api.aip_action_store import (
    AipActionConflict,
    AipActionIdempotencyConflict,
    AipActionNotFound,
    AipActionStore,
    AipActionStoreError,
    AipActionTransitionBlocked,
    canonical_hash,
    W5_EXTERNAL_ACTION_FAMILIES,
)
from aos_api.aip_contracts import ActionReceiptStatus, ResourceRef
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.marking import ensure_field_writes, ensure_markings
from aos_api.tenant_scope import TenantScope


class AipActionBudgetExceeded(AipActionStoreError):
    code = "AIP_BUDGET_EXCEEDED"


class AipActionForbidden(AipActionStoreError):
    code = "AIP_SCOPE_FORBIDDEN"


class AipActionDependencyUnavailable(AipActionStoreError):
    code = "AIP_DEPENDENCY_UNAVAILABLE"


class AipActionExecutionService:
    def __init__(self, store: AipActionStore, adapters: ActionAdapterRegistry) -> None:
        self._store = store
        self._adapters = adapters

    @staticmethod
    def _require_executor(principal: Principal) -> None:
        if not {role.lower() for role in principal.roles}.intersection({"admin", "executor", "aip_executor"}):
            raise AipActionForbidden("Action executor role required")

    def acquire_lease(
        self,
        principal: Principal,
        proposal_id: str,
        idempotency_key: str,
        body: AcquireExecutionLeaseRequest,
    ) -> ActionExecutionView:
        self._require_executor(principal)
        scope = TenantScope(principal.org_id, principal.project_id)
        with connect(scope) as conn:
            self._store._idempotency_lock(conn, scope, "lease", idempotency_key)
            proposal = conn.execute(
                "SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR UPDATE",
                (*scope.key, proposal_id),
            ).fetchone()
            if proposal is None:
                raise AipActionNotFound("proposal not found in scope")
            existing = conn.execute(
                "SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND attempt=1",
                (*scope.key, proposal_id),
            ).fetchone()
            if existing is not None:
                if existing["proposal_hash"] != body.expected_proposal_hash:
                    raise AipActionIdempotencyConflict("proposal already leased for another hash")
                if existing["owner_id"] != principal.subject:
                    raise AipActionTransitionBlocked("proposal lease belongs to another executor")
                return self._view(scope, proposal_id, existing)
            now = datetime.now(timezone.utc)
            if proposal["status"] != "approved":
                raise AipActionTransitionBlocked(f"proposal is not executable while {proposal['status']}")
            if proposal["expires_at"] <= now:
                raise AipActionTransitionBlocked("proposal expired before execution")
            if int(proposal["version"]) != body.expected_proposal_version or proposal["proposal_hash"] != body.expected_proposal_hash:
                raise AipActionConflict("proposal revision or hash changed before lease")
            self._store.assert_bound_impact_preview_current(conn, scope, proposal)
            policy = proposal["policy_snapshot"] or {}
            expected_policy_hash = canonical_hash(policy)
            if proposal["approval_policy_hash"] not in {None, expected_policy_hash}:
                raise AipActionTransitionBlocked("APPROVAL_POLICY_HASH_DRIFTED")
            if proposal["source_draft_id"] is not None and bool(policy.get("draftOnly")):
                raise AipActionTransitionBlocked("ACTION_DRAFT_ONLY_POLICY")
            if proposal["created_by"] == principal.subject:
                raise AipActionTransitionBlocked("maker cannot execute own proposal")
            approvals = conn.execute(
                """SELECT approval_event_id,actor_id,expires_at,proposal_hash,
                          action_binding_hash,approval_policy_hash,slot_id,
                          eligibility_snapshot_hash
                   FROM aip_action_approval_event
                   WHERE org_id=%s AND project_id=%s AND proposal_id=%s
                     AND decision='approved' ORDER BY created_at,approval_event_id""",
                (*scope.key, proposal_id),
            ).fetchall()
            minimum = int(policy.get("minimumApprovals", 1))
            valid = [row for row in approvals if row["expires_at"] is None or row["expires_at"] > now]
            if len(valid) < minimum:
                raise AipActionTransitionBlocked("valid approval quorum is no longer satisfied")
            if any(
                row["proposal_hash"] != proposal["proposal_hash"]
                or row["approval_policy_hash"] not in {None, expected_policy_hash}
                or row["action_binding_hash"] != proposal["action_binding_hash"]
                for row in valid
            ):
                raise AipActionTransitionBlocked("APPROVAL_SET_BINDING_DRIFTED")
            if principal.subject in {row["actor_id"] for row in valid}:
                raise AipActionTransitionBlocked("approver cannot execute the same proposal")
            if proposal["risk_level"] == "R4" or not bool(policy.get("executionAllowed", True)):
                raise AipActionTransitionBlocked("R4 execution is disabled without specialized policy")
            approval_set_hash = canonical_hash(
                [
                    {
                        "approvalEventId": row["approval_event_id"],
                        "actorId": row["actor_id"],
                        "slotId": row["slot_id"],
                        "eligibilitySnapshotHash": row["eligibility_snapshot_hash"],
                        "expiresAt": row["expires_at"],
                    }
                    for row in valid
                ]
            )
            reservation_ref = None
            if proposal["action_type_id"] in W5_EXTERNAL_ACTION_FAMILIES:
                raise AipActionTransitionBlocked(
                    "ACTION_BUDGET_RESERVATION_AUTHORITY_UNAVAILABLE"
                )
            current = self._store.action_type_snapshot(scope, proposal["action_type_id"])
            if current["revisionHash"] != proposal["action_type_revision_hash"]:
                raise AipActionConflict("Action Type revision changed before execution")
            ensure_markings(principal, current.get("requiredMarkings") or [], conn=conn)
            props_row = conn.execute(
                "SELECT properties FROM meta_object_type WHERE id=%s",
                (current["objectType"],),
            ).fetchone()
            if props_row and isinstance(props_row["properties"], list):
                ensure_field_writes(
                    principal,
                    proposal["payload"] or {},
                    props_row["properties"],
                    conn=conn,
                )
            self._apply_guardrails(conn, scope, proposal["action_type_id"])
            lease_id = f"lease-{uuid.uuid4().hex[:20]}"
            expires_at = now + timedelta(seconds=body.lease_seconds)
            conn.execute(
                """INSERT INTO aip_action_execution_lease
                   (org_id,project_id,lease_id,proposal_id,proposal_hash,attempt,status,
                    owner_id,expires_at,action_binding_hash,approval_set_hash,reservation_ref,
                    idempotency_key)
                   VALUES (%s,%s,%s,%s,%s,1,'active',%s,%s,%s,%s,%s::jsonb,%s)""",
                (
                    *scope.key,
                    lease_id,
                    proposal_id,
                    proposal["proposal_hash"],
                    principal.subject,
                    expires_at,
                    proposal["action_binding_hash"],
                    approval_set_hash,
                    (
                        self._store._json(reservation_ref)
                        if reservation_ref is not None
                        else None
                    ),
                    idempotency_key,
                ),
            )
            conn.execute(
                "UPDATE aip_action_proposal SET status='leased',version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                (*scope.key, proposal_id),
            )
            self._event(conn, scope, proposal, "leased", principal.subject, {"leaseId": lease_id})
            conn.commit()
        return self._view(
            scope,
            proposal_id,
            {
                "lease_id": lease_id,
                "proposal_id": proposal_id,
                "proposal_hash": proposal["proposal_hash"],
                "attempt": 1,
                "expires_at": expires_at,
                "created_at": now,
                "action_binding_hash": proposal["action_binding_hash"],
                "approval_set_hash": approval_set_hash,
                "reservation_ref": reservation_ref,
            },
        )

    def execute(self, principal: Principal, lease_id: str, expected_hash: str) -> ActionExecutionView:
        self._require_executor(principal)
        scope = TenantScope(principal.org_id, principal.project_id)
        with connect(scope) as conn:
            self._store._idempotency_lock(conn, scope, "execute", lease_id)
            lease = conn.execute(
                "SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s FOR UPDATE",
                (*scope.key, lease_id),
            ).fetchone()
            if lease is None:
                raise AipActionNotFound("execution lease not found in scope")
            previous = conn.execute(
                "SELECT receipt_id FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND lease_id=%s AND receipt_kind='initial'",
                (*scope.key, lease_id),
            ).fetchone()
            if previous is not None:
                return self._view(scope, lease["proposal_id"], lease)
            if lease["owner_id"] != principal.subject:
                raise AipActionTransitionBlocked("execution lease belongs to another executor")
            if lease["status"] != "active" or lease["expires_at"] <= datetime.now(timezone.utc):
                raise AipActionTransitionBlocked("execution lease is not active")
            if lease["proposal_hash"] != expected_hash:
                raise AipActionConflict("execution hash does not match lease")
            proposal = conn.execute(
                "SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR UPDATE",
                (*scope.key, lease["proposal_id"]),
            ).fetchone()
            self._store.assert_bound_impact_preview_current(conn, scope, proposal)
            adapter = self._adapters.get(proposal["action_type_id"])
            if adapter is None:
                raise AipActionDependencyUnavailable("Action adapter is not registered")
            self._assert_no_kill_switch(conn, scope, proposal["action_type_id"])
            conn.execute(
                "UPDATE aip_action_execution_lease SET status='consumed',consumed_at=NOW() WHERE org_id=%s AND project_id=%s AND lease_id=%s",
                (*scope.key, lease_id),
            )
            conn.execute(
                "UPDATE aip_action_proposal SET status='executing',version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                (*scope.key, proposal["proposal_id"]),
            )
            conn.commit()

        try:
            outcome = adapter.execute(
                payload=dict(proposal["payload"] or {}),
                idempotency_key=f"{proposal['idempotency_key']}:{proposal['proposal_hash']}",
            )
        except (TimeoutError, ConnectionError) as exc:
            outcome = AdapterOutcome(
                "unknown",
                getattr(exc, "provider_request_id", None),
                {"errorType": type(exc).__name__},
            )
        except Exception as exc:  # fail closed; no automatic retry
            outcome = AdapterOutcome("failed", payload={"errorType": type(exc).__name__})
        if outcome.status not in {"accepted", "applied", "failed", "unknown"}:
            outcome = AdapterOutcome("unknown", outcome.provider_request_id, {"invalidAdapterStatus": outcome.status})
        self._append_initial_receipt(scope, proposal, lease_id, outcome)
        return self._view(scope, proposal["proposal_id"], lease)

    def reconcile(self, principal: Principal, receipt_id: str, reason: str) -> ActionExecutionView:
        self._require_executor(principal)
        scope = TenantScope(principal.org_id, principal.project_id)
        with connect(scope) as conn:
            self._store._idempotency_lock(conn, scope, "reconcile", receipt_id)
            receipt = conn.execute(
                "SELECT * FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s FOR UPDATE",
                (*scope.key, receipt_id),
            ).fetchone()
            if receipt is None:
                raise AipActionNotFound("receipt not found in scope")
            if receipt["status"] != "unknown" or receipt["receipt_kind"] != "initial":
                raise AipActionTransitionBlocked("only an initial unknown receipt can be reconciled")
            existing = conn.execute(
                "SELECT receipt_id FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND supersedes_receipt_id=%s",
                (*scope.key, receipt_id),
            ).fetchone()
            if existing is not None:
                lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, receipt["lease_id"])).fetchone()
                return self._view(scope, receipt["proposal_id"], lease)
            proposal = conn.execute("SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, receipt["proposal_id"])).fetchone()
        if not receipt["provider_request_id"]:
            raise AipActionDependencyUnavailable("provider request id unavailable for reconciliation")
        adapter = self._adapters.get(proposal["action_type_id"])
        if adapter is None:
            raise AipActionDependencyUnavailable("adapter unavailable for reconciliation")
        try:
            result = adapter.reconcile(provider_request_id=receipt["provider_request_id"], request_fingerprint=receipt["request_fingerprint"])
        except Exception as exc:
            raise AipActionDependencyUnavailable("authorized provider reread failed") from exc
        if result.status not in {"applied", "failed"}:
            raise AipActionDependencyUnavailable("provider reread did not reach a terminal result")
        with connect(scope) as conn:
            new_id = f"receipt-{uuid.uuid4().hex[:20]}"
            conn.execute(
                """INSERT INTO aip_action_receipt
                   (org_id,project_id,receipt_id,proposal_id,lease_id,status,provider_request_id,
                    request_fingerprint,evidence_refs,payload,receipt_kind,supersedes_receipt_id)
                   VALUES (%s,%s,%s,%s,%s,'reconciled',%s,%s,'[]'::jsonb,%s::jsonb,'reconcile',%s)""",
                (*scope.key, new_id, receipt["proposal_id"], receipt["lease_id"], receipt["provider_request_id"], receipt["request_fingerprint"], self._store._json({"resolvedStatus": result.status, "provider": result.payload, "reason": reason}), receipt_id),
            )
            conn.execute("UPDATE aip_action_proposal SET status='reconciled',version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, receipt["proposal_id"]))
            conn.commit()
            lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, receipt["lease_id"])).fetchone()
        return self._view(scope, receipt["proposal_id"], lease)

    def get_execution_view(self, principal: Principal, proposal_id: str) -> ActionExecutionView:
        """Read the canonical execution projection without inventing client state."""
        scope = TenantScope(principal.org_id, principal.project_id)
        with connect(scope) as conn:
            lease = conn.execute(
                """SELECT * FROM aip_action_execution_lease
                   WHERE org_id=%s AND project_id=%s AND proposal_id=%s
                   ORDER BY attempt DESC, created_at DESC LIMIT 1""",
                (*scope.key, proposal_id),
            ).fetchone()
        return self._view(scope, proposal_id, lease)

    def create_compensation(
        self,
        principal: Principal,
        proposal_id: str,
        idempotency_key: str,
        body: CreateCompensationRequest,
    ):
        scope = TenantScope(principal.org_id, principal.project_id)
        with connect(scope) as conn:
            original = conn.execute(
                "SELECT risk_level FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                (*scope.key, proposal_id),
            ).fetchone()
            receipt = conn.execute(
                "SELECT receipt_id,status FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s AND proposal_id=%s",
                (*scope.key, body.receipt_id, proposal_id),
            ).fetchone()
        if original is None or receipt is None:
            raise AipActionNotFound("original proposal or receipt not found in scope")
        if original["risk_level"] == "R4":
            raise AipActionTransitionBlocked("R4 compensation requires specialized policy")
        if receipt["status"] not in {"applied", "reconciled"}:
            raise AipActionTransitionBlocked("only an applied or reconciled outcome can be compensated")
        from aos_api.aip_action_service import AipActionService

        request = CreateActionProposalRequest(
            action_type_id=body.action_type_id,
            purpose=body.purpose,
            payload=body.payload,
            evidence_refs=[ResourceRef(
                resource_type="ActionReceipt",
                resource_id=body.receipt_id,
                revision=None,
                authority="aip_action_receipt",
            )],
        )
        return AipActionService(self._store).create_proposal(principal, idempotency_key, request)

    def _append_initial_receipt(self, scope: TenantScope, proposal: Any, lease_id: str, outcome: AdapterOutcome) -> None:
        fingerprint = canonical_hash({"proposalId": proposal["proposal_id"], "proposalHash": proposal["proposal_hash"], "payload": proposal["payload"]})
        receipt_payload = dict(outcome.payload)
        if proposal["action_binding_hash"]:
            receipt_payload["actionBindingHash"] = proposal["action_binding_hash"]
        with connect(scope) as conn:
            conn.execute(
                """INSERT INTO aip_action_receipt
                   (org_id,project_id,receipt_id,proposal_id,lease_id,status,provider_request_id,
                    request_fingerprint,evidence_refs,payload,receipt_kind)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,%s::jsonb,'initial')
                   ON CONFLICT (org_id,project_id,lease_id) WHERE receipt_kind='initial' DO NOTHING""",
                (*scope.key, f"receipt-{uuid.uuid4().hex[:20]}", proposal["proposal_id"], lease_id, outcome.status, outcome.provider_request_id, fingerprint, self._store._json(receipt_payload)),
            )
            projected_status = "executing" if outcome.status == "accepted" else outcome.status
            conn.execute("UPDATE aip_action_proposal SET status=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (projected_status, *scope.key, proposal["proposal_id"]))
            conn.commit()

    def _apply_guardrails(self, conn: Any, scope: TenantScope, action_type_id: str) -> None:
        self._assert_no_kill_switch(conn, scope, action_type_id)
        rows = conn.execute(
            "SELECT daily_budget,rate_limit_per_minute FROM aip_action_guardrail WHERE org_id=%s AND project_id=%s AND (action_type_id IS NULL OR action_type_id=%s)",
            (*scope.key, action_type_id),
        ).fetchall()
        budgets = [int(row["daily_budget"]) for row in rows if row["daily_budget"] is not None]
        rates = [int(row["rate_limit_per_minute"]) for row in rows if row["rate_limit_per_minute"] is not None]
        now = datetime.now(timezone.utc)
        minute = now.replace(second=0, microsecond=0)
        used_day = int(conn.execute("SELECT COALESCE(SUM(budget_units),0) AS n FROM aip_action_usage WHERE org_id=%s AND project_id=%s AND action_type_id=%s AND usage_day=%s", (*scope.key, action_type_id, now.date())).fetchone()["n"])
        used_minute = int(conn.execute("SELECT COALESCE(SUM(execution_count),0) AS n FROM aip_action_usage WHERE org_id=%s AND project_id=%s AND action_type_id=%s AND usage_minute=%s", (*scope.key, action_type_id, minute)).fetchone()["n"])
        if budgets and used_day + 1 > min(budgets):
            raise AipActionBudgetExceeded("daily Action budget exhausted")
        if rates and used_minute + 1 > min(rates):
            raise AipActionBudgetExceeded("Action rate limit exhausted")
        conn.execute(
            """INSERT INTO aip_action_usage
               (org_id,project_id,action_type_id,usage_day,usage_minute,execution_count,budget_units)
               VALUES (%s,%s,%s,%s,%s,1,1)
               ON CONFLICT (org_id,project_id,action_type_id,usage_day,usage_minute)
               DO UPDATE SET execution_count=aip_action_usage.execution_count+1,
                             budget_units=aip_action_usage.budget_units+1,updated_at=NOW()""",
            (*scope.key, action_type_id, now.date(), minute),
        )

    @staticmethod
    def _assert_no_kill_switch(conn: Any, scope: TenantScope, action_type_id: str) -> None:
        if os.getenv("AIP_ACTION_PLATFORM_KILL_SWITCH", "").strip().lower() in {"1", "true", "yes", "on"}:
            raise AipActionTransitionBlocked("platform Action kill switch is enabled")
        row = conn.execute(
            "SELECT level FROM aip_action_guardrail WHERE org_id=%s AND project_id=%s AND kill_enabled=TRUE AND (action_type_id IS NULL OR action_type_id=%s) ORDER BY level LIMIT 1",
            (*scope.key, action_type_id),
        ).fetchone()
        if row is not None:
            raise AipActionTransitionBlocked(f"{row['level']} Action kill switch is enabled")

    def _view(self, scope: TenantScope, proposal_id: str, lease: Any | None) -> ActionExecutionView:
        bundle = self._store.get_proposal(scope, proposal_id)
        with connect(scope) as conn:
            receipts = conn.execute("SELECT * FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND proposal_id=%s ORDER BY created_at,receipt_id", (*scope.key, proposal_id)).fetchall()
        lease_model = None if lease is None else ActionExecutionLeaseSnapshot(
            id=lease["lease_id"], proposal_id=proposal_id,
            proposal_hash=lease["proposal_hash"], attempt=lease["attempt"],
            expires_at=lease["expires_at"], created_at=lease["created_at"],
            action_binding_hash=lease["action_binding_hash"],
            approval_set_hash=lease["approval_set_hash"],
            reservation_ref=lease["reservation_ref"],
        )
        receipt_models = [ActionReceiptSnapshot(
            id=row["receipt_id"], proposal_id=row["proposal_id"], lease_id=row["lease_id"],
            status=ActionReceiptStatus(row["status"]), provider_request_id=row["provider_request_id"],
            evidence_refs=[ResourceRef.model_validate(item) for item in row["evidence_refs"]],
            receipt_kind=row["receipt_kind"], supersedes_receipt_id=row["supersedes_receipt_id"],
            request_fingerprint=row["request_fingerprint"], payload=row["payload"], created_at=row["created_at"],
        ) for row in receipts]
        return ActionExecutionView(proposal=bundle.proposal, lease=lease_model, receipts=receipt_models)

    def _event(self, conn: Any, scope: TenantScope, proposal: Any, event_type: str, actor_id: str, payload: dict[str, Any]) -> None:
        conn.execute(
            """INSERT INTO aip_action_event
               (org_id,project_id,event_id,proposal_id,event_type,actor_id,proposal_version,proposal_hash,payload)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
            (*scope.key, f"action-event-{uuid.uuid4().hex[:20]}", proposal["proposal_id"], event_type, actor_id, int(proposal["version"]) + 1, proposal["proposal_hash"], self._store._json(payload)),
        )
