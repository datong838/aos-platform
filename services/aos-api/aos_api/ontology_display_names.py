"""Human-readable, non-authoritative labels for ontology objects and relations.

Canonical object identifiers remain the only identity used by APIs and graph
edges.  These helpers build a presentation projection from an allow-list of
non-sensitive business fields after field redaction has run.
"""

from __future__ import annotations

from typing import Any, Mapping


OBJECT_TYPE_DISPLAY_NAMES: dict[str, str] = {
    "Order": "订单",
    "OrderLine": "订单明细",
    "Payment": "支付记录",
    "Shipment": "发货记录",
    "Product": "商品",
    "ProductSku": "商品 SKU",
    "Category": "商品类目",
    "CustomerLite": "会员",
    "Shop": "店铺",
    "Weapp": "小程序",
    "ProductReview": "商品评价",
    "SystemConfig": "系统配置",
}

RELATION_TYPE_DISPLAY_NAMES: dict[str, str] = {
    "Order.lines": "订单包含明细",
    "OrderLine.ofSku": "订单明细对应 SKU",
    "OrderLine.ofProduct": "订单明细对应商品",
    "ProductSku.ofProduct": "SKU 属于商品",
    "Product.inCategory": "商品属于类目",
    "Shop.sellsProduct": "店铺销售商品",
    "Order.fulfilledBy": "订单由店铺履约",
    "Order.placedByLite": "订单由会员下单",
    "Shop.hasWeapp": "店铺拥有小程序",
    "Product.hasReview": "商品包含评价",
    "ProductReview.ofSku": "评价对应 SKU",
    "ProductReview.byMember": "评价来自会员",
    "Order.hasPayment": "订单对应支付记录",
    "Order.fromWeapp": "订单来源于小程序",
}

_SAFE_DISPLAY_FIELDS: dict[str, tuple[str, ...]] = {
    "Order": ("orderNo",),
    "Product": ("title",),
    "Category": ("name",),
    "Shop": ("name",),
    "Weapp": ("name",),
    "Payment": ("outTradeNo",),
}


def object_type_display_name(object_type: str) -> str:
    return OBJECT_TYPE_DISPLAY_NAMES.get(object_type, object_type)


def relation_type_display_name(relation_type: str) -> str:
    return RELATION_TYPE_DISPLAY_NAMES.get(relation_type, relation_type)


def _safe_text(value: object) -> str | None:
    if value is None or isinstance(value, (bool, dict, list, tuple, set)):
        return None
    text = str(value).strip()
    if not text or text == "[REDACTED]" or len(text) > 120:
        return None
    return text


def _source_parts(object_id: str) -> tuple[str, str, str] | None:
    parts = object_id.split(":")
    if len(parts) < 3 or parts[0].lower() != "niushop":
        return None
    return parts[0], parts[1], ":".join(parts[2:])


def source_record_label(object_id: str) -> str:
    parts = _source_parts(object_id)
    if parts:
        return f"源记录 #{parts[2]}"
    return f"系统记录 {object_id}"


def source_identity_label(object_id: str) -> str:
    parts = _source_parts(object_id)
    if parts:
        return f"Niushop 微商城 · 站点 {parts[1]} · 源记录 #{parts[2]}"
    return f"系统记录 {object_id}"


def build_object_display_label(
    object_type: str,
    object_id: str,
    properties: Mapping[str, Any] | None,
) -> str:
    props = properties or {}
    business_label = next(
        (
            candidate
            for field in _SAFE_DISPLAY_FIELDS.get(object_type, ())
            if (candidate := _safe_text(props.get(field))) is not None
        ),
        None,
    )
    return f"{object_type_display_name(object_type)} · {business_label or source_record_label(object_id)}"


def build_object_display_projection(
    object_type: str,
    object_id: str,
    properties: Mapping[str, Any] | None,
) -> dict[str, str]:
    return {
        "_displayLabel": build_object_display_label(object_type, object_id, properties),
        "_sourceRecordLabel": source_record_label(object_id),
        "_sourceIdentityLabel": source_identity_label(object_id),
    }
