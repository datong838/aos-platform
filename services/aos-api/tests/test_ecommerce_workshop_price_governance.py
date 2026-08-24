"""W2-07A strict price-governance contract shell tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_price_governance import EcommerceWorkshopPriceGovernance
from aos_api.ecommerce_workshop_price_governance_contracts import PriceCountLedger, PriceObservationProjection, PriceReadinessAxis

HASH = "sha256:" + "a" * 64
REF = {"resourceType": "PriceObservationRevision", "resourceId": "price-1", "revision": 1, "contentHash": HASH, "receiptId": "receipt-price-1"}
SKU = {"resourceType": "ProductSku", "resourceId": "sku-1", "revision": 1, "contentHash": HASH, "receiptId": "receipt-sku-1"}
BASIS = {"basis": "landed", "skuRef": SKU, "bundleRef": None, "quantity": 1, "unit": "piece", "currency": "CNY", "tax": "included", "shipping": "included", "promotionCondition": "none", "effectiveFrom": "2026-08-24T08:00:00Z", "effectiveUntil": None}


def test_price_shell_is_canonical_blocked_and_repricing_disabled() -> None:
    envelope = EcommerceWorkshopPriceGovernance(clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")
    assert [item.view_id for item in envelope.views] == ["governance", "competitor", "schedule"]
    assert all([axis.axis for axis in item.readiness_axes] == list(PriceReadinessAxis) for item in envelope.views)
    assert all(item.status == "blocked" and item.observations == [] for item in envelope.views)
    assert all(item.readiness_axes[-1].status == "disabled" for item in envelope.views)
    assert envelope.page.count == 0


def test_unknown_price_cannot_be_fabricated_as_zero() -> None:
    with pytest.raises(ValidationError, match="unknown price cannot expose"):
        PriceObservationProjection(observationRef=REF, market="CN", amount=0, quoteBasis=BASIS, observedAt="2026-08-24T08:00:00Z", freshness="unknown", license="unknown", comparability="unknown", matchStatus="unknown", originalRefs=[REF], blockers=[{"code": "PRICE_UNKNOWN", "dependency": "price", "requiredAction": "re-read"}])


def test_comparable_price_requires_fresh_licensed_confirmed_original() -> None:
    with pytest.raises(ValidationError, match="fresh licensed confirmed"):
        PriceObservationProjection(observationRef=REF, market="CN", amount=10, quoteBasis=BASIS, observedAt="2026-08-24T08:00:00Z", freshness="stale", license="allowed", comparability="comparable", matchStatus="preliminary", originalRefs=[REF])


def test_price_ledger_and_clock_fail_closed() -> None:
    with pytest.raises(ValidationError, match="conserve"):
        PriceCountLedger(input=2, eligible=1, excluded=0, needsReview=0, unknown=0, deduplicated=0)
    with pytest.raises(ValueError, match="timezone-aware"):
        EcommerceWorkshopPriceGovernance(clock=lambda: datetime(2026, 8, 24)).read(org_id="org-org", project_id="dev-project")
