from datetime import UTC, datetime, timedelta
import uuid

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import (
    AipNetworkPolicyStore,
    NetworkPolicyDependencyBlocked,
    NetworkPolicyIdempotencyConflict,
    NetworkPolicyNotFound,
)
from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate
from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime.now(UTC)
SUFFIX = uuid.uuid4().hex


def publish_egress(*, until=None):
    identity = uuid.uuid4().hex
    return AipRuntimeGuardPolicyStore().publish_egress(
        SCOPE,
        "test",
        f"egress:{identity}",
        EgressPolicyRevisionCreate(
            policyId=f"test:egress:{identity}", revision=1, environment="development",
            allowedSchemes=["https"], allowedHosts=["apihub.agnes-ai.com"],
            allowedPorts=[443], allowPublicFallback=False,
            unknownDestinationBehavior="block", regionState="confirmed",
            region="cn-approved-development", effectiveFrom=NOW - timedelta(days=7),
            effectiveUntil=until or NOW + timedelta(days=60), owner="test",
            approvalRef="approval:test", lifecycle="active",
        ),
    )


def policy(egress, *, name="primary", lifecycle="active", start=None, until=None):
    return NetworkPolicyRevisionCreate(
        policyId=f"test:network:{name}:{SUFFIX}", revision=1,
        allowedSchemes=["https"], allowedHosts=["apihub.agnes-ai.com"],
        allowedPorts=[443], tlsRequired=True, publicFallbackAllowed=False,
        egressPolicyRef={"assetType": "EgressPolicyRevision", "assetId": egress.policy_id,
                         "revision": egress.revision, "contentHash": egress.content_hash},
        effectiveFrom=start or NOW - timedelta(hours=1),
        effectiveUntil=until or NOW + timedelta(days=30), owner="test",
        approvalRef="approval:test", lifecycle=lifecycle,
    )


def ref(item, *, content_hash=None):
    return VersionedAssetRef(assetType="NetworkPolicyRevision", assetId=item.policy_id,
                             revision=item.revision, contentHash=content_hash or item.content_hash)


def test_network_store_cas_replay_exact_read_and_tenant_isolation() -> None:
    egress = publish_egress()
    store = AipNetworkPolicyStore()
    request = policy(egress)
    first = store.publish(SCOPE, "test", f"network:{SUFFIX}", request)
    assert store.publish(SCOPE, "test", f"network:{SUFFIX}", request) == first
    with pytest.raises(NetworkPolicyIdempotencyConflict):
        store.publish(SCOPE, "test", f"network:{SUFFIX}", request.model_copy(update={"owner": "other"}))
    with pytest.raises(NetworkPolicyNotFound):
        store.get(CANARY, first.policy_id)
    assert store.require_exact_active(SCOPE, ref(first), now=NOW) == first


def test_network_exact_gate_blocks_missing_drift_inactive_and_expired() -> None:
    egress = publish_egress()
    store = AipNetworkPolicyStore()
    with pytest.raises(NetworkPolicyDependencyBlocked, match="unavailable"):
        store.require_exact_active(SCOPE, VersionedAssetRef(
            assetType="NetworkPolicyRevision", assetId=f"missing:{SUFFIX}", revision=1,
            contentHash="a" * 64), now=NOW)
    active = store.publish(SCOPE, "test", f"active:{SUFFIX}", policy(egress, name="active"))
    with pytest.raises(NetworkPolicyDependencyBlocked, match="drifted"):
        store.require_exact_active(SCOPE, ref(active, content_hash="f" * 64), now=NOW)
    inactive = store.publish(SCOPE, "test", f"inactive:{SUFFIX}", policy(
        egress, name="inactive", lifecycle="blocked"))
    with pytest.raises(NetworkPolicyDependencyBlocked, match="not active"):
        store.require_exact_active(SCOPE, ref(inactive), now=NOW)
    expired = store.publish(SCOPE, "test", f"expired:{SUFFIX}", policy(
        egress, name="expired", start=NOW - timedelta(days=3), until=NOW - timedelta(days=1)))
    with pytest.raises(NetworkPolicyDependencyBlocked, match="outside effective window"):
        store.require_exact_active(SCOPE, ref(expired), now=NOW)


def test_network_policy_must_be_bounded_by_exact_egress() -> None:
    egress = publish_egress(until=NOW + timedelta(days=10))
    with pytest.raises(NetworkPolicyDependencyBlocked, match="window exceeds"):
        AipNetworkPolicyStore().publish(
            SCOPE, "test", f"window:{SUFFIX}", policy(egress, until=NOW + timedelta(days=20))
        )
