"""Read-only network activation preview; never grants or consumes approval."""
from __future__ import annotations

from aos_api.aip_network_policy_activation_target import (
    NetworkPolicyActivationTargetBlocked,
    build_network_policy_activation_target,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import (
    AipNetworkPolicyStore,
    NetworkPolicyDependencyBlocked,
)
from aos_api.tenant_scope import TenantScope


def preview_network_activation(
    scope: TenantScope,
    candidate: NetworkPolicyRevisionCreate,
    *,
    expected_version: int,
    store: AipNetworkPolicyStore,
) -> dict:
    """Show an exact candidate and current blockers without writing authority."""
    with store._connect_factory(scope) as conn:
        head = conn.execute(
            "SELECT current_revision,version FROM aip_network_policy_head "
            "WHERE org_id=%s AND project_id=%s AND policy_id=%s",
            (*scope.key, candidate.policy_id),
        ).fetchone()
    head_revision = int(head["current_revision"]) if head else 0
    head_version = int(head["version"]) if head else 0
    blockers = ["FORMAL_PRODUCER_UNAVAILABLE", "ATOMIC_APPROVAL_CONSUMER_UNAVAILABLE"]
    if expected_version != head_version:
        blockers.append("HEAD_VERSION_DRIFT")
    if candidate.revision != head_revision + 1:
        blockers.append("CANDIDATE_REVISION_DRIFT")
    try:
        store._require_egress(scope, candidate)
    except NetworkPolicyDependencyBlocked:
        blockers.append("EGRESS_DEPENDENCY_INVALID")
    try:
        target = build_network_policy_activation_target(
            scope=scope, candidate=candidate,
            expected_head_revision=head_revision, expected_head_version=head_version,
        )
    except NetworkPolicyActivationTargetBlocked:
        target = None
        if candidate.lifecycle.value != "active":
            blockers.append("ACTIVE_CANDIDATE_REQUIRED")
    if expected_version != head_version or "EGRESS_DEPENDENCY_INVALID" in blockers:
        target = None
    return {
        "policyId": candidate.policy_id,
        "candidateRevision": candidate.revision,
        "headRevision": head_revision,
        "headVersion": head_version,
        "targetContentHash": target.target_content_hash if target else None,
        "bindingHash": target.binding_hash if target else None,
        "activationAllowed": False,
        "blockers": blockers,
    }
