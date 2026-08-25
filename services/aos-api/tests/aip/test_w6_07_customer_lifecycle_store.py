import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_customer_contracts import CustomerExactRef
from aos_api.ecommerce_workshop_customer_lifecycle import CustomerConsentPolicyRevision, CustomerLifecycleBlocked
from aos_api.ecommerce_workshop_customer_lifecycle_store import EcommerceWorkshopCustomerLifecycleStore
from aos_api.tenant_scope import TenantScope
from datetime import UTC, datetime


SCOPE = TenantScope("org-org", "dev-project")


def ref(kind: str, identity: str) -> CustomerExactRef:
    return CustomerExactRef(resourceType=kind, resourceId=identity, revision=1, contentHash=f"sha256:{'a' * 64}", receiptId=f"receipt-{identity}")


def policy() -> CustomerConsentPolicyRevision:
    return CustomerConsentPolicyRevision(
        tenant=TenantContext(orgId="org-org", projectId="dev-project"), policyId="policy-1", revision=1,
        purpose="retention", allowedChannels=["wecom"], markingPolicyRef=ref("MarkingPolicyRevision", "marking"),
        retentionPolicyRef=ref("RetentionPolicyRevision", "retention"), preferencePolicyRef=ref("PreferencePolicyRevision", "preference"),
        retentionDays=365, unknownBehavior="block", contentHash="b" * 64, createdBy="operator", createdAt=datetime(2026, 8, 25, tzinfo=UTC),
    )


def test_production_store_never_trusts_caller_shaped_external_policy_refs():
    store = EcommerceWorkshopCustomerLifecycleStore(connect_factory=lambda _scope: None)
    with pytest.raises(CustomerLifecycleBlocked, match="EXTERNAL_POLICY_AUTHORITY_RESOLVER_UNAVAILABLE"):
        store.require_external_policy_authorities(SCOPE, ref("FrequencyPolicyRevision", "frequency"), ref("CapabilityBindingRevision", "capability"))


def test_store_rejects_cross_tenant_authority_before_persistence():
    item = policy().model_copy(update={"tenant": TenantContext(orgId="dev-org", projectId="dev-project")})
    with pytest.raises(CustomerLifecycleBlocked, match="TENANT_DRIFT"):
        EcommerceWorkshopCustomerLifecycleStore._assert_tenant(SCOPE, item)
