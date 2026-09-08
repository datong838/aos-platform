from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_budget_reservation_contracts import (
    BudgetBucketSnapshot,
    BudgetBucketTarget,
    BudgetExactRef,
    BudgetReservationRevision,
    ReserveBudgetRequest,
    derive_bucket_authorities,
    usage_cost_minor,
)


NOW = datetime(2026, 9, 8, tzinfo=UTC)
HASH = "sha256:" + "a" * 64


def ref(kind: str, identity: str) -> BudgetExactRef:
    return BudgetExactRef(
        resourceType=kind,
        resourceId=identity,
        revision=1,
        contentHash=HASH,
    )


def buckets():
    return tuple(
        BudgetBucketTarget(
            kind=kind,
            accountId=f"account-{kind}",
            periodStart=NOW,
            periodEnd=NOW + timedelta(days=1),
        )
        for kind in ("task", "daily", "pilot")
    )


def request(**overrides) -> ReserveBudgetRequest:
    values = {
        "operationId": "ecommerce_growth_content_generate",
        "invocationKey": "content-task-1",
        "taskRef": ref("Task", "task-1"),
        "policyRef": ref("BudgetRevision", "budget-1"),
        "pricingRef": ref("ModelPriceSnapshotRevision", "price-1"),
        "approvalRef": ref("ActionApprovalEvent", "approval-1"),
        "currency": "CNY",
        "upperBoundMinor": 500,
    }
    values.update(overrides)
    return ReserveBudgetRequest.model_validate(values)


def snapshots():
    return tuple(
        BudgetBucketSnapshot(
            **item.model_dump(),
            currency="CNY",
            limitMinor=1_000,
            heldMinor=500,
            submittedMinor=0,
            settledMinor=0,
            unknownMinor=0,
        )
        for item in buckets()
    )


def revision(**overrides):
    values = {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "invocationRef": ref("CapabilityInvocationRevision", "invocation-1"),
        "reservationRef": ref("BudgetReservationRevision", "reservation-1"),
        "operationId": "ecommerce_growth_content_generate",
        "invocationKey": "content-task-1",
        "taskRef": ref("Task", "task-1"),
        "policyRef": ref("BudgetRevision", "budget-1"),
        "pricingRef": ref("ModelPriceSnapshotRevision", "price-1"),
        "approvalRef": ref("ActionApprovalEvent", "approval-1"),
        "state": "held",
        "currency": "CNY",
        "upperBoundMinor": 500,
        "actualMinor": None,
        "providerRequestReceiptRef": None,
        "providerReceiptRef": None,
        "usageReceiptRefs": (),
        "reconciliationEvidenceRef": None,
        "buckets": snapshots(),
        "requestHash": "b" * 64,
        "replayed": False,
        "createdAt": NOW,
        "updatedAt": NOW,
    }
    values.update(overrides)
    return BudgetReservationRevision.model_validate(values)


def test_three_bucket_request_hash_is_exact_and_deterministic() -> None:
    item = request()
    assert item.request_hash() == request().request_hash()
    derived = derive_bucket_authorities(
        item,
        checked_at=NOW,
        budget_effective_from=NOW - timedelta(days=1),
        budget_effective_until=NOW + timedelta(days=40),
        daily_limit_minor=1_000,
        pilot_limit_minor=10_000,
    )
    assert tuple(bucket.kind for bucket in derived) == ("task", "daily", "pilot")
    assert derived[0].limit_minor == item.upper_bound_minor
    assert usage_cost_minor(quantity=1500, unit_price_cny="0.0025", price_unit=1000) == 0
    assert usage_cost_minor(quantity=2000, unit_price_cny="0.0025", price_unit=1000) == 1


def test_currency_and_authority_fail_closed() -> None:
    with pytest.raises(ValidationError):
        request(currency="USD")
    with pytest.raises(ValidationError, match="BudgetRevision"):
        request(policyRef=ref("BudgetPolicyRevision", "budget-1"))


def test_reservation_state_shapes_are_mutually_exclusive() -> None:
    revision()
    provider_request = ref("CapabilityProviderRequestReceipt", "request-1")
    revision(state="submitted", providerRequestReceiptRef=provider_request)
    revision(state="unknown", providerRequestReceiptRef=provider_request)
    revision(state="released")
    revision(
        state="released",
        providerRequestReceiptRef=provider_request,
        reconciliationEvidenceRef=ref("CapabilityProviderReceipt", "evidence-1"),
    )
    revision(
        state="settled",
        providerRequestReceiptRef=provider_request,
        providerReceiptRef=ref("CapabilityProviderReceipt", "provider-1"),
        usageReceiptRefs=(ref("UsageReceipt", "usage-1"),),
        actualMinor=360,
    )
    with pytest.raises(ValidationError, match="state shape drifted"):
        revision(state="unknown")
    with pytest.raises(ValidationError, match="state shape drifted"):
        revision(state="released", actualMinor=0)
    with pytest.raises(ValidationError, match="state shape drifted"):
        revision(
            state="settled",
            providerRequestReceiptRef=provider_request,
            providerReceiptRef=ref("CapabilityProviderReceipt", "provider-1"),
            usageReceiptRefs=(ref("UsageReceipt", "usage-1"),),
            actualMinor=501,
        )
