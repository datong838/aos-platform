from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_analyst import EcommerceWorkshopAnalyst
from aos_api.ecommerce_workshop_analyst_contracts import AnalystViewId
from aos_api.ecommerce_workshop_analyst_source_reader import EcommerceWorkshopAnalystSourceReader
from aos_api.source_readiness_contracts import ObservationStatus, PolicyCheckStatus, SourceReadinessStatus


_OBJECTS = (
    "Shop",
    "Product",
    "ProductSku",
    "Category",
    "Order",
    "OrderLine",
    "Shipment",
    "CustomerLite",
    "Weapp",
    "SystemConfig",
    "ProductReview",
    "Payment",
)
_VALUES = {"Shop": 1, "Product": 57, "ProductSku": 62, "Category": 11, "Order": 124, "OrderLine": 234, "Shipment": 19, "CustomerLite": 54, "Weapp": 3, "SystemConfig": 39, "ProductReview": 5, "Payment": 210}


def _exact(resource_type: str, resource_id: str) -> SimpleNamespace:
    return SimpleNamespace(resource_type=resource_type, resource_id=resource_id, revision="1", content_hash="a" * 64, authority="test")


def _item(object_type: str, index: int, cutoff: datetime) -> SimpleNamespace:
    status = SourceReadinessStatus.READY
    run_status = ObservationStatus.SUCCEEDED
    policy_status = PolicyCheckStatus.PASS
    if object_type in {"Shipment", "SystemConfig"}:
        status = SourceReadinessStatus.FAILED
        run_status = ObservationStatus.FAILED
        policy_status = PolicyCheckStatus.FAIL
    elif object_type == "Payment":
        status = SourceReadinessStatus.STALE
    return SimpleNamespace(
        object_type=object_type,
        pipeline_id=f"P{index:02d}-{object_type.lower()}-qyh",
        source_id="niushop-qyh",
        status=status,
        data_cutoff=cutoff,
        latest_run=SimpleNamespace(run_id=f"run-{index:02d}", status=run_status),
        counts=SimpleNamespace(projection_total=_VALUES[object_type]),
        quality=SimpleNamespace(status=policy_status, rule_ref=_exact("QualityPolicy", "quality-v1")),
        reconciliation=SimpleNamespace(status=PolicyCheckStatus.PASS, rule_ref=_exact("ReconciliationPolicy", "reconciliation-v1")),
    )


class _SourceService:
    def __init__(self, cutoff: datetime) -> None:
        self.calls = 0
        self.envelope = SimpleNamespace(
            tenant=TenantContext(orgId="org-org", projectId="dev-project"),
            checked_at=cutoff,
            sources=[_item(object_type, index, cutoff) for index, object_type in enumerate(_OBJECTS, start=1)],
        )

    def read(self, *, org_id: str, project_id: str):
        self.calls += 1
        assert (org_id, project_id) == ("org-org", "dev-project")
        return self.envelope


def test_reader_reuses_one_current_snapshot_and_never_exposes_failed_or_stale_business_counts() -> None:
    cutoff = datetime(2026, 8, 30, 8, 0, tzinfo=UTC)
    source = _SourceService(cutoff)
    response = EcommerceWorkshopAnalyst(
        reader=EcommerceWorkshopAnalystSourceReader(source),
        clock=lambda: cutoff,
    ).read(org_id="org-org", project_id="dev-project")

    assert source.calls == 1
    by_view = {view.view_id: view for view in response.views}
    assert [(metric.metric_id, metric.value) for metric in by_view[AnalystViewId.OVERVIEW].metrics] == [
        ("order_count", 124.0),
        ("product_count", 57.0),
        ("customer_count", 54.0),
    ]
    assert [(metric.metric_id, metric.value) for metric in by_view[AnalystViewId.DIAGNOSIS].metrics] == [
        ("order_count", 124.0),
        ("order_line_count", 234.0),
        ("customer_count", 54.0),
    ]
    all_business_metric_ids = {metric.metric_id for view in response.views if view.view_id is not AnalystViewId.QUALITY for metric in view.metrics}
    assert "shipment_count" not in all_business_metric_ids
    assert "system_config_count" not in all_business_metric_ids
    assert "payment_count" not in all_business_metric_ids

    quality = by_view[AnalystViewId.QUALITY]
    assert quality.status == "ready"
    assert [(metric.metric_id, metric.value, metric.denominator) for metric in quality.metrics] == [
        ("ready_source_count", 9.0, 12.0),
        ("failed_source_count", 2.0, 12.0),
        ("stale_source_count", 1.0, 12.0),
    ]


def test_observational_views_keep_non_causal_model_and_eval_axes_closed() -> None:
    cutoff = datetime(2026, 8, 30, 8, 0, tzinfo=UTC)
    response = EcommerceWorkshopAnalyst(
        reader=EcommerceWorkshopAnalystSourceReader(_SourceService(cutoff)),
        clock=lambda: cutoff,
    ).read(org_id="org-org", project_id="dev-project")
    by_view = {view.view_id: view for view in response.views}

    assert by_view[AnalystViewId.OVERVIEW].status == "ready"
    for view_id in (AnalystViewId.DRIVERS, AnalystViewId.DIAGNOSIS):
        view = by_view[view_id]
        assert view.status == "blocked"
        assert view.count_ledger.ready == 3
        assert [(axis.axis.value, axis.status.value) for axis in view.readiness_axes] == [
            ("metric_query", "ready"),
            ("model", "blocked"),
            ("eval", "blocked"),
            ("plan_materialization", "not_applicable"),
            ("professional_handoff", "not_applicable"),
        ]
    for view_id in (AnalystViewId.PLAN, AnalystViewId.EFFECTS, AnalystViewId.EVIDENCE):
        assert by_view[view_id].metrics == []
        assert by_view[view_id].status == "blocked"
