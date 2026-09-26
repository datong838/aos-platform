"""Exact payload binding for a formally approved content repair proposal.

The generic AIP budget gate still owns approval validity and limit accounting.
This narrow reader additionally pins the revised input and installation. It
does not propose, decide, reserve, or execute anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from aos_api.aip_action_store import canonical_hash as action_hash
from aos_api.aip_budget_reservation_store import canonical_hash as budget_hash
from aos_api.ecommerce_content_repair_brief_authority import _exact
from aos_api.tenant_scope import TenantScope


def require_repair_approval_binding(
    transaction: Any, scope: TenantScope, approval_ref: Mapping[str, Any], *,
    task_id: str, run_id: str, decision_ref: Mapping[str, Any],
    brief_ref: Mapping[str, Any], prior_artifact_ref: Mapping[str, Any],
    capability_ref: Mapping[str, Any], upper_bound_minor: int, dispatch: Any,
) -> None:
    """Reject an approval that saw any other input, cap, or runtime epoch."""
    if (type(scope) is not TenantScope or type(task_id) is not str or not task_id
            or type(run_id) is not str or not run_id
            or type(upper_bound_minor) is not int
            or not 1 <= upper_bound_minor <= 100_000_000):
        raise ValueError("scoped bounded repair approval required")
    approval = _exact(approval_ref, "ActionApprovalEvent")
    _exact(decision_ref, "ReturnDecision")
    _exact(brief_ref, "TaskBriefRevision")
    _exact(capability_ref, "CapabilityRevision")
    if (type(prior_artifact_ref) is not dict or set(prior_artifact_ref) != {
            "resourceType", "resourceId", "contentHash"}
            or prior_artifact_ref["resourceType"] != "Artifact"
            or type(prior_artifact_ref["resourceId"]) is not str
            or not prior_artifact_ref["resourceId"]
            or type(prior_artifact_ref["contentHash"]) is not str
            or len(prior_artifact_ref["contentHash"]) != 64):
        raise ValueError("repair approval original Artifact ref invalid")
    try:
        installation = {
            "installationId": str(dispatch.installation_id),
            "generation": str(dispatch.generation),
            "executionEpoch": dispatch.execution_epoch,
            "cutoverGroupId": str(dispatch.cutover_group_id),
            "cutoverGroupRevision": dispatch.cutover_group_revision,
            "dispatchRevision": dispatch.dispatch_revision,
        }
        checked_at = dispatch.checked_at
    except AttributeError as exc:
        raise ValueError("current repair dispatch snapshot required") from exc
    if (type(checked_at) is not datetime or checked_at.utcoffset() is None
            or any(type(installation[name]) is not int for name in (
                "executionEpoch", "cutoverGroupRevision", "dispatchRevision"))):
        raise ValueError("current repair dispatch version invalid")
    expected_payload = {
        "returnDecisionRef": dict(decision_ref), "briefRef": dict(brief_ref),
        "priorArtifactRef": dict(prior_artifact_ref),
        "installationBindingRef": installation,
        "capabilityRef": dict(capability_ref),
        "budgetUpperBoundMinor": upper_bound_minor,
    }
    rows = transaction.execute(
        """SELECT e.approval_event_id,e.proposal_id,e.proposal_version,
                  e.proposal_hash,e.decision,e.actor_id,e.reason,e.expires_at,
                  e.created_at,e.action_binding_hash,
                  p.status AS proposal_status,p.action_type_id,p.task_id,p.run_id,
                  p.payload AS proposal_payload,p.proposal_hash AS proposal_hash_saved,
                  p.expires_at AS proposal_expires_at,
                  p.action_binding_hash AS proposal_binding_hash,
                  p.created_by AS proposal_created_by,
                  d.proposal_hash AS draft_hash,d.status AS draft_status,
                  d.snapshot AS draft_snapshot
             FROM public.aip_action_approval_event e
             JOIN public.aip_action_proposal p
               ON p.org_id=e.org_id AND p.project_id=e.project_id
              AND p.proposal_id=e.proposal_id
             JOIN public.aip_action_draft d
               ON d.org_id=p.org_id AND d.project_id=p.project_id
              AND d.proposal_id=p.proposal_id
            WHERE e.org_id=%s AND e.project_id=%s AND e.approval_event_id=%s
            LIMIT 2""",
        (*scope.key, approval.resource_id),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("unique formal repair approval unavailable")
    row = dict(rows[0])
    event = {name: row.get(name) for name in (
        "approval_event_id", "proposal_id", "proposal_version", "proposal_hash",
        "decision", "actor_id", "reason", "expires_at", "created_at",
        "action_binding_hash",
    )}
    stable = row.get("draft_snapshot")
    if (
        approval.revision != row.get("proposal_version")
        or approval.content_hash != budget_hash(event, prefixed=True)
        or row.get("decision") != "approved"
        or row.get("proposal_status") != "approved"
        or row.get("action_type_id") != "ecommerce_growth_content_generate"
        or row.get("task_id") != task_id or row.get("run_id") != run_id
        or type(row.get("proposal_created_by")) is not str
        or not row["proposal_created_by"]
        or row.get("proposal_created_by") == row.get("actor_id")
        or type(row.get("actor_id")) is not str or not row["actor_id"]
        or row.get("proposal_payload") != expected_payload
        or type(stable) is not dict
        or stable.get("tenantScope") != {"orgId": scope.org_id, "projectId": scope.project_id}
        or stable.get("taskId") != task_id or stable.get("runId") != run_id
        or stable.get("createdBy") != row.get("proposal_created_by")
        or stable.get("actionType", {}).get("id") != "ecommerce_growth_content_generate"
        or stable.get("payload") != expected_payload
        or row.get("proposal_hash") != row.get("proposal_hash_saved")
        or row.get("draft_hash") != row.get("proposal_hash_saved")
        or row.get("draft_status") != "approved"
        or action_hash(stable) != row.get("proposal_hash_saved")
        or row.get("proposal_binding_hash") != row.get("action_binding_hash")
        or stable.get("actionBindingHash") != row.get("action_binding_hash")
        or type(row.get("expires_at")) is not datetime
        or type(row.get("proposal_expires_at")) is not datetime
        or row["expires_at"] <= checked_at or row["proposal_expires_at"] <= checked_at
        or type(row.get("created_at")) is not datetime
        or row["created_at"] > checked_at
    ):
        raise ValueError("formal repair approval exact input or installation drifted")
