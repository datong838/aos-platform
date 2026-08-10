from __future__ import annotations

from aos_api.ontology_display_names import (
    build_object_display_label,
    object_type_display_name,
    relation_type_display_name,
    source_identity_label,
    source_record_label,
)


def test_commerce_object_types_and_relations_are_human_readable() -> None:
    assert object_type_display_name("Order") == "订单"
    assert object_type_display_name("ProductSku") == "商品 SKU"
    assert object_type_display_name("UnknownType") == "UnknownType"
    assert relation_type_display_name("Order.fromWeapp") == "订单来源于小程序"
    assert relation_type_display_name("Unknown.rel") == "Unknown.rel"


def test_business_labels_prefer_safe_real_properties() -> None:
    assert build_object_display_label(
        "Order", "niushop:1:20", {"orderNo": "2026030723225001"}
    ) == "订单 · 2026030723225001"
    assert build_object_display_label(
        "Product", "niushop:1:56", {"title": "秋意系列面膜"}
    ) == "商品 · 秋意系列面膜"
    assert build_object_display_label(
        "Shop", "niushop:1:1", {"name": "栖月汇"}
    ) == "店铺 · 栖月汇"


def test_fallback_is_chinese_source_record_and_does_not_promote_sensitive_values() -> None:
    assert build_object_display_label(
        "Shipment", "niushop:1:3", {"trackingNo": "SF-PRIVATE-001"}
    ) == "发货记录 · 源记录 #3"
    assert build_object_display_label(
        "CustomerLite", "niushop:1:5", {"mobile": "13800000000"}
    ) == "会员 · 源记录 #5"
    assert build_object_display_label(
        "Order", "niushop:1:20", {"orderNo": {"unexpected": "object"}}
    ) == "订单 · 源记录 #20"


def test_source_identity_is_preserved_as_secondary_explanation() -> None:
    assert source_record_label("niushop:1:20") == "源记录 #20"
    assert source_identity_label("niushop:1:20") == "Niushop 微商城 · 站点 1 · 源记录 #20"
    assert source_record_label("opaque-id") == "系统记录 opaque-id"
