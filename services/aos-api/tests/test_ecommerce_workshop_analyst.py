"""W2-06A strict analyst contract shell tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_analyst import EcommerceWorkshopAnalyst
from aos_api.ecommerce_workshop_analyst_contracts import AnalystCountLedger, AnalystMetricValue, AnalystReadinessAxis, AnalystViewId


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
