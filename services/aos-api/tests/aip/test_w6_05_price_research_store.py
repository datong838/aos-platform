from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
import pytest

from aos_api.ecommerce_workshop_price_research import PriceResearchBlocked
from aos_api.ecommerce_workshop_price_research_store import EcommerceWorkshopPriceResearchStore
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
OTHER = TenantScope("dev-org", "dev-project")


class Connection:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def execute(self, _sql, _params=None):
        if self.fail:
            raise psycopg.OperationalError("database unavailable")
        return SimpleNamespace(fetchone=lambda: None)


class Factory:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    @contextmanager
    def __call__(self, _scope):
        yield Connection(fail=self.fail)


def test_store_rejects_tenant_drift_before_persistence():
    item = SimpleNamespace(tenant=SimpleNamespace(org_id=SCOPE.org_id, project_id=SCOPE.project_id))
    EcommerceWorkshopPriceResearchStore._assert_tenant(SCOPE, item)
    with pytest.raises(PriceResearchBlocked, match="PRICE_RESEARCH_TENANT_DRIFT"):
        EcommerceWorkshopPriceResearchStore._assert_tenant(OTHER, item)


def test_contribution_read_reports_authority_unavailable_without_fallback():
    store = EcommerceWorkshopPriceResearchStore(Factory(fail=True))
    with pytest.raises(PriceResearchBlocked, match="PRICE_RESEARCH_AUTHORITY_UNAVAILABLE"):
        store.latest_batch_or_none(SCOPE)


def test_missing_exact_ref_fails_closed_instead_of_returning_latest():
    from aos_api.ecommerce_workshop_price_governance_contracts import PriceExactRef

    store = EcommerceWorkshopPriceResearchStore(Factory())
    exact_ref = PriceExactRef(
        resourceType="PriceResearchProfileRevision",
        resourceId="missing-profile",
        revision=1,
        contentHash=f"sha256:{'a' * 64}",
        receiptId="receipt-missing-profile",
    )
    with pytest.raises(PriceResearchBlocked, match="PRICERESEARCHPROFILEREVISION_MISSING_OR_DRIFTED"):
        store.require_profile(SCOPE, exact_ref)
