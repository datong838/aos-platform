"""Read-only, exact Event reconciliation; never authorizes a decision resend."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from psycopg.rows import dict_row

from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionInquiry
from aos_api.tenant_scope import TenantScope, apply_transaction_scope


class NetworkIssuerReconcileBlocked(RuntimeError):
    pass


class ReconcileStatus(StrEnum):
    UNRESOLVED = "unresolved"
    OBSERVED = "observed"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class ReconcileResult:
    status: ReconcileStatus
    event_id: str | None = None
    decision: str | None = None


def classify_event_row(inquiry: NetworkIssuerDecisionInquiry, *, expected_actor: str,
                       row: dict[str, Any] | None) -> ReconcileResult:
    if row is None:
        return ReconcileResult(ReconcileStatus.UNRESOLVED)
    if (row.get("proposal_id") != inquiry.proposal_id
            or row.get("request_hash") != inquiry.request_hash
            or row.get("actor_id") != expected_actor
            or row.get("action_type_id") != "aip_activate_network_policy"
            or row.get("event_proposal_hash") != row.get("current_proposal_hash")
            or row.get("decision") not in {"approved", "rejected"}
            or not isinstance(row.get("approval_event_id"), str)
            or not row["approval_event_id"]):
        return ReconcileResult(ReconcileStatus.CONFLICT)
    return ReconcileResult(ReconcileStatus.OBSERVED,
                           event_id=row["approval_event_id"], decision=row["decision"])


def reconcile_approval_event_read_only(conn: Any, inquiry: NetworkIssuerDecisionInquiry,
                                       *, expected_actor: str,
                                       expected_database: str) -> ReconcileResult:
    if (conn.read_only is not True or conn.info.dbname != expected_database
            or not expected_database or not expected_actor
            or expected_actor != expected_actor.strip()):
        raise NetworkIssuerReconcileBlocked("READ_ONLY_REQUIRED")
    apply_transaction_scope(conn, TenantScope(inquiry.org_id, inquiry.project_id))
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""SELECT session_user AS login,current_user AS role,
          current_setting('aos.org_id',true) AS org_id,
          current_setting('aos.project_id',true) AS project_id,
          r.rolsuper,r.rolbypassrls,r.rolinherit,
          pg_has_role(session_user,'aos_app','MEMBER') AS owner_member
          FROM pg_roles r WHERE r.rolname=session_user""")
        identity = cur.fetchone()
        if (identity is None or identity["login"] != "aos_network_approval_issuer"
                or identity["role"] != "aos_runtime"
                or identity["org_id"] != inquiry.org_id
                or identity["project_id"] != inquiry.project_id
                or identity["rolsuper"] or identity["rolbypassrls"]
                or identity["rolinherit"] or identity["owner_member"]):
            raise NetworkIssuerReconcileBlocked("ISSUER_READ_IDENTITY_REQUIRED")
        cur.execute("""SELECT e.approval_event_id,e.proposal_id,e.request_hash,
          e.actor_id,e.decision,e.proposal_hash AS event_proposal_hash,
          p.proposal_hash AS current_proposal_hash,p.action_type_id
          FROM public.aip_action_approval_event e
          LEFT JOIN public.aip_action_proposal p
            ON p.org_id=e.org_id AND p.project_id=e.project_id
           AND p.proposal_id=e.proposal_id
          WHERE e.org_id=%s AND e.project_id=%s AND e.idempotency_key=%s""",
          (inquiry.org_id, inquiry.project_id, inquiry.idempotency_key))
        rows = cur.fetchall()
    if len(rows) > 1:
        return ReconcileResult(ReconcileStatus.CONFLICT)
    return classify_event_row(inquiry, expected_actor=expected_actor,
                              row=rows[0] if rows else None)
