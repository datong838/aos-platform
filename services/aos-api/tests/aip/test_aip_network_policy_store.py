from datetime import UTC, datetime, timedelta
import json
import uuid

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import (
    AipNetworkPolicyStore,
    NetworkPolicyApprovalRequired,
    NetworkPolicyDependencyBlocked,
    NetworkPolicyIdempotencyConflict,
    NetworkPolicyNotFound,
    materialize_policy,
)
from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate
from aos_api.tenant_scope import TenantScope
from aos_api.db import connect
from tests.aip._runtime_guard_history_fixture import seed_historical_runtime_guard


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime.now(UTC)
SUFFIX = uuid.uuid4().hex


def publish_egress(*, until=None):
    identity = uuid.uuid4().hex
    return seed_historical_runtime_guard(
        SCOPE, "test-history",
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


def seed_historical_active(egress, *, name, start=None, until=None):
    """Represent an existing row in the disposable test DB; publish stays gated."""
    item = materialize_policy(SCOPE, "test-history", policy(
        egress, name=name, lifecycle="active", start=start, until=until,
    ))
    with connect(SCOPE) as conn:
        conn.execute(
            "INSERT INTO aip_network_policy_head(org_id,project_id,policy_id,current_revision,version) VALUES(%s,%s,%s,%s,1)",
            (*SCOPE.key, item.policy_id, item.revision),
        )
        conn.execute(
            """INSERT INTO aip_network_policy_revision(org_id,project_id,policy_id,revision,content_hash,lifecycle,
               effective_from,effective_until,payload,created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (*SCOPE.key, item.policy_id, item.revision, item.content_hash, item.lifecycle.value,
             item.effective_from, item.effective_until, json.dumps(item.model_dump(mode="json", by_alias=True)),
             item.created_by, item.created_at),
        )
        conn.commit()
    return item


def test_network_store_cas_replay_exact_read_and_tenant_isolation() -> None:
    egress = publish_egress()
    store = AipNetworkPolicyStore()
    request = policy(egress, lifecycle="draft")
    first = store.publish(SCOPE, "test", f"network:{SUFFIX}", request)
    assert store.publish(SCOPE, "test", f"network:{SUFFIX}", request) == first
    with pytest.raises(NetworkPolicyIdempotencyConflict):
        store.publish(SCOPE, "test", f"network:{SUFFIX}", request.model_copy(update={"owner": "other"}))
    with pytest.raises(NetworkPolicyNotFound):
        store.get(CANARY, first.policy_id)
    with pytest.raises(NetworkPolicyDependencyBlocked, match="not active"):
        store.require_exact_active(SCOPE, ref(first), now=NOW)


def test_network_exact_gate_blocks_missing_drift_inactive_and_expired() -> None:
    egress = publish_egress()
    store = AipNetworkPolicyStore()
    with pytest.raises(NetworkPolicyDependencyBlocked, match="unavailable"):
        store.require_exact_active(SCOPE, VersionedAssetRef(
            assetType="NetworkPolicyRevision", assetId=f"missing:{SUFFIX}", revision=1,
            contentHash="a" * 64), now=NOW)
    active = seed_historical_active(egress, name="active")
    assert store.require_exact_active(SCOPE, ref(active), now=NOW) == active
    with pytest.raises(NetworkPolicyDependencyBlocked, match="drifted"):
        store.require_exact_active(SCOPE, ref(active, content_hash="f" * 64), now=NOW)
    inactive = store.publish(SCOPE, "test", f"inactive:{SUFFIX}", policy(
        egress, name="inactive", lifecycle="blocked"))
    with pytest.raises(NetworkPolicyDependencyBlocked, match="not active"):
        store.require_exact_active(SCOPE, ref(inactive), now=NOW)
    expired = seed_historical_active(
        egress, name="expired", start=NOW - timedelta(days=3), until=NOW - timedelta(days=1),
    )
    with pytest.raises(NetworkPolicyDependencyBlocked, match="outside effective window"):
        store.require_exact_active(SCOPE, ref(expired), now=NOW)


def test_network_policy_must_be_bounded_by_exact_egress() -> None:
    egress = publish_egress(until=NOW + timedelta(days=10))
    with pytest.raises(NetworkPolicyDependencyBlocked, match="window exceeds"):
        AipNetworkPolicyStore().publish(
            SCOPE, "test", f"window:{SUFFIX}", policy(egress, lifecycle="draft", until=NOW + timedelta(days=20))
        )


def test_new_active_network_policy_rejects_string_only_approval() -> None:
    egress = publish_egress()
    request = policy(egress, name="unapproved-active")
    store = AipNetworkPolicyStore()
    with pytest.raises(NetworkPolicyApprovalRequired, match="exact approval"):
        store.publish(SCOPE, "test", f"approval:{SUFFIX}", request)
    with pytest.raises(NetworkPolicyNotFound):
        store.get(SCOPE, request.policy_id)
