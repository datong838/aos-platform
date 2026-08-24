from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_customer import EcommerceWorkshopCustomer
from aos_api.ecommerce_workshop_customer_contracts import CustomerAxisReadiness, CustomerBlocker, CustomerCountLedger, CustomerExactRef, CustomerProjection, CustomerReadinessAxis, CustomerViewId
from aos_api.ecommerce_workshop_customer_reader import CustomerViewObservation
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 24, 8, tzinfo=UTC)
HASH = "sha256:" + "a" * 64


class FakeReader:
    def __init__(self, *, tenant_drift: CustomerViewId | None = None, revision_drift: CustomerViewId | None = None) -> None:
        self.tenant_drift = tenant_drift
        self.revision_drift = revision_drift
        self.calls = []

    def read_view(self, scope, *, view_id, cutoff, limit):
        self.calls.append((scope, view_id, cutoff, limit))
        observed_scope = TenantScope(org_id="dev-org", project_id="dev-project") if view_id is self.tenant_drift else scope
        ref = CustomerExactRef(resourceType="CustomerReadAuthority", resourceId=f"{view_id.value}-1", revision=1, contentHash=HASH, receiptId=f"receipt-{view_id.value}-1")
        axes = tuple(CustomerAxisReadiness(axis=axis, status="ready", exactRef=ref) for axis in CustomerReadinessAxis)
        return CustomerViewObservation(scope=observed_scope, resource_revision=4 if view_id is self.revision_drift else 3, data_cutoff=cutoff, readiness_axes=axes, authority_refs=(ref,), input_count=0)


def test_customer_shell_is_four_view_get_only_failure_closed_without_pii() -> None:
    payload = EcommerceWorkshopCustomer(clock=lambda: NOW).read(org_id="org-org", project_id="dev-project").model_dump(mode="json", by_alias=True)
    assert [item["viewId"] for item in payload["views"]] == [item.value for item in CustomerViewId]
    assert all(len(item["readinessAxes"]) == 6 and item["status"] == "blocked" for item in payload["views"])
    serialized = str(payload).lower()
    for forbidden in ("mobile", "openid", "nickname", "avatar", "address", "email", "realname", "protectedcontact", "providerkey"):
        assert forbidden not in serialized


def test_customer_unknown_never_becomes_eligible() -> None:
    assert CustomerCountLedger(input=1, eligible=0, excluded=0, unknown=1, deduplicated=0).unknown == 1
    with pytest.raises(ValidationError):
        CustomerCountLedger(input=1, eligible=1, excluded=0, unknown=1, deduplicated=0)


def test_customer_disclosure_requires_current_consent_and_retention() -> None:
    ref = CustomerExactRef(resource_type="CustomerLiteRevision", resource_id="customer-1", revision=1, content_hash=HASH, receipt_id="receipt-1")
    blocker = CustomerBlocker(code="CONSENT_WITHDRAWN", dependency="consent", required_action="keep excluded")
    with pytest.raises(ValidationError):
        CustomerProjection(customer_ref=ref, purpose="retention", disclosure="allowed", freshness="fresh", quality="pass", consent="withdrawn", retention="active", blockers=[blocker])


def test_customer_axes_require_exact_ref_for_ready() -> None:
    with pytest.raises(ValidationError):
        CustomerAxisReadiness(axis=CustomerReadinessAxis.CUSTOMER_LITE, status="ready")


def test_customer_bounded_reader_allows_trusted_empty_without_fake_people() -> None:
    reader = FakeReader()
    envelope = EcommerceWorkshopCustomer(reader=reader, clock=lambda: NOW).read(org_id="org-org", project_id="dev-project")
    assert all(item.status == "ready" and item.items == [] for item in envelope.views)
    assert envelope.resource_revision == 3
    assert [call[3] for call in reader.calls] == [100, 100, 100, 100]


def test_customer_tenant_drift_is_isolated_and_revision_drift_blocks_all() -> None:
    isolated = EcommerceWorkshopCustomer(reader=FakeReader(tenant_drift=CustomerViewId.SEGMENT), clock=lambda: NOW).read(org_id="org-org", project_id="dev-project")
    assert [item.status for item in isolated.views] == ["ready", "blocked", "ready", "ready"]
    conflict = EcommerceWorkshopCustomer(reader=FakeReader(revision_drift=CustomerViewId.DIALOGUE), clock=lambda: NOW).read(org_id="org-org", project_id="dev-project")
    assert conflict.resource_revision == 1
    assert all(item.status == "blocked" and item.authority_refs == [] for item in conflict.views)
    assert all(item.blockers[0].code == "CUSTOMER_SHARED_RESOURCE_REVISION_CONFLICT" for item in conflict.views)
