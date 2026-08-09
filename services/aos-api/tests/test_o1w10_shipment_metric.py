"""O1-W10 P07 Shipment 权威履约指标合同。"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aos_api.ec_derived_metrics import apply_derived_metrics
from aos_api.ec_ot_writer import _build_object
from aos_api.ec_source_adapter import BATCH_READ_SPECS, BatchReadSpec
from aos_api.ecom_core_models import SyncScope
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
SYNC_SCOPE = SyncScope(
    org_id="org-org",
    workspace_id="dev-project",
    platform="niushop",
    shop_or_marketplace_id="1",
    stream="P07-shipment-qyh",
)


def _p07_graph() -> tuple[SimpleNamespace, list[SimpleNamespace]]:
    pipeline = SimpleNamespace(id="P07-shipment-qyh", config={"target_ot": "Shipment"})
    nodes = [
        SimpleNamespace(
            id="source",
            node_type="source",
            config={"source_id": "niushop-qyh", "source_table": "ns_express_delivery_package"},
        )
    ]
    return pipeline, nodes


def test_shipment_order_timing_batch_spec_is_frozen() -> None:
    assert BATCH_READ_SPECS["shipment_order_timing"] == BatchReadSpec(
        table="ns_order",
        columns=("order_id", "pay_time"),
        filter_column="order_id",
    )


@patch("aos_api.ec_live_executor.batch_read_public")
def test_shipment_enrichment_uses_current_source_before_normalize(
    batch_read: MagicMock,
) -> None:
    from aos_api.ec_live_executor import _enrich_shipment_order_pay_time

    pipeline, nodes = _p07_graph()
    rows = [{"id": 1, "order_id": 7, "delivery_time": 300}]
    batch_read.return_value = [{"order_id": 7, "pay_time": 100}]

    _enrich_shipment_order_pay_time(
        pipeline=pipeline,
        nodes=nodes,
        node_id=None,
        scope=SCOPE,
        rows=rows,
    )

    assert rows[0]["_order_pay_time"] == 100
    batch_read.assert_called_once_with(
        pipeline=pipeline,
        nodes=nodes,
        node_id=None,
        scope=SCOPE,
        spec_id="shipment_order_timing",
        filter_values=("7",),
    )


def test_delivered_shipment_has_actual_overdue_duration() -> None:
    paid_at = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    delivered_at = datetime(2026, 1, 4, tzinfo=timezone.utc).timestamp()
    row = {
        "ot": "Shipment",
        "source_pk": "1",
        "delivery_time": delivered_at,
        "_order_pay_time": paid_at,
        "properties": {},
    }
    pipeline, _ = _p07_graph()

    result = apply_derived_metrics([row], pipeline)

    assert result[0]["properties"]["overdue_hours"] == 24.0


def test_all_derived_metrics_are_removed_from_base_object_payload() -> None:
    row = {
        "ot": "Shipment",
        "source_pk": "1",
        "source_updated_at": datetime(2026, 1, 4, tzinfo=timezone.utc),
        "source_timezone": "Asia/Shanghai",
        "delivery_time": datetime(2026, 1, 4, tzinfo=timezone.utc).timestamp(),
        "properties": {
            "orderId": "7",
            "status": "active",
            "carrier": "x",
            "trackingNo": "y",
            "overdue_hours": 24.0,
        },
    }

    obj = _build_object(row, SYNC_SCOPE)

    assert obj is not None
    assert "overdue_hours" not in obj.properties
