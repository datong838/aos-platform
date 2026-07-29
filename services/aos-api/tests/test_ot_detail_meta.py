"""W3-C2 · OT 详情元数据派生单测（无 PG）。"""
from __future__ import annotations

from aos_api.ot_detail_meta import build_ot_detail_meta


def test_build_ot_detail_meta_basic() -> None:
    meta = build_ot_detail_meta(
        type_id="Order",
        name="订单",
        description="demo",
        published=True,
        properties=[{"name": "orderId", "type": "string"}, {"name": "title", "type": "string"}],
        required_markings=["PII"],
        created_at="2026-01-01",
    )
    assert meta["rid"] == "ri.ontology.main.object-type.order"
    assert meta["apiName"] == "Order"
    assert meta["primaryKey"] == "orderId"
    assert meta["titleKey"] == "title"
    assert meta["displayName"] == "订单"
    assert meta["pluralName"] == "订单s"
    assert meta["backingDataset"] == "ds/order"
    assert meta["syncStrategy"] == "incremental"
    assert meta["storageType"] == "object_storage"
    assert meta["createdBy"] == "system"
    assert meta["visibility"] == "PII"
    assert meta["published"] is True


def test_build_ot_detail_meta_empty_props() -> None:
    meta = build_ot_detail_meta(type_id="Site", name="Site", properties=[])
    assert meta["primaryKey"] == "id"
    assert meta["titleKey"] == "id"
    assert meta["pluralName"] == "Sites"
    assert meta["visibility"] == "org"


def test_build_ot_detail_meta_string_props() -> None:
    meta = build_ot_detail_meta(
        type_id="WorkOrder",
        name="WorkOrder",
        properties=["id", "status"],
    )
    assert meta["primaryKey"] == "id"
    assert meta["titleKey"] == "status"
