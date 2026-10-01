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
    EgressPolicyApprovalRequired,
    DataPolicyApprovalRequired,
    GuardPolicyIdempotencyConflict,
    GuardPolicyNotFound,
    GuardPolicyDependencyBlocked,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._runtime_guard_history_fixture import seed_historical_runtime_guard


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime.now(UTC)
SUFFIX = uuid.uuid4().hex


def egress(revision: int = 1, *, name: str = "primary", host: str = "apihub.agnes-ai.com", lifecycle: str = "active") -> EgressPolicyRevisionCreate:
    return EgressPolicyRevisionCreate(
        policyId=f"test:egress:{name}:{SUFFIX}", revision=revision, environment="development",
        allowedSchemes=["https"], allowedHosts=[host], allowedPorts=[443],
        allowPublicFallback=False, unknownDestinationBehavior="block",
        regionState="confirmed", region="cn-approved-development",
        effectiveFrom=NOW, effectiveUntil=NOW + timedelta(days=30), owner="test",
        approvalRef="approval:test", lifecycle=lifecycle,
    )


def data_policy(revision: int = 1, *, name: str = "primary", lifecycle: str = "active") -> DataClassificationPolicyRevisionCreate:
    return DataClassificationPolicyRevisionCreate(
        policyId=f"test:data:{name}:{SUFFIX}", revision=revision, environment="development",
        allowedClassifications=["public_catalog"],
        prohibitedClassifications=["direct_pii", "raw_order_detail", "customer_conversation", "credential", "commercial_sensitive", "cross_tenant", "unknown"],
        denyUnknown=True, allowDirectPii=False, allowCommercialSensitive=False,
        allowCrossTenant=False, effectiveFrom=NOW, effectiveUntil=NOW + timedelta(days=30),
        owner="test", approvalRef="approval:test", lifecycle=lifecycle,
    )


def test_guard_policy_store_cas_replay_exact_read_and_tenant_isolation() -> None:
    store = AipRuntimeGuardPolicyStore()
    first = store.publish_egress(SCOPE, "test", "egress-v1", egress(lifecycle="draft"), expected_version=0)
    assert store.publish_egress(SCOPE, "test", "egress-v1", egress(lifecycle="draft"), expected_version=0) == first
    with pytest.raises(GuardPolicyIdempotencyConflict):
        store.publish_egress(SCOPE, "test", "egress-v1", egress(revision=2, lifecycle="draft"), expected_version=1)
    data = store.publish_data_classification(SCOPE, "test", "data-v1", data_policy(lifecycle="draft"), expected_version=0)
    assert store.get_egress(SCOPE, first.policy_id, 1).content_hash == first.content_hash
    assert store.get_data_classification(SCOPE, data.policy_id).revision == 1
    with pytest.raises(GuardPolicyNotFound):
        store.get_egress(CANARY, first.policy_id)


def test_guard_policy_store_requires_exact_active_effective_refs() -> None:
    store = AipRuntimeGuardPolicyStore()
    e = seed_historical_runtime_guard(SCOPE, "test-history", egress(name="exact"))
    d = seed_historical_runtime_guard(SCOPE, "test-history", data_policy(name="exact"))
    for item,kind in ((e,"EgressPolicyRevision"),(d,"DataClassificationPolicyRevision")):
        exact=VersionedAssetRef(assetType=kind,assetId=item.policy_id,revision=item.revision,contentHash=item.content_hash)
        assert item.revision==2
        assert store.require_exact_active(SCOPE,exact,now=NOW)==item
        with pytest.raises(GuardPolicyDependencyBlocked,match="outside effective window"):
            store.require_exact_active(SCOPE,exact,now=item.effective_until)
        with pytest.raises(GuardPolicyDependencyBlocked):
            store.require_exact_active(CANARY,exact,now=NOW)
        with pytest.raises(GuardPolicyDependencyBlocked):
            store.require_exact_active(SCOPE,exact.model_copy(update={"revision":1}),now=NOW)


def test_new_active_egress_rejects_string_only_approval() -> None:
    store = AipRuntimeGuardPolicyStore()
    request = egress(name="unapproved")
    with pytest.raises(EgressPolicyApprovalRequired, match="exact approval"):
        store.publish_egress(SCOPE, "test", f"egress-unapproved:{SUFFIX}", request)
    with pytest.raises(GuardPolicyNotFound):
        store.get_egress(SCOPE, request.policy_id)


def test_new_active_data_policy_rejects_string_only_approval() -> None:
    store = AipRuntimeGuardPolicyStore()
    request = data_policy(name="unapproved")
    with pytest.raises(DataPolicyApprovalRequired, match="exact approval"):
        store.publish_data_classification(SCOPE, "test", f"data-unapproved:{SUFFIX}", request)
    with pytest.raises(GuardPolicyNotFound):
        store.get_data_classification(SCOPE, request.policy_id)
