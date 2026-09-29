"""Internal read-only precheck for a future atomic NetworkPolicy consumer.

This module neither consumes an approval nor permits an active policy INSERT.
The caller owns the tenant transaction and must still pass the database gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_action_store import canonical_hash
from aos_api.aip_contracts import ApprovalDecision
from aos_api.aip_network_policy_action_producer import (
    ACTION_ID, NetworkPolicyApprovalGuard, NetworkPolicyProducerBlocked,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.tenant_scope import TenantScope


class NetworkApprovalConsumptionBlocked(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NetworkApprovalPrecheck:
    """Evidence for the caller to recheck in its eventual atomic write transaction."""

    proposal_id: str
    approval_event_id: str
    proposal_hash: str
    binding_hash: str
    policy_id: str
    revision: int
    target_content_hash: str
    consumption_key: str


_OPERATION = "network_policy.activate"


def precheck_network_activation(
    conn: Any, scope: TenantScope, proposal_id: str, approval_event_id: str,
) -> NetworkApprovalPrecheck:
    if (type(scope) is not TenantScope or not proposal_id or not approval_event_id):
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_INPUT_INVALID")
    identity = conn.execute(
        "SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
        "current_setting('aos.project_id',true) AS project_id",
    ).fetchone()
    if identity is None or (identity["role"], identity["org_id"], identity["project_id"]) != (
        "aos_runtime", *scope.key,
    ):
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_TENANT_ROLE_REQUIRED")
    row = conn.execute(
        "SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s "
        "AND proposal_id=%s FOR UPDATE",
        (*scope.key, proposal_id),
    ).fetchone()
    if row is None or row["action_type_id"] != ACTION_ID:
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_PROPOSAL_UNAVAILABLE")
    now = datetime.now(UTC)
    if row["status"] != "approved":
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_PROPOSAL_NOT_APPROVED")
    if row["expires_at"] is None or row["expires_at"] <= now:
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_PROPOSAL_EXPIRED")
    approvals = conn.execute(
        "SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s "
        "AND proposal_id=%s ORDER BY created_at,approval_event_id FOR SHARE",
        (*scope.key, proposal_id),
    ).fetchall()
    if (len(approvals) != 1 or approvals[0]["approval_event_id"] != approval_event_id
            or approvals[0]["decision"] != "approved"):
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_APPROVAL_UNAVAILABLE")
    approval = approvals[0]
    if approval["expires_at"] is None or approval["expires_at"] <= now:
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_APPROVAL_EXPIRED")
    if (int(row["version"]) != int(approval["proposal_version"]) + 1
            or row["proposal_hash"] != approval["proposal_hash"]
            or not row["action_binding_hash"]
            or row["action_binding_hash"] != approval["action_binding_hash"]
            or row["approval_policy_hash"] != canonical_hash(row["policy_snapshot"])
            or row["approval_policy_hash"] != approval["approval_policy_hash"]
            or approval["slot_id"] != "checker.1"
            or approval["actor_id"] == row["created_by"]):
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_APPROVAL_BINDING_DRIFTED")
    if conn.execute(
        "SELECT 1 FROM aip_action_withdrawal_event WHERE org_id=%s AND project_id=%s "
        "AND proposal_id=%s FOR SHARE", (*scope.key, proposal_id),
    ).fetchone():
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_WITHDRAWN")
    if conn.execute(
        "SELECT 1 FROM aip_network_policy_receipt WHERE org_id=%s AND project_id=%s "
        "AND operation=%s AND idempotency_key=%s",
        (*scope.key, _OPERATION, proposal_id),
    ).fetchone():
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_ALREADY_RECORDED")
    try:
        role = NetworkPolicyApprovalGuard(
            scope=scope, checker=approval["actor_id"], decision=ApprovalDecision.APPROVED,
        ).check(conn, scope, approval["actor_id"], row)[0].lower()
        expected_eligibility = canonical_hash({
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "actorId": approval["actor_id"], "roles": [role],
            "slotId": "checker.1", "approvalPolicyHash": row["approval_policy_hash"],
        })
        if approval["eligibility_snapshot_hash"] != expected_eligibility:
            raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_CHECKER_ROLE_DRIFTED")
        candidate = NetworkPolicyRevisionCreate.model_validate(row["payload"]["candidate"])
        if (row["payload"]["targetContentHash"] != canonical_hash(
                candidate.model_dump(mode="json", by_alias=True))
                or row["payload"]["bindingHash"] != row["action_binding_hash"]):
            raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_TARGET_DRIFTED")
    except (NetworkPolicyProducerBlocked, KeyError, TypeError, IndexError, ValueError) as exc:
        if isinstance(exc, NetworkApprovalConsumptionBlocked):
            raise
        raise NetworkApprovalConsumptionBlocked("NETWORK_CONSUMPTION_CURRENT_BINDING_DRIFTED") from exc
    return NetworkApprovalPrecheck(
        proposal_id=proposal_id, approval_event_id=approval_event_id,
        proposal_hash=row["proposal_hash"], binding_hash=row["action_binding_hash"],
        policy_id=candidate.policy_id, revision=candidate.revision,
        target_content_hash=row["payload"]["targetContentHash"], consumption_key=proposal_id,
    )
