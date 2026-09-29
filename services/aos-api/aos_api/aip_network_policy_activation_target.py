"""Pure exact target hash for a future formally approved NetworkPolicy activation.

This does not register an ActionType, verify an approval, or publish a policy.
"""
from __future__ import annotations

from dataclasses import dataclass

from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import canonical_hash
from aos_api.aip_runtime_guard_policy_contracts import GuardPolicyLifecycle
from aos_api.tenant_scope import TenantScope


class NetworkPolicyActivationTargetBlocked(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NetworkPolicyActivationTarget:
    scope: TenantScope
    action_type_id: str
    policy_id: str
    revision: int
    expected_head_revision: int
    expected_head_version: int
    target_content_hash: str
    binding_hash: str


def build_network_policy_activation_target(
    *, scope: TenantScope, candidate: NetworkPolicyRevisionCreate,
    expected_head_revision: int, expected_head_version: int,
) -> NetworkPolicyActivationTarget:
    if (type(scope) is not TenantScope
            or type(candidate) is not NetworkPolicyRevisionCreate
            or type(expected_head_revision) is not int or expected_head_revision < 0
            or type(expected_head_version) is not int or expected_head_version < 0
            or candidate.lifecycle is not GuardPolicyLifecycle.ACTIVE
            or candidate.revision != expected_head_revision + 1):
        raise NetworkPolicyActivationTargetBlocked("NETWORK_ACTIVATION_TARGET_INVALID")
    action_type_id = "aip_activate_network_policy"
    target_content_hash = canonical_hash(candidate.model_dump(mode="json", by_alias=True))
    binding_hash = canonical_hash({
        "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
        "actionTypeId": action_type_id,
        "policyId": candidate.policy_id,
        "revision": candidate.revision,
        "expectedHeadRevision": expected_head_revision,
        "expectedHeadVersion": expected_head_version,
        "targetContentHash": target_content_hash,
    })
    return NetworkPolicyActivationTarget(
        scope=scope, action_type_id=action_type_id, policy_id=candidate.policy_id,
        revision=candidate.revision, expected_head_revision=expected_head_revision,
        expected_head_version=expected_head_version,
        target_content_hash=target_content_hash, binding_hash=binding_hash,
    )
