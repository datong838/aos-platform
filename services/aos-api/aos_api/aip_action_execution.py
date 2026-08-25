"""AIP-3B single-attempt execution, immutable Receipt and reconciliation."""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from aos_api.aip_action_adapters import ActionAdapterRegistry, AdapterOutcome
from aos_api.aip_adapter_contracts import (
    AdapterLifecycle,
    ImmutableExactRevisionRef,
    NormalizedUsageCandidate,
)
from aos_api.aip_action_models import (
    AcquireExecutionLeaseRequest,
    ActionExecutionAttemptSnapshot,
    ActionExecutionLeaseSnapshot,
    ActionExecutionView,
    ActionReconcileAttemptSnapshot,
    ActionReceiptSnapshot,
    CreateCompensationRequest,
    CreateActionDraftRequest,
    CreateManualReconcileCaseRequest,
    CreateActionProposalRequest,
    DecideManualReconcileCaseRequest,
    ManualReconcileCaseSnapshot,
    SubmitActionDraftRequest,
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
from aos_api.aip_eval_contracts import LineageRootType
from aos_api.aip_lineage_service import AipLineageService
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
        proposal, lease, attempt, adapter = self._prepare_execution(
            principal, scope, lease_id, expected_hash
        )
        if (
            adapter is None
            and attempt is not None
            and attempt["status"] == "dispatch_claimed"
            and self._dispatch_claim_is_stale(attempt)
        ):
            self._append_initial_receipt(
                scope,
                proposal,
                lease,
                attempt,
                AdapterOutcome("unknown", payload={"errorType": "DISPATCH_STATE_AMBIGUOUS"}),
            )
            return self._view(scope, proposal["proposal_id"], lease)
        if adapter is None:
            return self._view(scope, proposal["proposal_id"], lease)
        if not self._claim_dispatch(scope, attempt["attempt_id"]):
            if self._dispatch_claim_is_stale(attempt):
                self._append_initial_receipt(
                    scope,
                    proposal,
                    lease,
                    attempt,
                    AdapterOutcome("unknown", payload={"errorType": "DISPATCH_STATE_AMBIGUOUS"}),
                )
            return self._view(scope, proposal["proposal_id"], lease)

        try:
            outcome = adapter.execute(
                payload=dict(proposal["payload"] or {}),
                idempotency_key=attempt["idempotency_envelope"],
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
            outcome = AdapterOutcome(
                "unknown",
                outcome.provider_request_id,
                {"invalidAdapterStatus": outcome.status},
            )
        if not isinstance(outcome.payload, dict):
            outcome = AdapterOutcome(
                "unknown",
                outcome.provider_request_id,
                {"errorType": "ADAPTER_OUTPUT_SCHEMA_INVALID"},
            )
        usage = self._normalize_usage(adapter, outcome)
        self._append_initial_receipt(scope, proposal, lease, attempt, outcome, usage)
        return self._view(scope, proposal["proposal_id"], lease)

    def _prepare_execution(
        self,
        principal: Principal,
        scope: TenantScope,
        lease_id: str,
        expected_hash: str,
    ) -> tuple[Any, Any, Any, Any | None]:
        """Persist the one logical Provider request before any Provider I/O."""
        with connect(scope) as conn:
            self._store._idempotency_lock(conn, scope, "execute", lease_id)
            lease = conn.execute(
                "SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s FOR UPDATE",
                (*scope.key, lease_id),
            ).fetchone()
            if lease is None:
                raise AipActionNotFound("execution lease not found in scope")
            proposal = conn.execute(
                "SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR UPDATE",
                (*scope.key, lease["proposal_id"]),
            ).fetchone()
            attempt = conn.execute(
                "SELECT * FROM aip_action_execution_attempt WHERE org_id=%s AND project_id=%s AND lease_id=%s FOR UPDATE",
                (*scope.key, lease_id),
            ).fetchone()
            previous = conn.execute(
                "SELECT receipt_id FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND lease_id=%s AND receipt_kind='initial'",
                (*scope.key, lease_id),
            ).fetchone()
            if previous is not None:
                return proposal, lease, attempt, None
            if lease["owner_id"] != principal.subject:
                raise AipActionTransitionBlocked("execution lease belongs to another executor")
            if lease["proposal_hash"] != expected_hash:
                raise AipActionConflict("execution hash does not match lease")
            if attempt is not None:
                adapter = self._adapter_for_attempt(proposal, attempt)
                if adapter is None and attempt["status"] == "prepared":
                    raise AipActionDependencyUnavailable("Action adapter is not registered")
                return proposal, lease, attempt, adapter
            if lease["status"] != "active" or lease["expires_at"] <= datetime.now(timezone.utc):
                raise AipActionTransitionBlocked("execution lease is not active")
            self._store.assert_bound_impact_preview_current(conn, scope, proposal)
            binding = self._binding_context(conn, scope, proposal)
            adapter, binding = self._resolve_adapter(proposal, binding)
            self._assert_no_kill_switch(conn, scope, proposal["action_type_id"])
            attempt_id = f"attempt-{canonical_hash({'scope': scope.key, 'leaseId': lease_id})[:20]}"
            outbox_id = f"dispatch-{attempt_id.removeprefix('attempt-')}"
            request_hash = canonical_hash(
                {
                    "proposalId": proposal["proposal_id"],
                    "proposalHash": proposal["proposal_hash"],
                    "payload": proposal["payload"],
                    "actionBindingHash": lease["action_binding_hash"],
                }
            )
            idempotency_envelope = canonical_hash(
                {
                    "attemptId": attempt_id,
                    "leaseId": lease_id,
                    "proposalHash": proposal["proposal_hash"],
                    "requestHash": request_hash,
                }
            )
            conn.execute(
                """INSERT INTO aip_action_execution_attempt
                   (org_id,project_id,attempt_id,lease_id,proposal_id,status,
                    action_binding_hash,approval_set_hash,adapter_revision_ref,
                    account_binding_ref,capability_binding_ref,reservation_ref,
                    output_schema_ref,receipt_schema_ref,usage_schema_ref,
                    redaction_policy_ref,
                    idempotency_envelope,request_hash)
                   VALUES (%s,%s,%s,%s,%s,'prepared',%s,%s,%s::jsonb,%s::jsonb,
                           %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                           %s::jsonb,%s,%s)""",
                (
                    *scope.key,
                    attempt_id,
                    lease_id,
                    proposal["proposal_id"],
                    lease["action_binding_hash"],
                    lease["approval_set_hash"],
                    self._store._json(binding.get("adapterRevisionRef")) if binding.get("adapterRevisionRef") else None,
                    self._store._json(binding.get("accountBindingRef")) if binding.get("accountBindingRef") else None,
                    self._store._json(binding.get("capabilityBindingRef")) if binding.get("capabilityBindingRef") else None,
                    self._store._json(lease["reservation_ref"]) if lease["reservation_ref"] else None,
                    self._store._json(binding.get("outputSchemaRef")) if binding.get("outputSchemaRef") else None,
                    self._store._json(binding.get("receiptSchemaRef")) if binding.get("receiptSchemaRef") else None,
                    self._store._json(binding.get("usageSchemaRef")) if binding.get("usageSchemaRef") else None,
                    self._store._json(binding.get("redactionPolicyRef")) if binding.get("redactionPolicyRef") else None,
                    idempotency_envelope,
                    request_hash,
                ),
            )
            conn.execute(
                """INSERT INTO aip_action_dispatch_outbox
                   (org_id,project_id,outbox_id,attempt_id,status)
                   VALUES (%s,%s,%s,%s,'pending')""",
                (*scope.key, outbox_id, attempt_id),
            )
            conn.execute(
                "UPDATE aip_action_execution_lease SET status='consumed',consumed_at=NOW() WHERE org_id=%s AND project_id=%s AND lease_id=%s",
                (*scope.key, lease_id),
            )
            conn.execute(
                "UPDATE aip_action_proposal SET status='executing',version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                (*scope.key, proposal["proposal_id"]),
            )
            conn.commit()
            attempt = conn.execute(
                "SELECT * FROM aip_action_execution_attempt WHERE org_id=%s AND project_id=%s AND attempt_id=%s",
                (*scope.key, attempt_id),
            ).fetchone()
            return proposal, lease, attempt, adapter

    def _claim_dispatch(self, scope: TenantScope, attempt_id: str) -> bool:
        with connect(scope) as conn:
            outbox = conn.execute(
                "SELECT * FROM aip_action_dispatch_outbox WHERE org_id=%s AND project_id=%s AND attempt_id=%s FOR UPDATE",
                (*scope.key, attempt_id),
            ).fetchone()
            if outbox is None:
                raise AipActionDependencyUnavailable("execution dispatch outbox is unavailable")
            if outbox["status"] != "pending":
                return False
            claim_token = f"claim-{uuid.uuid4().hex[:20]}"
            conn.execute(
                """UPDATE aip_action_dispatch_outbox
                   SET status='dispatching',claim_token=%s,claimed_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND outbox_id=%s""",
                (claim_token, *scope.key, outbox["outbox_id"]),
            )
            conn.execute(
                """UPDATE aip_action_execution_attempt
                   SET status='dispatch_claimed',claimed_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                (*scope.key, attempt_id),
            )
            conn.commit()
            return True

    @staticmethod
    def _dispatch_claim_is_stale(attempt: Any) -> bool:
        claimed_at = attempt["claimed_at"]
        return bool(
            claimed_at
            and claimed_at <= datetime.now(timezone.utc) - timedelta(seconds=30)
        )

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
            if receipt["status"] not in {"unknown", "accepted"} or receipt["receipt_kind"] != "initial":
                raise AipActionTransitionBlocked("only an initial unknown or accepted receipt can be reconciled")
            existing = conn.execute(
                "SELECT receipt_id FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND supersedes_receipt_id=%s",
                (*scope.key, receipt_id),
            ).fetchone()
            if existing is not None:
                lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, receipt["lease_id"])).fetchone()
                return self._view(scope, receipt["proposal_id"], lease)
            proposal = conn.execute("SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, receipt["proposal_id"])).fetchone()
            reconcile_attempt_id = f"reconcile-{canonical_hash({'receiptId': receipt_id})[:20]}"
            conn.execute(
                """INSERT INTO aip_action_reconcile_attempt
                   (org_id,project_id,reconcile_attempt_id,original_receipt_id,attempt_id,
                    proposal_id,adapter_revision_ref,account_binding_ref,provider_request_id,
                    request_fingerprint,query_policy,status,expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb,'pending',NOW()+INTERVAL '30 minutes')
                   ON CONFLICT (org_id,project_id,original_receipt_id) DO NOTHING""",
                (
                    *scope.key,
                    reconcile_attempt_id,
                    receipt_id,
                    receipt["attempt_id"],
                    receipt["proposal_id"],
                    self._store._json(receipt["adapter_revision_ref"]),
                    self._store._json(receipt["account_binding_ref"]),
                    receipt["provider_request_id"],
                    receipt["request_fingerprint"],
                    self._store._json({"mode": "provider_status_query", "noExecuteRetry": True}),
                ),
            )
            reconcile_attempt = conn.execute(
                """SELECT * FROM aip_action_reconcile_attempt
                   WHERE org_id=%s AND project_id=%s AND original_receipt_id=%s FOR UPDATE""",
                (*scope.key, receipt_id),
            ).fetchone()
            if reconcile_attempt["status"] in {"claimed", "resolved", "manual_required"}:
                conn.commit()
                lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, receipt["lease_id"])).fetchone()
                return self._view(scope, receipt["proposal_id"], lease)
            if not receipt["provider_request_id"]:
                self._create_or_get_manual_case(
                    conn, scope, receipt, principal.subject, reason,
                    ["provider outcome evidence", "business object readback"], [],
                    reconcile_attempt_id=reconcile_attempt["reconcile_attempt_id"],
                )
                conn.commit()
                lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, receipt["lease_id"])).fetchone()
                return self._view(scope, receipt["proposal_id"], lease)
            conn.execute(
                """UPDATE aip_action_reconcile_attempt SET status='claimed',
                   claim_token=%s,claimed_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND reconcile_attempt_id=%s""",
                (f"claim-{uuid.uuid4().hex[:20]}", *scope.key, reconcile_attempt["reconcile_attempt_id"]),
            )
            conn.commit()
        adapter = self._adapter_for_reconcile(proposal, receipt)
        if adapter is None:
            return self._manual_after_automatic_failure(
                principal, receipt, reason, reconcile_attempt_id,
                "exact Adapter reconciliation capability unavailable",
            )
        try:
            result = adapter.reconcile(provider_request_id=receipt["provider_request_id"], request_fingerprint=receipt["request_fingerprint"])
        except Exception:
            return self._manual_after_automatic_failure(
                principal, receipt, reason, reconcile_attempt_id,
                "authorized provider reread failed",
            )
        if result.status not in {"applied", "failed", "partial"}:
            return self._manual_after_automatic_failure(
                principal, receipt, reason, reconcile_attempt_id,
                "provider reread remained non-terminal",
            )
        with connect(scope) as conn:
            current_attempt = conn.execute(
                """SELECT * FROM aip_action_reconcile_attempt
                   WHERE org_id=%s AND project_id=%s AND reconcile_attempt_id=%s FOR UPDATE""",
                (*scope.key, reconcile_attempt_id),
            ).fetchone()
            if current_attempt is None or current_attempt["status"] != "claimed":
                raise AipActionConflict("reconcile attempt claim changed before delivery")
            self._append_reconcile_receipt(
                conn, scope, receipt,
                provider_outcome=result.status,
                reconciliation_status="automatic",
                resolution_quality="confirmed",
                resolution_source="provider_query",
                payload={"provider": result.payload, "reason": reason},
                evidence_refs=[],
                reconcile_attempt_id=reconcile_attempt_id,
            )
            conn.execute(
                """UPDATE aip_action_reconcile_attempt
                   SET status='resolved',completed_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND reconcile_attempt_id=%s""",
                (*scope.key, reconcile_attempt_id),
            )
            if receipt["attempt_id"] is not None:
                conn.execute(
                    """UPDATE aip_action_execution_attempt
                       SET status=%s,provider_request_id=%s,finished_at=NOW()
                       WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                    (result.status, result.provider_request_id, *scope.key, receipt["attempt_id"]),
                )
            conn.execute("UPDATE aip_action_proposal SET status='reconciled',version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, receipt["proposal_id"]))
            conn.commit()
            lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, receipt["lease_id"])).fetchone()
        return self._view(scope, receipt["proposal_id"], lease)

    def _manual_after_automatic_failure(
        self,
        principal: Principal,
        receipt: Any,
        reason: str,
        reconcile_attempt_id: str,
        missing_fact: str,
    ) -> ActionExecutionView:
        scope = TenantScope(principal.org_id, principal.project_id)
        with connect(scope) as conn:
            current = conn.execute(
                """SELECT * FROM aip_action_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s FOR UPDATE""",
                (*scope.key, receipt["receipt_id"]),
            ).fetchone()
            existing = conn.execute(
                """SELECT receipt_id FROM aip_action_receipt
                   WHERE org_id=%s AND project_id=%s AND supersedes_receipt_id=%s""",
                (*scope.key, receipt["receipt_id"]),
            ).fetchone()
            if existing is None:
                self._create_or_get_manual_case(
                    conn, scope, current, principal.subject, reason,
                    [missing_fact, "controlled provider or business evidence"], [],
                    reconcile_attempt_id=reconcile_attempt_id,
                )
            conn.execute(
                """UPDATE aip_action_reconcile_attempt
                   SET status='manual_required',completed_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND reconcile_attempt_id=%s
                     AND status<>'resolved'""",
                (*scope.key, reconcile_attempt_id),
            )
            conn.commit()
            lease = conn.execute(
                """SELECT * FROM aip_action_execution_lease
                   WHERE org_id=%s AND project_id=%s AND lease_id=%s""",
                (*scope.key, receipt["lease_id"]),
            ).fetchone()
        return self._view(scope, receipt["proposal_id"], lease)

    def _create_or_get_manual_case(
        self,
        conn: Any,
        scope: TenantScope,
        receipt: Any,
        maker_id: str,
        reason: str,
        required_facts: list[str],
        evidence_refs: list[ResourceRef] | list[dict[str, Any]],
        *,
        reconcile_attempt_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> Any:
        normalized_evidence = [
            item.model_dump(mode="json", by_alias=True)
            if isinstance(item, ResourceRef)
            else item
            for item in evidence_refs
        ]
        normalized_required = list(dict.fromkeys([item.strip() for item in required_facts if item.strip()]))
        case_id = f"manual-case-{canonical_hash({'receiptId': receipt['receipt_id']})[:20]}"
        missing = normalized_required if not normalized_evidence else []
        conn.execute(
            """INSERT INTO aip_action_manual_reconcile_case
               (org_id,project_id,case_id,original_receipt_id,reconcile_attempt_id,
                attempt_id,proposal_id,action_binding_hash,account_binding_ref,
                object_scope,expected_diff,required_facts,evidence_refs,missing_facts,
                conflict_facts,maker_id,status,expires_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                       %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,'open',%s)
               ON CONFLICT (org_id,project_id,original_receipt_id) DO NOTHING""",
            (
                *scope.key, case_id, receipt["receipt_id"], reconcile_attempt_id,
                receipt["attempt_id"], receipt["proposal_id"], receipt["action_binding_hash"],
                self._store._json(receipt["account_binding_ref"]),
                self._store._json({"proposalId": receipt["proposal_id"]}),
                self._store._json({"reason": reason}),
                self._store._json(normalized_required), self._store._json(normalized_evidence),
                self._store._json(missing), self._store._json([]), maker_id,
                expires_at or datetime.now(timezone.utc) + timedelta(hours=24),
            ),
        )
        if reconcile_attempt_id is not None:
            conn.execute(
                """UPDATE aip_action_reconcile_attempt SET status='manual_required',completed_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND reconcile_attempt_id=%s
                     AND status<>'resolved'""",
                (*scope.key, reconcile_attempt_id),
            )
        return conn.execute(
            """SELECT * FROM aip_action_manual_reconcile_case
               WHERE org_id=%s AND project_id=%s AND original_receipt_id=%s""",
            (*scope.key, receipt["receipt_id"]),
        ).fetchone()

    def _append_reconcile_receipt(
        self,
        conn: Any,
        scope: TenantScope,
        original: Any,
        *,
        provider_outcome: str,
        reconciliation_status: str,
        resolution_quality: str,
        resolution_source: str,
        payload: dict[str, Any],
        evidence_refs: list[dict[str, Any]],
        reconcile_attempt_id: str | None = None,
        manual_case_id: str | None = None,
        manual_decision_receipt_id: str | None = None,
        applied_effect: dict[str, Any] | None = None,
        compensated_effect: dict[str, Any] | None = None,
        residual_effect: dict[str, Any] | None = None,
    ) -> str:
        controlled_payload, _ = self._control_provider_payload(payload)
        new_id = f"receipt-{canonical_hash({'parent': original['receipt_id'], 'method': reconciliation_status})[:20]}"
        response_hash = canonical_hash(controlled_payload)
        lineage_source_ref = {
            "resourceType": "ActionReceipt",
            "resourceId": new_id,
            "revision": "reconcile",
            "authority": "aip_action_receipt",
        }
        receipt_fact = {
            "receiptId": new_id,
            "originalReceiptId": original["receipt_id"],
            "attemptId": original["attempt_id"],
            "proposalId": original["proposal_id"],
            "leaseId": original["lease_id"],
            "providerOutcome": provider_outcome,
            "reconciliationStatus": reconciliation_status,
            "resolutionQuality": resolution_quality,
            "resolutionSource": resolution_source,
            "reconcileAttemptId": reconcile_attempt_id,
            "manualCaseId": manual_case_id,
            "manualDecisionReceiptId": manual_decision_receipt_id,
            "actionBindingHash": original["action_binding_hash"],
            "responseHash": response_hash,
            "evidenceRefs": evidence_refs,
            "payload": controlled_payload,
            "appliedEffect": applied_effect,
            "compensatedEffect": compensated_effect,
            "residualEffect": residual_effect,
        }
        receipt_content_hash = canonical_hash(receipt_fact)
        conn.execute(
            """INSERT INTO aip_action_receipt
               (org_id,project_id,receipt_id,proposal_id,lease_id,status,
                provider_request_id,request_fingerprint,evidence_refs,payload,
                receipt_kind,supersedes_receipt_id,attempt_id,action_binding_hash,
                approval_set_hash,adapter_revision_ref,account_binding_ref,
                capability_binding_ref,reservation_ref,response_hash,
                output_schema_ref,receipt_schema_ref,usage_schema_ref,
                redaction_policy_ref,usage_receipt_refs,lineage_source_ref,
                receipt_content_hash,provider_outcome,reconciliation_status,
                resolution_quality,resolution_source,resolution_cutoff,
                reconcile_attempt_id,manual_reconcile_case_id,
                manual_decision_receipt_id,applied_effect,compensated_effect,residual_effect)
               VALUES (%s,%s,%s,%s,%s,'reconciled',%s,%s,%s::jsonb,%s::jsonb,
                       'reconcile',%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,
                       %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,
                       %s,%s,%s,%s,NOW(),%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)""",
            (
                *scope.key, new_id, original["proposal_id"], original["lease_id"],
                original["provider_request_id"], original["request_fingerprint"],
                self._store._json(evidence_refs), self._store._json(controlled_payload),
                original["receipt_id"], original["attempt_id"], original["action_binding_hash"],
                original["approval_set_hash"], self._store._json(original["adapter_revision_ref"]),
                self._store._json(original["account_binding_ref"]),
                self._store._json(original["capability_binding_ref"]),
                self._store._json(original["reservation_ref"]), response_hash,
                self._store._json(original["output_schema_ref"]),
                self._store._json(original["receipt_schema_ref"]),
                self._store._json(original["usage_schema_ref"]),
                self._store._json(original["redaction_policy_ref"]),
                self._store._json(original["usage_receipt_refs"]),
                self._store._json(lineage_source_ref), receipt_content_hash,
                provider_outcome, reconciliation_status, resolution_quality,
                resolution_source, reconcile_attempt_id, manual_case_id,
                manual_decision_receipt_id, self._store._json(applied_effect),
                self._store._json(compensated_effect), self._store._json(residual_effect),
            ),
        )
        return new_id

    def _adapter_for_reconcile(self, proposal: Any, receipt: Any) -> Any | None:
        raw_ref = receipt["adapter_revision_ref"]
        if raw_ref is None:
            return self._adapters.get(proposal["action_type_id"])
        try:
            ref = ImmutableExactRevisionRef.model_validate(raw_ref)
        except Exception:
            return None
        item = self._adapters.get_conformant(ref)
        return item[1] if item else None

    def create_manual_reconcile_case(
        self,
        principal: Principal,
        receipt_id: str,
        body: CreateManualReconcileCaseRequest,
    ) -> ActionExecutionView:
        self._require_executor(principal)
        scope = TenantScope(principal.org_id, principal.project_id)
        with connect(scope) as conn:
            receipt = conn.execute(
                """SELECT * FROM aip_action_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s FOR UPDATE""",
                (*scope.key, receipt_id),
            ).fetchone()
            if receipt is None:
                raise AipActionNotFound("receipt not found in scope")
            if receipt["receipt_kind"] != "initial" or receipt["status"] not in {"unknown", "accepted"}:
                raise AipActionTransitionBlocked("manual reconciliation requires an initial unknown or accepted receipt")
            self._create_or_get_manual_case(
                conn,
                scope,
                receipt,
                principal.subject,
                body.reason,
                body.required_facts,
                body.evidence_refs,
                expires_at=body.expires_at,
            )
            conn.commit()
            lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, receipt["lease_id"])).fetchone()
        return self._view(scope, receipt["proposal_id"], lease)

    def decide_manual_reconcile_case(
        self,
        principal: Principal,
        case_id: str,
        body: DecideManualReconcileCaseRequest,
    ) -> ActionExecutionView:
        self._require_executor(principal)
        scope = TenantScope(principal.org_id, principal.project_id)
        with connect(scope) as conn:
            case = conn.execute(
                """SELECT * FROM aip_action_manual_reconcile_case
                   WHERE org_id=%s AND project_id=%s AND case_id=%s FOR UPDATE""",
                (*scope.key, case_id),
            ).fetchone()
            if case is None:
                raise AipActionNotFound("manual reconcile case not found in scope")
            if case["status"] == "resolved":
                receipt = conn.execute("SELECT * FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s", (*scope.key, case["original_receipt_id"])).fetchone()
                lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, receipt["lease_id"])).fetchone()
                return self._view(scope, case["proposal_id"], lease)
            if int(case["version"]) != body.expected_version:
                raise AipActionConflict("manual reconcile case version changed")
            if case["maker_id"] == principal.subject:
                raise AipActionTransitionBlocked("manual reconcile maker cannot check the same case")
            evidence_refs = [*case["evidence_refs"], *[item.model_dump(mode="json", by_alias=True) for item in body.evidence_refs]]
            if body.decision == "unresolved" or not evidence_refs:
                conn.execute(
                    """UPDATE aip_action_manual_reconcile_case
                       SET status='unresolved',version=version+1,
                           missing_facts=%s::jsonb,updated_at=NOW()
                       WHERE org_id=%s AND project_id=%s AND case_id=%s""",
                    (self._store._json(case["required_facts"] or ["controlled evidence"]), *scope.key, case_id),
                )
                conn.commit()
                receipt = conn.execute("SELECT * FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s", (*scope.key, case["original_receipt_id"])).fetchone()
                lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, receipt["lease_id"])).fetchone()
                return self._view(scope, case["proposal_id"], lease)
            outcome = body.decision.removeprefix("confirmed_")
            original = conn.execute(
                """SELECT * FROM aip_action_receipt
                   WHERE org_id=%s AND project_id=%s AND receipt_id=%s FOR UPDATE""",
                (*scope.key, case["original_receipt_id"]),
            ).fetchone()
            existing = conn.execute(
                """SELECT receipt_id FROM aip_action_receipt
                   WHERE org_id=%s AND project_id=%s AND supersedes_receipt_id=%s""",
                (*scope.key, original["receipt_id"]),
            ).fetchone()
            if existing is not None:
                raise AipActionConflict("receipt outcome was already resolved")
            decision_fact = {
                "caseId": case_id,
                "originalReceiptId": original["receipt_id"],
                "outcome": outcome,
                "makerId": case["maker_id"],
                "checkerId": principal.subject,
                "evidenceRefs": evidence_refs,
                "appliedEffect": body.applied_effect,
                "compensatedEffect": body.compensated_effect,
                "residualEffect": body.residual_effect,
            }
            decision_receipt_id = f"manual-decision-{canonical_hash(decision_fact)[:20]}"
            conn.execute(
                """INSERT INTO aip_action_manual_reconcile_decision_receipt
                   (org_id,project_id,decision_receipt_id,case_id,original_receipt_id,
                    resolved_provider_outcome,resolution_quality,evidence_refs,maker_id,checker_id,
                    applied_effect,compensated_effect,residual_effect,source_hash)
                   VALUES (%s,%s,%s,%s,%s,%s,'confirmed',%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s)""",
                (
                    *scope.key, decision_receipt_id, case_id, original["receipt_id"], outcome,
                    self._store._json(evidence_refs), case["maker_id"], principal.subject,
                    self._store._json(body.applied_effect), self._store._json(body.compensated_effect),
                    self._store._json(body.residual_effect), canonical_hash(decision_fact),
                ),
            )
            self._append_reconcile_receipt(
                conn, scope, original,
                provider_outcome=outcome,
                reconciliation_status="manual",
                resolution_quality="confirmed",
                resolution_source="manual_evidence",
                payload={"decisionReceiptId": decision_receipt_id},
                evidence_refs=evidence_refs,
                manual_case_id=case_id,
                manual_decision_receipt_id=decision_receipt_id,
                applied_effect=body.applied_effect,
                compensated_effect=body.compensated_effect,
                residual_effect=body.residual_effect,
            )
            if original["attempt_id"] is not None:
                conn.execute(
                    """UPDATE aip_action_execution_attempt SET status=%s,finished_at=NOW()
                       WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                    (outcome, *scope.key, original["attempt_id"]),
                )
            conn.execute(
                """UPDATE aip_action_manual_reconcile_case
                   SET status='resolved',version=version+1,missing_facts='[]'::jsonb,updated_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND case_id=%s""",
                (*scope.key, case_id),
            )
            conn.execute("UPDATE aip_action_proposal SET status='reconciled',version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*scope.key, case["proposal_id"]))
            conn.commit()
            lease = conn.execute("SELECT * FROM aip_action_execution_lease WHERE org_id=%s AND project_id=%s AND lease_id=%s", (*scope.key, original["lease_id"])).fetchone()
        return self._view(scope, case["proposal_id"], lease)

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
                "SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                (*scope.key, proposal_id),
            ).fetchone()
            receipt = conn.execute(
                "SELECT * FROM aip_action_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s AND proposal_id=%s",
                (*scope.key, body.receipt_id, proposal_id),
            ).fetchone()
        if original is None or receipt is None:
            raise AipActionNotFound("original proposal or receipt not found in scope")
        if original["risk_level"] == "R4":
            raise AipActionTransitionBlocked("R4 compensation requires specialized policy")
        resolved_outcome = receipt["provider_outcome"] or (
            receipt["status"] if receipt["status"] in {"applied", "failed"} else None
        )
        if resolved_outcome not in {"applied", "partial"}:
            raise AipActionTransitionBlocked("only a confirmed applied or partial outcome can be compensated")
        from aos_api.aip_action_service import AipActionService
        is_external = original["action_type_id"] in W5_EXTERNAL_ACTION_FAMILIES
        if body.policy_revision_ref is None:
            if is_external:
                raise AipActionTransitionBlocked("external compensation requires an exact CompensationPolicyRevision")
            if not body.action_type_id:
                raise AipActionTransitionBlocked("legacy internal compensation requires actionTypeId")
            request = CreateActionProposalRequest(
                action_type_id=body.action_type_id,
                purpose=body.purpose,
                payload=body.payload,
                evidence_refs=[ResourceRef(
                    resource_type="ActionReceipt", resource_id=body.receipt_id,
                    revision=None, authority="aip_action_receipt",
                )],
            )
            return AipActionService(self._store).create_proposal(principal, idempotency_key, request)
        if body.action_type_id is not None or body.payload:
            raise AipActionTransitionBlocked("exact policy compensation does not accept caller-selected actionTypeId or payload")
        with connect(scope) as conn:
            duplicate = conn.execute(
                """SELECT compensation_proposal_id FROM aip_action_compensation_link
                   WHERE org_id=%s AND project_id=%s AND original_receipt_id=%s""",
                (*scope.key, body.receipt_id),
            ).fetchone()
            if duplicate is not None:
                return self._store.get_proposal(scope, duplicate["compensation_proposal_id"])
            ref = body.policy_revision_ref
            policy = conn.execute(
                """SELECT * FROM aip_action_compensation_policy_revision
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s AND revision=%s
                     AND content_hash=%s AND lifecycle='published'
                     AND valid_from<=NOW() AND (expires_at IS NULL OR expires_at>NOW())""",
                (*scope.key, ref.resource_id, ref.revision, ref.content_hash),
            ).fetchone()
        if policy is None:
            raise AipActionDependencyUnavailable("exact CompensationPolicyRevision is unavailable")
        if policy["original_action_type_id"] != original["action_type_id"] or resolved_outcome not in set(policy["allowed_outcomes"]):
            raise AipActionTransitionBlocked("CompensationPolicyRevision does not allow this Action outcome")
        applied_effect = receipt["applied_effect"] or receipt["residual_effect"]
        compensation_effect = body.effect_delta or receipt["residual_effect"] or applied_effect
        if resolved_outcome == "partial" and (applied_effect is None or compensation_effect is None):
            raise AipActionTransitionBlocked("partial compensation requires exact applied and residual effect")
        self._assert_effect_within_policy(
            compensation_effect,
            policy["effect_scope_schema"],
            policy["maximum_effect"],
        )
        policy_ref = ref.model_dump(mode="json", by_alias=True)
        generated_payload = {
            **policy["payload_template"],
            "originalProposalId": proposal_id,
            "originalReceiptId": body.receipt_id,
            "resolvedProviderOutcome": resolved_outcome,
            "compensationPolicyRef": policy_ref,
            "effectDelta": compensation_effect,
        }
        intent_fact = {
            "originalReceiptId": body.receipt_id,
            "policyRef": policy_ref,
            "purpose": body.purpose,
            "effectDelta": compensation_effect,
            "impactPreviewRef": (
                body.impact_preview_ref.model_dump(mode="json", by_alias=True)
                if body.impact_preview_ref
                else None
            ),
        }
        intent_hash = canonical_hash(intent_fact)
        with connect(scope) as conn:
            conn.execute(
                """INSERT INTO aip_action_compensation_intent
                   (org_id,project_id,intent_id,original_receipt_id,policy_id,
                    policy_revision,policy_hash,idempotency_key,request_hash,status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')
                   ON CONFLICT (org_id,project_id,original_receipt_id) DO NOTHING""",
                (
                    *scope.key, f"comp-intent-{canonical_hash({'receiptId': body.receipt_id})[:20]}",
                    body.receipt_id, ref.resource_id, ref.revision, ref.content_hash,
                    idempotency_key, intent_hash,
                ),
            )
            intent = conn.execute(
                """SELECT * FROM aip_action_compensation_intent
                   WHERE org_id=%s AND project_id=%s AND original_receipt_id=%s FOR UPDATE""",
                (*scope.key, body.receipt_id),
            ).fetchone()
            if intent["request_hash"] != intent_hash:
                raise AipActionIdempotencyConflict("compensation intent already fixes another exact request")
            if intent["status"] == "linked":
                conn.commit()
                return self._store.get_proposal(scope, intent["compensation_proposal_id"])
            effective_idempotency_key = intent["idempotency_key"]
            conn.commit()
        request = CreateActionProposalRequest(
            action_type_id=policy["compensation_action_type_id"],
            purpose=body.purpose,
            object_ref=(ResourceRef.model_validate(original["object_ref"]) if original["object_ref"] else None),
            payload=generated_payload,
            evidence_refs=[ResourceRef(
                resource_type="ActionReceipt", resource_id=body.receipt_id,
                revision=receipt["receipt_content_hash"], authority="aip_action_receipt",
            )],
            impact_preview_ref=body.impact_preview_ref,
        )
        action_service = AipActionService(self._store)
        prepared_body = CreateActionDraftRequest.model_validate(
            request.model_dump(mode="json", by_alias=True)
        )
        _prepared_scope, _prepared_snapshot, prepared_risk = action_service._prepare_action(
            principal, prepared_body
        )
        risk_order = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}
        if risk_order[prepared_risk.level.value] < risk_order[policy["risk_floor"]]:
            raise AipActionTransitionBlocked("generated compensation risk is below policy floor")
        if policy["compensation_action_type_id"] in W5_EXTERNAL_ACTION_FAMILIES:
            draft = action_service.create_draft(
                principal,
                f"{effective_idempotency_key}:draft",
                prepared_body,
            )
            bundle = action_service.submit_draft(
                principal,
                draft.draft_id,
                f"{effective_idempotency_key}:submit",
                SubmitActionDraftRequest(
                    expected_revision=draft.revision,
                    expected_content_hash=draft.content_hash,
                ),
            )
        else:
            bundle = action_service.create_proposal(principal, effective_idempotency_key, request)
        # Creating a compensation proposal does not prove that the inverse effect
        # has happened. Preserve the currently confirmed residual effect until a
        # later execution Receipt closes that fact.
        residual_effect = receipt["residual_effect"] or applied_effect
        link_fact = {
            "originalProposalId": proposal_id,
            "originalReceiptId": body.receipt_id,
            "resolvedOutcomeReceiptId": body.receipt_id,
            "policyRef": policy_ref,
            "compensationProposalId": bundle.proposal.id,
            "appliedEffect": applied_effect,
            "compensationEffect": compensation_effect,
            "residualEffect": residual_effect,
        }
        with connect(scope) as conn:
            conn.execute(
                """INSERT INTO aip_action_compensation_link
                   (org_id,project_id,link_id,original_proposal_id,original_receipt_id,
                    resolved_outcome_receipt_id,policy_id,policy_revision,policy_hash,
                    compensation_proposal_id,action_binding_hash,applied_effect,
                    compensation_effect,residual_effect,source_hash)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s)
                   ON CONFLICT (org_id,project_id,original_receipt_id) DO NOTHING""",
                (
                    *scope.key, f"comp-link-{canonical_hash(link_fact)[:20]}", proposal_id,
                    body.receipt_id, body.receipt_id, ref.resource_id, ref.revision,
                    ref.content_hash, bundle.proposal.id, original["action_binding_hash"],
                    self._store._json(applied_effect), self._store._json(compensation_effect),
                    self._store._json(residual_effect), canonical_hash(link_fact),
                ),
            )
            conn.execute(
                """UPDATE aip_action_compensation_intent
                   SET status='linked',compensation_proposal_id=%s,linked_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND original_receipt_id=%s
                     AND request_hash=%s""",
                (bundle.proposal.id, *scope.key, body.receipt_id, intent_hash),
            )
            conn.execute(
                """UPDATE aip_action_proposal SET compensation_original_proposal_id=%s,
                   compensation_original_receipt_id=%s,compensation_policy_ref=%s::jsonb,
                   compensation_effect=%s::jsonb,compensation_residual_effect=%s::jsonb
                   WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
                (
                    proposal_id, body.receipt_id, self._store._json(policy_ref),
                    self._store._json(compensation_effect), self._store._json(residual_effect),
                    *scope.key, bundle.proposal.id,
                ),
            )
            conn.commit()
        return self._store.get_proposal(scope, bundle.proposal.id)

    def _append_initial_receipt(
        self,
        scope: TenantScope,
        proposal: Any,
        lease: Any,
        attempt: Any,
        outcome: AdapterOutcome,
        usage: NormalizedUsageCandidate | None = None,
    ) -> None:
        usage = usage or NormalizedUsageCandidate(
            quality="unknown", amount=None, unit="request"
        )
        controlled_payload, redaction_manifest = self._control_provider_payload(outcome.payload)
        applied_effect = controlled_payload.get("appliedEffect")
        residual_effect = controlled_payload.get("residualEffect")
        if residual_effect is None and outcome.status in {"applied", "partial"}:
            residual_effect = applied_effect
        if not isinstance(applied_effect, dict):
            applied_effect = None
        if not isinstance(residual_effect, dict):
            residual_effect = None
        response_hash = canonical_hash(controlled_payload)
        receipt_id = f"receipt-{canonical_hash({'attemptId': attempt['attempt_id']})[:20]}"
        artifact_id = f"action-response-{attempt['attempt_id'].removeprefix('attempt-')}"
        usage_receipt_id = f"usage-{canonical_hash({'attemptId': attempt['attempt_id'], 'kind': 'action'})[:28]}"
        lineage_id = AipLineageService.lineage_id(
            LineageRootType.ACTION, proposal["proposal_id"]
        )
        response_artifact_ref = {
            "resourceType": "ActionResponseArtifact",
            "resourceId": artifact_id,
            "revision": response_hash,
            "authority": "aip_action_response_artifact",
        }
        usage_ref = {
            "resourceType": "UsageReceipt",
            "resourceId": usage_receipt_id,
            "revision": response_hash,
            "authority": "aip_usage_receipt",
        }
        lineage_source_ref = {
            "resourceType": "ActionReceipt",
            "resourceId": receipt_id,
            "revision": "initial",
            "authority": "aip_action_receipt",
        }
        fingerprint = attempt["request_hash"]
        receipt_payload = {
            **controlled_payload,
            "actionBindingHash": lease["action_binding_hash"],
            "redactionApplied": bool(redaction_manifest["redactedPaths"]),
        }
        receipt_fact = {
            "receiptId": receipt_id,
            "attemptId": attempt["attempt_id"],
            "proposalId": proposal["proposal_id"],
            "leaseId": lease["lease_id"],
            "status": outcome.status,
            "providerRequestId": outcome.provider_request_id,
            "requestHash": fingerprint,
            "responseHash": response_hash,
            "actionBindingHash": lease["action_binding_hash"],
            "approvalSetHash": lease["approval_set_hash"],
            "adapterRevisionRef": attempt["adapter_revision_ref"],
            "accountBindingRef": attempt["account_binding_ref"],
            "capabilityBindingRef": attempt["capability_binding_ref"],
            "reservationRef": lease["reservation_ref"],
            "outputSchemaRef": attempt["output_schema_ref"],
            "receiptSchemaRef": attempt["receipt_schema_ref"],
            "usageSchemaRef": attempt["usage_schema_ref"],
            "redactionPolicyRef": attempt["redaction_policy_ref"],
            "responseArtifactRef": response_artifact_ref,
            "usageReceiptRefs": [usage_ref],
            "usage": usage.model_dump(mode="json", by_alias=True),
            "lineageSourceRef": lineage_source_ref,
            "appliedEffect": applied_effect,
            "residualEffect": residual_effect,
            "payload": receipt_payload,
        }
        receipt_content_hash = canonical_hash(receipt_fact)
        with connect(scope) as conn:
            conn.execute(
                """INSERT INTO aip_action_response_artifact
                   (org_id,project_id,artifact_id,attempt_id,content_hash,
                    controlled_payload,redaction_manifest)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
                   ON CONFLICT (org_id,project_id,attempt_id) DO NOTHING""",
                (
                    *scope.key,
                    artifact_id,
                    attempt["attempt_id"],
                    response_hash,
                    self._store._json(controlled_payload),
                    self._store._json(redaction_manifest),
                ),
            )
            inserted = conn.execute(
                """INSERT INTO aip_action_receipt
                   (org_id,project_id,receipt_id,proposal_id,lease_id,status,provider_request_id,
                    request_fingerprint,evidence_refs,payload,receipt_kind,attempt_id,
                    action_binding_hash,approval_set_hash,adapter_revision_ref,
                    account_binding_ref,capability_binding_ref,reservation_ref,
                    response_artifact_ref,response_hash,output_schema_ref,
                    receipt_schema_ref,usage_schema_ref,redaction_policy_ref,
                    usage_receipt_refs,lineage_source_ref,receipt_content_hash,
                    provider_outcome,reconciliation_status,applied_effect,residual_effect)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,%s::jsonb,'initial',
                           %s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                           %s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                           %s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s::jsonb,%s::jsonb)
                   ON CONFLICT (org_id,project_id,lease_id) WHERE receipt_kind='initial'
                   DO NOTHING RETURNING receipt_id""",
                (
                    *scope.key,
                    receipt_id,
                    proposal["proposal_id"],
                    lease["lease_id"],
                    outcome.status,
                    outcome.provider_request_id,
                    fingerprint,
                    self._store._json(receipt_payload),
                    attempt["attempt_id"],
                    lease["action_binding_hash"],
                    lease["approval_set_hash"],
                    self._store._json(attempt["adapter_revision_ref"]) if attempt["adapter_revision_ref"] else None,
                    self._store._json(attempt["account_binding_ref"]) if attempt["account_binding_ref"] else None,
                    self._store._json(attempt["capability_binding_ref"]) if attempt["capability_binding_ref"] else None,
                    self._store._json(lease["reservation_ref"]) if lease["reservation_ref"] else None,
                    self._store._json(response_artifact_ref),
                    response_hash,
                    self._store._json(attempt["output_schema_ref"]) if attempt["output_schema_ref"] else None,
                    self._store._json(attempt["receipt_schema_ref"]) if attempt["receipt_schema_ref"] else None,
                    self._store._json(attempt["usage_schema_ref"]) if attempt["usage_schema_ref"] else None,
                    self._store._json(attempt["redaction_policy_ref"]) if attempt["redaction_policy_ref"] else None,
                    self._store._json([usage_ref]),
                    self._store._json(lineage_source_ref),
                    receipt_content_hash,
                    outcome.status,
                    "pending" if outcome.status in {"unknown", "accepted"} else "not_required",
                    self._store._json(applied_effect),
                    self._store._json(residual_effect),
                ),
            ).fetchone()
            if inserted is None:
                conn.rollback()
                return
            conn.execute(
                """INSERT INTO aip_usage_receipt
                   (org_id,project_id,receipt_id,provider,provider_receipt_id,
                    lineage_id,usage_kind,quantity,unit,currency,quality,source_hash,observed_at)
                   VALUES (%s,%s,%s,'action-delivery-bridge',%s,%s,%s,%s,
                           %s,%s,%s,%s,NOW())
                   ON CONFLICT (org_id,project_id,provider,provider_receipt_id) DO NOTHING""",
                (
                    *scope.key,
                    usage_receipt_id,
                    attempt["attempt_id"],
                    lineage_id,
                    "cost" if usage.currency else "tool_unit",
                    usage.amount,
                    usage.unit,
                    usage.currency,
                    usage.quality.value,
                    receipt_content_hash,
                ),
            )
            settlement_status = (
                "not_required"
                if not lease["reservation_ref"]
                else "unknown"
                if usage.quality.value == "unknown"
                else "pending"
            )
            conn.execute(
                """INSERT INTO aip_action_settlement_request
                   (org_id,project_id,settlement_request_id,attempt_id,receipt_id,
                    reservation_ref,status,source_hash)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                   ON CONFLICT (org_id,project_id,attempt_id) DO NOTHING""",
                (
                    *scope.key,
                    f"settlement-{attempt['attempt_id'].removeprefix('attempt-')}",
                    attempt["attempt_id"],
                    receipt_id,
                    self._store._json(lease["reservation_ref"]) if lease["reservation_ref"] else None,
                    settlement_status,
                    receipt_content_hash,
                ),
            )
            conn.execute(
                """INSERT INTO aip_action_lineage_projection_request
                   (org_id,project_id,projection_request_id,attempt_id,receipt_id,
                    lineage_id,source_hash,status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'pending')
                   ON CONFLICT (org_id,project_id,receipt_id) DO NOTHING""",
                (
                    *scope.key,
                    f"lineage-request-{attempt['attempt_id'].removeprefix('attempt-')}",
                    attempt["attempt_id"],
                    receipt_id,
                    lineage_id,
                    receipt_content_hash,
                ),
            )
            conn.execute(
                """UPDATE aip_action_execution_attempt
                   SET status=%s,provider_request_id=%s,finished_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                (outcome.status, outcome.provider_request_id, *scope.key, attempt["attempt_id"]),
            )
            conn.execute(
                """UPDATE aip_action_dispatch_outbox
                   SET status=%s,completed_at=NOW()
                   WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                ("unknown" if outcome.status == "unknown" else "delivered", *scope.key, attempt["attempt_id"]),
            )
            projected_status = "executing" if outcome.status == "accepted" else outcome.status
            conn.execute("UPDATE aip_action_proposal SET status=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (projected_status, *scope.key, proposal["proposal_id"]))
            conn.commit()

    @staticmethod
    def _control_provider_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        redacted: list[str] = []
        sensitive = {
            "secret",
            "clientsecret",
            "token",
            "accesstoken",
            "refreshtoken",
            "password",
            "cookie",
            "apikey",
            "authorization",
        }

        def visit(value: Any, path: str) -> Any:
            if isinstance(value, dict):
                controlled: dict[str, Any] = {}
                for key, item in value.items():
                    item_path = f"{path}.{key}" if path else str(key)
                    normalized_key = str(key).lower().replace("_", "").replace("-", "")
                    if normalized_key in sensitive:
                        controlled[str(key)] = "[REDACTED]"
                        redacted.append(item_path)
                    else:
                        controlled[str(key)] = visit(item, item_path)
                return controlled
            if isinstance(value, list):
                return [visit(item, f"{path}[{index}]") for index, item in enumerate(value)]
            if value is None or isinstance(value, (str, int, float, bool)):
                return value
            return str(value)

        controlled = visit(dict(payload or {}), "")
        if len(AipActionStore._json(controlled).encode()) > 64 * 1024:
            return (
                {"errorType": "PROVIDER_RESPONSE_TOO_LARGE"},
                {"redactedPaths": redacted, "truncated": True},
            )
        return controlled, {"redactedPaths": redacted, "truncated": False}

    @staticmethod
    def _assert_effect_within_policy(
        effect: dict[str, Any] | None,
        scope_schema: dict[str, Any] | None,
        maximum_effect: dict[str, Any] | None,
    ) -> None:
        if effect is None:
            return
        allowed_keys = set((scope_schema or {}).get("allowedKeys") or [])
        if allowed_keys and not set(effect).issubset(allowed_keys):
            raise AipActionTransitionBlocked("compensation effect exceeds policy scope")
        if not maximum_effect:
            return
        for key, value in effect.items():
            limit = maximum_effect.get(key)
            if limit is None:
                raise AipActionTransitionBlocked("compensation effect exceeds policy maximum")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if value < 0 or not isinstance(limit, (int, float)) or isinstance(limit, bool) or value > limit:
                    raise AipActionTransitionBlocked("compensation effect exceeds policy maximum")
            elif value != limit:
                raise AipActionTransitionBlocked("compensation effect exceeds policy maximum")

    @staticmethod
    def _binding_context(conn: Any, scope: TenantScope, proposal: Any) -> dict[str, Any]:
        if proposal["impact_preview_id"] is None:
            return {}
        row = conn.execute(
            """SELECT external_action_binding FROM aip_impact_preview_revision
               WHERE org_id=%s AND project_id=%s AND preview_id=%s
                 AND revision=%s AND content_hash=%s""",
            (
                *scope.key,
                proposal["impact_preview_id"],
                proposal["impact_preview_revision"],
                proposal["impact_preview_hash"],
            ),
        ).fetchone()
        raw_binding = row["external_action_binding"] if row else None
        if isinstance(raw_binding, str):
            raw_binding = json.loads(raw_binding)
        binding = dict(raw_binding or {})
        return {
            "adapterRevisionRef": binding.get("adapterCapabilityRef"),
            "accountBindingRef": binding.get("accountRef"),
            "capabilityBindingRef": binding.get("capabilityBindingRef"),
        }

    def _resolve_adapter(
        self, proposal: Any, binding: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        raw_ref = binding.get("adapterRevisionRef")
        if raw_ref is None:
            adapter = self._adapters.get(proposal["action_type_id"])
            if adapter is None:
                raise AipActionDependencyUnavailable("Action adapter is not registered")
            return adapter, binding
        try:
            ref = ImmutableExactRevisionRef.model_validate(raw_ref)
        except Exception as exc:
            raise AipActionDependencyUnavailable(
                "exact Adapter capability ref is invalid"
            ) from exc
        item = self._adapters.get_conformant(ref)
        if item is None:
            raise AipActionDependencyUnavailable(
                "exact conformant Adapter revision is not registered"
            )
        revision, adapter = item
        if (
            revision.lifecycle is not AdapterLifecycle.PUBLISHED
            or revision.action_type_family != proposal["action_type_id"]
        ):
            raise AipActionDependencyUnavailable(
                "Adapter revision is not published for this Action family"
            )
        exact = lambda value: value.model_dump(mode="json", by_alias=True)
        return adapter, {
            **binding,
            "outputSchemaRef": exact(revision.output_schema_ref),
            "receiptSchemaRef": exact(revision.receipt_schema_ref),
            "usageSchemaRef": exact(revision.usage_schema_ref),
            "redactionPolicyRef": exact(revision.redaction_policy_ref),
        }

    def _adapter_for_attempt(self, proposal: Any, attempt: Any) -> Any | None:
        raw_ref = attempt["adapter_revision_ref"]
        if raw_ref is None:
            return self._adapters.get(proposal["action_type_id"])
        try:
            ref = ImmutableExactRevisionRef.model_validate(raw_ref)
        except Exception:
            return None
        item = self._adapters.get_conformant(ref)
        return item[1] if item else None

    @staticmethod
    def _normalize_usage(adapter: Any, outcome: AdapterOutcome) -> NormalizedUsageCandidate:
        normalizer = getattr(adapter, "normalize_usage", None)
        if not callable(normalizer):
            return NormalizedUsageCandidate(
                providerRequestId=outcome.provider_request_id,
                quality="unknown",
                amount=None,
                unit="request",
            )
        try:
            candidate = normalizer(outcome=outcome)
            return NormalizedUsageCandidate.model_validate(candidate)
        except Exception:
            return NormalizedUsageCandidate(
                providerRequestId=outcome.provider_request_id,
                quality="unknown",
                amount=None,
                unit="request",
            )

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
            attempt = conn.execute(
                """SELECT * FROM aip_action_execution_attempt
                   WHERE org_id=%s AND project_id=%s AND proposal_id=%s
                   ORDER BY created_at DESC,attempt_id DESC LIMIT 1""",
                (*scope.key, proposal_id),
            ).fetchone()
            reconcile_attempt = conn.execute(
                """SELECT * FROM aip_action_reconcile_attempt
                   WHERE org_id=%s AND project_id=%s AND proposal_id=%s
                   ORDER BY created_at DESC,reconcile_attempt_id DESC LIMIT 1""",
                (*scope.key, proposal_id),
            ).fetchone()
            manual_case = conn.execute(
                """SELECT * FROM aip_action_manual_reconcile_case
                   WHERE org_id=%s AND project_id=%s AND proposal_id=%s
                   ORDER BY created_at DESC,case_id DESC LIMIT 1""",
                (*scope.key, proposal_id),
            ).fetchone()
            settlement = None
            lineage_request = None
            if attempt is not None:
                settlement = conn.execute(
                    """SELECT status FROM aip_action_settlement_request
                       WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                    (*scope.key, attempt["attempt_id"]),
                ).fetchone()
                lineage_request = conn.execute(
                    """SELECT status FROM aip_action_lineage_projection_request
                       WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                    (*scope.key, attempt["attempt_id"]),
                ).fetchone()
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
            attempt_id=row["attempt_id"], action_binding_hash=row["action_binding_hash"],
            approval_set_hash=row["approval_set_hash"],
            adapter_revision_ref=row["adapter_revision_ref"], account_binding_ref=row["account_binding_ref"],
            capability_binding_ref=row["capability_binding_ref"], reservation_ref=row["reservation_ref"],
            response_artifact_ref=(ResourceRef.model_validate(row["response_artifact_ref"]) if row["response_artifact_ref"] else None),
            response_hash=row["response_hash"], output_schema_ref=row["output_schema_ref"],
            receipt_schema_ref=row["receipt_schema_ref"], usage_schema_ref=row["usage_schema_ref"],
            redaction_policy_ref=row["redaction_policy_ref"],
            usage_receipt_refs=[ResourceRef.model_validate(item) for item in row["usage_receipt_refs"]],
            lineage_source_ref=(ResourceRef.model_validate(row["lineage_source_ref"]) if row["lineage_source_ref"] else None),
            receipt_content_hash=row["receipt_content_hash"],
            provider_outcome=row["provider_outcome"],
            reconciliation_status=row["reconciliation_status"],
            resolution_quality=row["resolution_quality"],
            resolution_source=row["resolution_source"],
            resolution_cutoff=row["resolution_cutoff"],
            reconcile_attempt_id=row["reconcile_attempt_id"],
            manual_reconcile_case_id=row["manual_reconcile_case_id"],
            manual_decision_receipt_id=row["manual_decision_receipt_id"],
            applied_effect=row["applied_effect"],
            compensated_effect=row["compensated_effect"],
            residual_effect=row["residual_effect"],
        ) for row in receipts]
        attempt_model = None if attempt is None else ActionExecutionAttemptSnapshot(
            id=attempt["attempt_id"], lease_id=attempt["lease_id"], proposal_id=proposal_id,
            status=attempt["status"], action_binding_hash=attempt["action_binding_hash"],
            approval_set_hash=attempt["approval_set_hash"],
            idempotency_envelope=attempt["idempotency_envelope"], request_hash=attempt["request_hash"],
            provider_request_id=attempt["provider_request_id"],
            provider_outcome=(attempt["status"] if attempt["status"] in {"accepted", "applied", "failed", "partial", "unknown"} else None),
            usage_settlement_status=(settlement["status"] if settlement else "pending"),
            lineage_projection_status=(lineage_request["status"] if lineage_request else "pending"),
            created_at=attempt["created_at"], claimed_at=attempt["claimed_at"], finished_at=attempt["finished_at"],
        )
        reconcile_model = None if reconcile_attempt is None else ActionReconcileAttemptSnapshot(
            id=reconcile_attempt["reconcile_attempt_id"],
            original_receipt_id=reconcile_attempt["original_receipt_id"],
            status=reconcile_attempt["status"],
            provider_request_id=reconcile_attempt["provider_request_id"],
            expires_at=reconcile_attempt["expires_at"],
            created_at=reconcile_attempt["created_at"],
            claimed_at=reconcile_attempt["claimed_at"],
            completed_at=reconcile_attempt["completed_at"],
        )
        manual_case_model = None if manual_case is None else ManualReconcileCaseSnapshot(
            id=manual_case["case_id"],
            original_receipt_id=manual_case["original_receipt_id"],
            status=manual_case["status"],
            version=manual_case["version"],
            required_facts=manual_case["required_facts"],
            evidence_refs=[ResourceRef.model_validate(item) for item in manual_case["evidence_refs"]],
            missing_facts=manual_case["missing_facts"],
            conflict_facts=manual_case["conflict_facts"],
            maker_id=manual_case["maker_id"],
            expires_at=manual_case["expires_at"],
            created_at=manual_case["created_at"],
            updated_at=manual_case["updated_at"],
        )
        return ActionExecutionView(
            proposal=bundle.proposal,
            lease=lease_model,
            attempt=attempt_model,
            receipts=receipt_models,
            reconcile_attempt=reconcile_model,
            manual_reconcile_case=manual_case_model,
        )

    def _event(self, conn: Any, scope: TenantScope, proposal: Any, event_type: str, actor_id: str, payload: dict[str, Any]) -> None:
        conn.execute(
            """INSERT INTO aip_action_event
               (org_id,project_id,event_id,proposal_id,event_type,actor_id,proposal_version,proposal_hash,payload)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
            (*scope.key, f"action-event-{uuid.uuid4().hex[:20]}", proposal["proposal_id"], event_type, actor_id, int(proposal["version"]) + 1, proposal["proposal_hash"], self._store._json(payload)),
        )
