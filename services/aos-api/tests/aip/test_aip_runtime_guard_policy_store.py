from datetime import UTC, datetime, timedelta
import uuid

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevisionCreate,
    EgressPolicyRevisionCreate,
)
from aos_api.aip_runtime_guard_policy_store import (
    AipRuntimeGuardPolicyStore,
    GuardPolicyIdempotencyConflict,
    GuardPolicyNotFound,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 17, tzinfo=UTC)
SUFFIX = uuid.uuid4().hex


def egress(revision: int = 1, *, name: str = "primary", host: str = "apihub.agnes-ai.com") -> EgressPolicyRevisionCreate:
    return EgressPolicyRevisionCreate(
        policyId=f"test:egress:{name}:{SUFFIX}", revision=revision, environment="development",
        allowedSchemes=["https"], allowedHosts=[host], allowedPorts=[443],
        allowPublicFallback=False, unknownDestinationBehavior="block",
        regionState="confirmed", region="cn-approved-development",
        effectiveFrom=NOW, effectiveUntil=NOW + timedelta(days=30), owner="test",
        approvalRef="approval:test", lifecycle="active",
    )


def data_policy(revision: int = 1, *, name: str = "primary") -> DataClassificationPolicyRevisionCreate:
    return DataClassificationPolicyRevisionCreate(
        policyId=f"test:data:{name}:{SUFFIX}", revision=revision, environment="development",
        allowedClassifications=["public_catalog"],
        prohibitedClassifications=["direct_pii", "raw_order_detail", "customer_conversation", "credential", "commercial_sensitive", "cross_tenant", "unknown"],
        denyUnknown=True, allowDirectPii=False, allowCommercialSensitive=False,
        allowCrossTenant=False, effectiveFrom=NOW, effectiveUntil=NOW + timedelta(days=30),
        owner="test", approvalRef="approval:test", lifecycle="active",
    )


def test_guard_policy_store_cas_replay_exact_read_and_tenant_isolation() -> None:
    store = AipRuntimeGuardPolicyStore()
    first = store.publish_egress(SCOPE, "test", "egress-v1", egress(), expected_version=0)
    assert store.publish_egress(SCOPE, "test", "egress-v1", egress(), expected_version=0) == first
    with pytest.raises(GuardPolicyIdempotencyConflict):
        store.publish_egress(SCOPE, "test", "egress-v1", egress(revision=2), expected_version=1)
    data = store.publish_data_classification(SCOPE, "test", "data-v1", data_policy(), expected_version=0)
    assert store.get_egress(SCOPE, first.policy_id, 1).content_hash == first.content_hash
    assert store.get_data_classification(SCOPE, data.policy_id).revision == 1
    with pytest.raises(GuardPolicyNotFound):
        store.get_egress(CANARY, first.policy_id)


def test_guard_policy_store_requires_exact_active_effective_refs() -> None:
    store = AipRuntimeGuardPolicyStore()
    e = store.publish_egress(SCOPE, "test", "egress-exact", egress(name="exact"), expected_version=0)
    d = store.publish_data_classification(SCOPE, "test", "data-exact", data_policy(name="exact"), expected_version=0)
    store.require_exact_active(SCOPE, VersionedAssetRef(assetType="EgressPolicyRevision", assetId=e.policy_id, revision=1, contentHash=e.content_hash), now=NOW)
    store.require_exact_active(SCOPE, VersionedAssetRef(assetType="DataClassificationPolicyRevision", assetId=d.policy_id, revision=1, contentHash=d.content_hash), now=NOW)
