from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_network_policy_activation_target import (
    NetworkPolicyActivationTargetBlocked,
    build_network_policy_activation_target,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.tenant_scope import TenantScope


def _candidate(**changes):
    now = datetime(2026, 9, 29, tzinfo=UTC)
    values = {
        "policyId": "network-1", "revision": 2,
        "allowedSchemes": ["https"], "allowedHosts": ["api.agnes-ai.cn"],
        "allowedPorts": [443], "tlsRequired": True, "publicFallbackAllowed": False,
        "egressPolicyRef": {"assetType": "EgressPolicyRevision", "assetId": "egress-1",
                            "revision": 1, "contentHash": "a" * 64},
        "effectiveFrom": now, "effectiveUntil": now + timedelta(days=1),
        "owner": "owner-1", "approvalRef": "pending-formal-approval",
        "lifecycle": "active",
    }
    values.update(changes)
    return NetworkPolicyRevisionCreate.model_validate(values)


def _build(item=None, scope=None, head_revision=1, head_version=1):
    return build_network_policy_activation_target(
        scope=scope or TenantScope("org-org", "dev-project"),
        candidate=item or _candidate(), expected_head_revision=head_revision,
        expected_head_version=head_version,
    )


def test_target_is_deterministic_and_binds_exact_identity():
    first = _build()
    assert first == _build()
    assert first.action_type_id == "aip_activate_network_policy"
    assert first.policy_id == "network-1"
    assert first.revision == 2
    assert first.expected_head_revision == 1
    assert first.expected_head_version == 1
    assert len(first.target_content_hash) == len(first.binding_hash) == 64


def test_tenant_and_payload_changes_change_binding_hash():
    original = _build()
    assert _build(scope=TenantScope("other-org", "dev-project")).binding_hash != original.binding_hash
    assert _build(item=_candidate(allowedHosts=["api.example.com"])).binding_hash != original.binding_hash
    assert _build(item=_candidate(policyId="network-2")).binding_hash != original.binding_hash
    assert _build(head_version=2).binding_hash != original.binding_hash


@pytest.mark.parametrize("head_revision,head_version", [(2, 1), (-1, 1), (1, -1), (True, 1)])
def test_wrong_head_or_revision_is_rejected(head_revision, head_version):
    with pytest.raises(NetworkPolicyActivationTargetBlocked):
        _build(head_revision=head_revision, head_version=head_version)


def test_non_active_candidate_is_rejected():
    with pytest.raises(NetworkPolicyActivationTargetBlocked):
        _build(item=_candidate(lifecycle="draft"))
