"""W2-07A strict price-governance contract shell tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_price_governance import EcommerceWorkshopPriceGovernance
from aos_api.ecommerce_workshop_price_governance_contracts import PriceAxisReadiness, PriceCountLedger, PriceExactRef, PriceGovernanceViewId, PriceObservationProjection, PriceReadinessAxis
from aos_api.ecommerce_workshop_price_governance_reader import PriceGovernanceViewObservation
from aos_api.ecommerce_workshop_remedy_scenario import EcommerceWorkshopRemedyScenario
from aos_api.tenant_scope import TenantScope

HASH = "sha256:" + "a" * 64
REF = {"resourceType": "PriceObservationRevision", "resourceId": "price-1", "revision": 1, "contentHash": HASH, "receiptId": "receipt-price-1"}
SKU = {"resourceType": "ProductSku", "resourceId": "sku-1", "revision": 1, "contentHash": HASH, "receiptId": "receipt-sku-1"}
BASIS = {"basis": "landed", "skuRef": SKU, "bundleRef": None, "quantity": 1, "unit": "piece", "currency": "CNY", "tax": "included", "shipping": "included", "promotionCondition": "none", "effectiveFrom": "2026-08-24T08:00:00Z", "effectiveUntil": None}


class FakeReader:
    def __init__(self, *, tenant_drift: PriceGovernanceViewId | None = None, revision_drift: PriceGovernanceViewId | None = None) -> None:
        self.tenant_drift = tenant_drift
        self.revision_drift = revision_drift
        self.calls = []

    def read_view(self, scope, *, view_id, cutoff, limit):
        self.calls.append((scope, view_id, cutoff, limit))
        observed_scope = TenantScope(org_id="dev-org", project_id="dev-project") if view_id is self.tenant_drift else scope
        ref = PriceExactRef(resourceType="PriceAuthority", resourceId=f"{view_id.value}-1", revision=1, contentHash=HASH, receiptId=f"receipt-{view_id.value}-1")
        axes = tuple(PriceAxisReadiness(axis=axis, status="disabled" if axis is PriceReadinessAxis.REPRICING else "ready", exactRef=None if axis is PriceReadinessAxis.REPRICING else ref, blockers=[{"code": "REPRICING_R4_SPECIALIZED_GATE_REQUIRED", "dependency": "price.repricing", "requiredAction": "keep disabled"}] if axis is PriceReadinessAxis.REPRICING else []) for axis in PriceReadinessAxis)
        return PriceGovernanceViewObservation(scope=observed_scope, resource_revision=4 if view_id is self.revision_drift else 3, data_cutoff=cutoff, readiness_axes=axes, authority_refs=(ref,), input_count=0)


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


def test_bounded_reader_allows_trusted_empty_without_fake_quotes() -> None:
    reader = FakeReader()
    envelope = EcommerceWorkshopPriceGovernance(reader=reader, clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")
    assert all(item.status == "ready" and item.observations == [] for item in envelope.views)
    assert envelope.resource_revision == 3
    assert [call[3] for call in reader.calls] == [100, 100, 100]


def test_one_tenant_drift_is_isolated_but_cross_revision_drift_blocks_all() -> None:
    isolated = EcommerceWorkshopPriceGovernance(reader=FakeReader(tenant_drift=PriceGovernanceViewId.COMPETITOR), clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")
    assert [item.status for item in isolated.views] == ["ready", "blocked", "ready"]
    conflict = EcommerceWorkshopPriceGovernance(reader=FakeReader(revision_drift=PriceGovernanceViewId.SCHEDULE), clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")
    assert conflict.resource_revision == 1
    assert all(item.status == "blocked" and item.authority_refs == [] for item in conflict.views)
    assert all(item.blockers[0].code == "PRICE_SHARED_RESOURCE_REVISION_CONFLICT" for item in conflict.views)


def test_remedy_scenario_is_additive_v2_while_legacy_service_stays_v1() -> None:
    legacy = EcommerceWorkshopPriceGovernance(clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")
    enhanced = EcommerceWorkshopPriceGovernance(remedy_scenario=EcommerceWorkshopRemedyScenario(), clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")
    assert legacy.schema_version == "aos.ecommerce-workshop.price-governance-view/v1" and legacy.remedy_scenario is None
    assert enhanced.schema_version == "aos.ecommerce-workshop.price-governance-view/v2"
    assert enhanced.remedy_scenario is not None
    assert enhanced.remedy_scenario.blockers[0].code == "PRICE_CASE_EXACT_ROOT_REQUIRED"
