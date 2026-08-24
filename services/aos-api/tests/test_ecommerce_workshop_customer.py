from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_customer import EcommerceWorkshopCustomer
from aos_api.ecommerce_workshop_customer_contracts import CustomerAxisReadiness, CustomerBlocker, CustomerCountLedger, CustomerExactRef, CustomerProjection, CustomerReadinessAxis, CustomerViewId


NOW = datetime(2026, 8, 24, 8, tzinfo=UTC)
HASH = "sha256:" + "a" * 64


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
