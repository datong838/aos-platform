"""W2-06A strict analyst contract shell tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_analyst import EcommerceWorkshopAnalyst
from aos_api.ecommerce_workshop_analyst_contracts import AnalystCountLedger, AnalystMetricValue, AnalystReadinessAxis, AnalystViewId
from aos_api.ecommerce_workshop_analyst_contracts import AnalystAxisReadiness, AnalystExactRef
from aos_api.ecommerce_workshop_analyst_reader import AnalystViewObservation
from aos_api.tenant_scope import TenantScope

HASH = "sha256:" + "a" * 64


class FakeReader:
    def __init__(self, *, drift: AnalystViewId | None = None) -> None:
        self.drift = drift
        self.calls = []

    def read_view(self, scope, *, view_id, cutoff, limit):
        self.calls.append((scope, view_id, cutoff, limit))
        observed_scope = TenantScope(org_id="dev-org", project_id="dev-project") if view_id is self.drift else scope
        ref = AnalystExactRef(resourceType="MetricAuthority", resourceId=f"{view_id.value}-1", revision=1, contentHash=HASH, receiptId=f"receipt-{view_id.value}-1")
        return AnalystViewObservation(scope=observed_scope, resource_revision=3, data_cutoff=cutoff, readiness_axes=tuple(AnalystAxisReadiness(axis=axis, status="ready", exactRef=ref) for axis in AnalystReadinessAxis), authority_refs=(ref,))


def test_analyst_shell_is_canonical_blocked_and_never_invents_zero() -> None:
    view = EcommerceWorkshopAnalyst(clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")
    assert [item.view_id for item in view.views] == list(AnalystViewId)
    assert all([axis.axis for axis in item.readiness_axes] == list(AnalystReadinessAxis) for item in view.views)
    assert all(item.status == "blocked" and item.metrics == [] for item in view.views)
    assert view.page.count == 0


def test_non_ready_metric_cannot_expose_zero_or_other_value() -> None:
    with pytest.raises(ValidationError, match="cannot expose a value"):
        AnalystMetricValue(metricId="gmv.total", status="unknown", value=0, blockers=[{"code": "LATEST_RUN_FAILED", "dependency": "P05", "requiredAction": "repair latest run"}])


def test_metric_ledger_and_ready_metric_fail_closed() -> None:
    with pytest.raises(ValidationError):
        AnalystCountLedger(denominator=2, ready=1, unknown=0, blocked=0, conflict=0)
    with pytest.raises(ValidationError, match="complete exact semantics"):
        AnalystMetricValue(metricId="gmv.total", status="ready", value=10)


def test_analyst_clock_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        EcommerceWorkshopAnalyst(clock=lambda: datetime(2026, 8, 24)).read(org_id="org-org", project_id="dev-project")


def test_bounded_reader_returns_trusted_empty_views_without_fake_metrics() -> None:
    reader = FakeReader()
    view = EcommerceWorkshopAnalyst(reader=reader, clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")
    assert all(item.status == "ready" and item.metrics == [] for item in view.views)
    assert view.resource_revision == 3
    assert view.page.count == 0
    assert [call[3] for call in reader.calls] == [100] * 7


def test_one_reader_tenant_drift_blocks_only_its_view() -> None:
    view = EcommerceWorkshopAnalyst(reader=FakeReader(drift=AnalystViewId.DIAGNOSIS), clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")
    assert [item.status for item in view.views].count("blocked") == 1
    assert view.views[2].authority_refs == []
