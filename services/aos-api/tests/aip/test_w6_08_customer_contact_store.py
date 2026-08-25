from datetime import UTC, datetime

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_customer_contact import (
    CreateCustomerFrequencyPolicyRequest,
    CustomerContactBlocked,
    CustomerFrequencyPolicyRevision,
)
from aos_api.ecommerce_workshop_customer_contact_store import EcommerceWorkshopCustomerContactStore
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def policy() -> CustomerFrequencyPolicyRevision:
    request = CreateCustomerFrequencyPolicyRequest(
        policyId="frequency-1", revision=1, channel="wecom", purpose="retention", timezone="Asia/Shanghai",
        quietHoursStart="21:00", quietHoursEnd="09:00", rollingWindowHours=24, maximumContacts=1,
    )
    return CustomerFrequencyPolicyRevision(
        tenant=TenantContext(orgId="org-org", projectId="dev-project"),
        **request.model_dump(mode="json", by_alias=True), contentHash="a" * 64,
        createdBy="operator", createdAt=datetime(2026, 8, 25, tzinfo=UTC),
    )


def test_production_store_never_trusts_caller_shaped_start_authorities():
    store = EcommerceWorkshopCustomerContactStore(connect_factory=lambda _scope: None)
    with pytest.raises(CustomerContactBlocked, match="START_AUTHORITY_RESOLVER_UNAVAILABLE"):
        store.require_start_authorities(SCOPE, None)  # type: ignore[arg-type]


def test_production_store_never_trusts_unresolved_action_receipt():
    store = EcommerceWorkshopCustomerContactStore(connect_factory=lambda _scope: None)
    with pytest.raises(CustomerContactBlocked, match="ACTION_RECEIPT_RESOLVER_UNAVAILABLE"):
        store.require_action_receipt(SCOPE, None, "a" * 64)  # type: ignore[arg-type]


def test_store_rejects_cross_tenant_authority_before_persistence():
    item = policy().model_copy(update={"tenant": TenantContext(orgId="dev-org", projectId="dev-project")})
    with pytest.raises(CustomerContactBlocked, match="TENANT_DRIFTED"):
        EcommerceWorkshopCustomerContactStore._assert_tenant(SCOPE, item)


def test_frequency_policy_quiet_hours_are_timezone_aware_and_fail_closed():
    item = policy()
    assert EcommerceWorkshopCustomerContactStore._inside_quiet_hours(item, datetime(2026, 8, 25, 15, tzinfo=UTC)) is True
    assert EcommerceWorkshopCustomerContactStore._inside_quiet_hours(item, datetime(2026, 8, 25, 8, tzinfo=UTC)) is False
