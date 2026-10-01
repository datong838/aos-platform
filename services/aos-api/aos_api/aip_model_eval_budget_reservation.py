"""Transaction-bound first Model Eval budget hold; this never sends to Provider."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_budget_reservation_contracts import (
    BudgetExactRef, derive_model_eval_bucket_authorities,
)
from aos_api.aip_budget_reservation_store import (
    AipBudgetReservationStore, BudgetReservationBlocked, canonical_hash,
)
from aos_api.aip_model_eval_action import ModelEvalActionGuard
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
from aos_api.tenant_scope import TenantScope


class ModelEvalBudgetBlocked(BudgetReservationBlocked):
    code = "MODEL_EVAL_BUDGET_BLOCKED"


class AipModelEvalBudgetReservationStore:
    """Use the caller's SERIALIZABLE transaction for a future joint capacity hold."""

    def __init__(self) -> None:
        self._ordinary = AipBudgetReservationStore()
        self._action = ModelEvalActionGuard()

    @staticmethod
    def _ref(ref: Any, kind: str) -> BudgetExactRef:
        if ref.asset_type != kind:
            raise ModelEvalBudgetBlocked(f"exact {kind} required")
        return BudgetExactRef(
            resourceType=kind, resourceId=ref.asset_id,
            revision=ref.revision, contentHash="sha256:" + ref.content_hash,
        )

    def hold(self, conn: Any, scope: TenantScope, request_id: str,
             approval_event_id: str) -> dict[str, Any]:
        if (type(scope) is not TenantScope
            or type(request_id) is not str or not request_id
            or request_id.strip() != request_id
            or type(approval_event_id) is not str or not approval_event_id
            or approval_event_id.strip() != approval_event_id):
            raise ModelEvalBudgetBlocked("exact tenant, request and original approval required")
        identity = conn.execute("""SELECT current_user AS role,
            current_setting('aos.org_id',true) AS org_id,
            current_setting('aos.project_id',true) AS project_id,
            current_setting('transaction_isolation') AS isolation""").fetchone()
        if (identity["role"], identity["org_id"], identity["project_id"],
            identity["isolation"]) != ("aos_runtime", *scope.key, "serializable"):
            raise ModelEvalBudgetBlocked("tenant SERIALIZABLE runtime transaction required")

        application = conn.execute("""SELECT request_hash,request_json,expires_at
            FROM aip_model_eval_request WHERE org_id=%s AND project_id=%s
              AND request_id=%s""", (*scope.key, request_id)).fetchone()
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if (application is None or application["expires_at"] <= now
            or canonical_hash(application["request_json"]) != application["request_hash"]):
            raise ModelEvalBudgetBlocked("current immutable Model Eval request required")
        try:
            request = ModelEvalRequestCreate.model_validate(application["request_json"])
        except (TypeError, ValueError) as exc:
            raise ModelEvalBudgetBlocked("valid Model Eval request required") from exc
        if (request.tenant.org_id, request.tenant.project_id) != scope.key:
            raise ModelEvalBudgetBlocked("request tenant drifted")

        approval = conn.execute("""SELECT * FROM aip_action_approval_event
            WHERE org_id=%s AND project_id=%s AND approval_event_id=%s""",
            (*scope.key, approval_event_id)).fetchone()
        if (approval is None or approval["decision"] != "approved"
            or approval["expires_at"] is None or approval["expires_at"] <= now):
            raise ModelEvalBudgetBlocked("current approved checker event required")
        proposal = conn.execute("""SELECT * FROM aip_action_proposal
            WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR UPDATE""",
            (*scope.key, approval["proposal_id"])).fetchone()
        if (proposal is None or proposal["status"] != "approved"
            or proposal["expires_at"] <= now
            or proposal["payload"] != {"requestId": request_id,
                                      "requestHash": application["request_hash"]}
            or approval["proposal_hash"] != proposal["proposal_hash"]
            or int(approval["proposal_version"]) != int(proposal["version"]) - 1
            or approval["action_binding_hash"] != proposal["action_binding_hash"]
            or approval["approval_policy_hash"] != proposal["approval_policy_hash"]):
            raise ModelEvalBudgetBlocked("current original Action approval binding required")
        try:
            self._action.check_proposal(conn, scope, approval["actor_id"], proposal,
                                        checker=True)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise ModelEvalBudgetBlocked("original Model Eval checker authority drifted") from exc

        policy_row = conn.execute("""SELECT r.revision,r.content_hash,r.lifecycle,
                   r.effective_from,r.effective_until,r.payload
            FROM aip_model_governance_policy_head h
            JOIN aip_model_governance_policy_revision r
              ON r.org_id=h.org_id AND r.project_id=h.project_id
             AND r.policy_kind=h.policy_kind AND r.policy_id=h.policy_id
             AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s AND h.policy_kind='budget'
              AND h.policy_id=%s FOR SHARE OF h""",
            (*scope.key, request.budget_policy_ref.asset_id)).fetchone()
        if (policy_row is None or policy_row["lifecycle"] != "active"
            or policy_row["revision"] != request.budget_policy_ref.revision
            or policy_row["content_hash"] != request.budget_policy_ref.content_hash
            or not policy_row["effective_from"] <= now < policy_row["effective_until"]):
            raise ModelEvalBudgetBlocked("current exact BudgetPolicy required")
        try:
            policy = BudgetPolicyRevision.model_validate(policy_row["payload"])
        except (TypeError, ValueError) as exc:
            raise ModelEvalBudgetBlocked("valid BudgetPolicy payload required") from exc
        if (policy.content_hash != policy_row["content_hash"]
            or (policy.tenant.org_id, policy.tenant.project_id) != scope.key
            or policy.currency != request.currency):
            raise ModelEvalBudgetBlocked("BudgetPolicy payload drifted")
        budget_ref = self._ref(policy.budget_revision_ref, "BudgetRevision")
        price_ref = self._ref(request.price_ref, "ModelPriceSnapshotRevision")
        budget_head = conn.execute("""SELECT current_revision FROM aip_budget_head
            WHERE org_id=%s AND project_id=%s AND budget_id=%s FOR SHARE""",
            (*scope.key, budget_ref.resource_id)).fetchone()
        if budget_head is None or int(budget_head["current_revision"]) != budget_ref.revision:
            raise ModelEvalBudgetBlocked("current BudgetRevision head required")
        budget = self._ordinary._budget_authority(conn, scope, budget_ref, now)
        self._ordinary._price_authority(conn, scope, price_ref, now)
        existing = conn.execute("""SELECT * FROM aip_model_eval_budget_reservation
            WHERE org_id=%s AND project_id=%s AND request_id=%s""",
            (*scope.key, request_id)).fetchone()
        if existing is not None:
            if (existing["approval_event_id"] != approval_event_id
                or existing["request_hash"] != application["request_hash"]
                or existing["proposal_hash"] != proposal["proposal_hash"]
                or existing["upper_bound_minor"] != request.upper_bound_minor
                or existing["state"] != "held"):
                raise ModelEvalBudgetBlocked("Model Eval hold identity drifted")
            return dict(existing)
        buckets = derive_model_eval_bucket_authorities(
            request_id=request_id, budget_revision_ref=budget_ref,
            upper_bound_minor=request.upper_bound_minor, checked_at=now,
            budget_effective_from=budget["effective_from"],
            budget_effective_until=budget["effective_until"],
            daily_limit_minor=int(budget["daily_limit_minor"]),
            pilot_limit_minor=int(budget["monthly_limit_minor"]),
        )
        self._ordinary._prepare_and_lock_buckets(conn, scope, buckets)
        for bucket in buckets:
            row = self._ordinary._bucket_row(conn, scope, bucket)
            if (row is None or row["period_end"] != bucket.period_end
                or int(row["limit_minor"]) != bucket.limit_minor
                or sum(int(row[column]) for column in (
                    "held_minor", "submitted_minor", "settled_minor", "unknown_minor"
                )) + request.upper_bound_minor > bucket.limit_minor):
                raise ModelEvalBudgetBlocked(f"{bucket.kind} budget limit exceeded")
        self._ordinary._cost_risk_authority(
            conn, scope, budget_ref, price_ref, request.upper_bound_minor,
            provider_ref=self._ref(request.provider_ref, "ProviderInstanceRevision"),
        )

        reservation_id = uuid.uuid4()
        immutable = {
            "reservationId": str(reservation_id), "requestId": request_id,
            "requestHash": application["request_hash"],
            "proposalId": proposal["proposal_id"],
            "proposalHash": proposal["proposal_hash"],
            "approvalEventId": approval_event_id,
            "budgetPolicyRef": request.budget_policy_ref.model_dump(mode="json", by_alias=True),
            "budgetRevisionRef": budget_ref.model_dump(mode="json", by_alias=True),
            "priceRef": price_ref.model_dump(mode="json", by_alias=True),
            "currency": request.currency, "upperBoundMinor": request.upper_bound_minor,
            "state": "held",
        }
        content_hash = canonical_hash(immutable, prefixed=True)
        conn.execute("""INSERT INTO aip_model_eval_budget_reservation (
            org_id,project_id,reservation_id,request_id,request_hash,proposal_id,
            proposal_hash,approval_event_id,budget_policy_ref,budget_revision_ref,
            price_ref,currency,upper_bound_minor,state,content_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,'held',%s)""",
            (*scope.key, reservation_id, request_id, application["request_hash"],
             proposal["proposal_id"], proposal["proposal_hash"], approval_event_id,
             json.dumps(immutable["budgetPolicyRef"]),
             json.dumps(immutable["budgetRevisionRef"]),
             json.dumps(immutable["priceRef"]), request.currency,
             request.upper_bound_minor, content_hash))
        for bucket in buckets:
            updated = conn.execute("""UPDATE aip_budget_bucket
                SET held_minor=held_minor+%s,version=version+1,
                    updated_at=clock_timestamp()
                WHERE org_id=%s AND project_id=%s AND bucket_kind=%s
                  AND account_id=%s AND period_start=%s AND currency=%s""",
                (request.upper_bound_minor, *scope.key, bucket.kind,
                 bucket.account_id, bucket.period_start, bucket.currency))
            if updated.rowcount != 1:
                raise ModelEvalBudgetBlocked("shared budget bucket drifted")
            conn.execute("""INSERT INTO aip_model_eval_budget_reservation_bucket (
                org_id,project_id,reservation_id,bucket_kind,account_id,
                period_start,currency,reserved_minor)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, reservation_id, bucket.kind, bucket.account_id,
                 bucket.period_start, bucket.currency, request.upper_bound_minor))
        return {"reservation_id": reservation_id, "request_id": request_id,
                "approval_event_id": approval_event_id, "state": "held",
                "content_hash": content_hash}


__all__ = ["AipModelEvalBudgetReservationStore", "ModelEvalBudgetBlocked"]
