"""D1.5: CustomerLite OT 契约扩展专项测试（FR-D1.5-1）。

验证 ecom_core_models 扩展：
1. CORE_OBJECT_TYPES 加入 CustomerLite
2. CORE_LINK_TYPES 加入 Order.placedByLite，方向 Order → CustomerLite
3. REQUIRED_PROPERTIES["CustomerLite"] 包含 memberLevel/status/createdAt/updatedAt
4. CoreObjectRecord 支持 CustomerLite 类型构造（含必填属性补齐）
5. CoreLinkRecord 支持 Order.placedByLite 构造（含跨租户拒绝）
6. 向后兼容：既有 7 OT 字段定义未修改（最小更改）

约束（与 frozen/02 §P08 一致）：
- CustomerLite 不引入 PII 字段（mobile/wx_openid/nickname/avatar 等禁止）
- placedByLite 的 source_type=Order, target_type=CustomerLite
- 与 D1 7 OT 契约共存，不破坏既有定义
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aos_api.ecom_core_models import (
    CORE_LINK_TYPES,
    CORE_OBJECT_TYPES,
    REQUIRED_PROPERTIES,
    CoreLinkRecord,
    CoreObjectRecord,
)
from aos_api.public_contracts import ExternalIdentityKey, ForwardEnumValue

NOW = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════
# 1. CORE_OBJECT_TYPES 扩展（FR-D1.5-1）
# ═══════════════════════════════════════════════


def test_CORE_OBJECT_TYPES_contains_CustomerLite() -> None:
    """FR-D1.5-1: CustomerLite MUST 存在于 CORE_OBJECT_TYPES。"""
    assert "CustomerLite" in CORE_OBJECT_TYPES


def test_CORE_OBJECT_TYPES_preserves_existing_7_ots() -> None:
    """FR-D1.5-1 最小更改：既有 7 OT 不变。"""
    expected = {
        "Shop", "Product", "ProductSku", "Category",
        "Order", "OrderLine", "Shipment",
    }
    assert expected.issubset(CORE_OBJECT_TYPES)


def test_CORE_OBJECT_TYPES_now_has_8_ots() -> None:
    """FR-D1.5-1: 扩展后 CORE_OBJECT_TYPES 共 8 个 OT。"""
    assert len(CORE_OBJECT_TYPES) == 8


# ═══════════════════════════════════════════════
# 2. CORE_LINK_TYPES 扩展（FR-D1.5-1）
# ═══════════════════════════════════════════════


def test_CORE_LINK_TYPES_contains_Order_placedByLite() -> None:
    """FR-D1.5-1: Order.placedByLite MUST 存在于 CORE_LINK_TYPES。"""
    assert "Order.placedByLite" in CORE_LINK_TYPES


def test_CORE_LINK_TYPES_placedByLite_direction_is_Order_to_CustomerLite() -> None:
    """FR-D1.5-1: placedByLite 方向是 Order → CustomerLite（与 frozen/02 §P08 一致）。"""
    assert CORE_LINK_TYPES["Order.placedByLite"] == ("Order", "CustomerLite")


def test_CORE_LINK_TYPES_preserves_existing_6_links() -> None:
    """FR-D1.5-1 最小更改：既有 6 条核心 Link 不变。"""
    expected = {
        "Order.lines",
        "OrderLine.ofSku",
        "OrderLine.ofProduct",
        "ProductSku.ofProduct",
        "Product.inCategory",
        "Shop.sellsProduct",
        "Order.fulfilledBy",
    }
    assert expected.issubset(CORE_LINK_TYPES.keys())


# ═══════════════════════════════════════════════
# 3. REQUIRED_PROPERTIES["CustomerLite"] 扩展（FR-D1.5-1）
# ═══════════════════════════════════════════════


def test_REQUIRED_PROPERTIES_has_CustomerLite_entry() -> None:
    """FR-D1.5-1: REQUIRED MUST 有 CustomerLite 条目。"""
    assert "CustomerLite" in REQUIRED_PROPERTIES


def test_REQUIRED_PROPERTIES_CustomerLite_contains_minimum_fields() -> None:
    """FR-D1.5-1: CustomerLite 必填字段含 memberLevel/status/createdAt/updatedAt。"""
    required = REQUIRED_PROPERTIES["CustomerLite"]
    assert "memberLevel" in required
    assert "status" in required
    assert "createdAt" in required
    assert "updatedAt" in required


def test_REQUIRED_PROPERTIES_CustomerLite_excludes_PII_fields() -> None:
    """FR-D1.5-1 PII 零泄漏：CustomerLite 必填字段不含 mobile/nickname/openid/avatar 等敏感字段。"""
    required = REQUIRED_PROPERTIES["CustomerLite"]
    pii_fields = {
        "mobile", "phone", "wxOpenid", "wx_openid", "openid",
        "nickname", "avatar", "regAddress", "reg_address",
        "password", "payPassword", "pay_password",
        "lastLoginIp", "last_login_ip",
    }
    leaked = pii_fields & required
    assert not leaked, f"CustomerLite 必填字段含 PII: {leaked}"


def test_REQUIRED_PROPERTIES_preserves_existing_7_ots_fields() -> None:
    """FR-D1.5-1 最小更改：既有 7 OT 的 REQUIRED_PROPERTIES 不变。"""
    assert REQUIRED_PROPERTIES["Shop"] == frozenset(
        {"name", "status", "currency", "timezone"}
    )
    assert REQUIRED_PROPERTIES["Product"] == frozenset(
        {"shopId", "title", "status", "categoryId", "createdAt", "updatedAt"}
    )
    assert REQUIRED_PROPERTIES["Order"] == frozenset(
        {"shopId", "status", "totalAmount", "currency", "createdAt", "updatedAt"}
    )
    assert REQUIRED_PROPERTIES["Shipment"] == frozenset(
        {"orderId", "status", "carrier", "trackingNo", "shippedAt", "updatedAt"}
    )


# ═══════════════════════════════════════════════
# 4. CoreObjectRecord 支持 CustomerLite 构造（FR-D1.5-1）
# ═══════════════════════════════════════════════


def _make_identity(external_id: str = "niushop:1:m-1") -> ExternalIdentityKey:
    return ExternalIdentityKey(
        org_id="org-org",
        workspace_id="dev-project",
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id=external_id,
    )


def _customer_lite_properties() -> dict:
    """CustomerLite 最小必填属性（无 PII）。"""
    return {
        "memberLevel": "1",
        "status": "active",
        "createdAt": "2026-01-01T00:00:00+08:00",
        "updatedAt": "2026-07-31T18:00:00+08:00",
    }


def test_CoreObjectRecord_accepts_CustomerLite() -> None:
    """FR-D1.5-1: CoreObjectRecord MUST 接受 CustomerLite 类型构造。"""
    record = CoreObjectRecord(
        identity=_make_identity(),
        object_type="CustomerLite",
        source_updated_at=NOW,
        source_timezone="+00:00",
        status=ForwardEnumValue.from_raw("ACTIVE", {"ACTIVE": "active", "DELETED": "deleted"}),
        properties=_customer_lite_properties(),
    )
    assert record.object_type == "CustomerLite"
    assert record.identity.external_id == "niushop:1:m-1"


def test_CoreObjectRecord_CustomerLite_normalizes_At_time_fields() -> None:
    """FR-D1.5-1: CustomerLite 的 createdAt/updatedAt MUST 被 ZonedInstant 规范化。"""
    record = CoreObjectRecord(
        identity=_make_identity(),
        object_type="CustomerLite",
        source_updated_at=NOW,
        source_timezone="+00:00",
        status=ForwardEnumValue.from_raw("ACTIVE", {"ACTIVE": "active", "DELETED": "deleted"}),
        properties={
            "memberLevel": "1",
            "status": "active",
            "createdAt": "2026-01-01T00:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    )
    # ZonedInstant 规范化后 createdAt 变为 UTC ISO 字符串
    assert record.properties["createdAt"].endswith("Z") or "+" in record.properties["createdAt"]
    # 必须存在 source_timezone 后缀字段
    assert "createdAtSourceTimezone" in record.properties
    assert "updatedAtSourceTimezone" in record.properties


def test_CoreObjectRecord_CustomerLite_rejects_missing_required_field() -> None:
    """FR-D1.5-1: CustomerLite 缺失必填字段 MUST 抛 ValueError。"""
    incomplete_props = dict(_customer_lite_properties())
    del incomplete_props["memberLevel"]
    with pytest.raises(ValueError, match="missing required properties for CustomerLite"):
        CoreObjectRecord(
            identity=_make_identity(),
            object_type="CustomerLite",
            source_updated_at=NOW,
            source_timezone="+00:00",
            status=ForwardEnumValue.from_raw("ACTIVE", {"ACTIVE": "active", "DELETED": "deleted"}),
            properties=incomplete_props,
        )


# ═══════════════════════════════════════════════
# 5. CoreLinkRecord 支持 Order.placedByLite 构造（FR-D1.5-1）
# ═══════════════════════════════════════════════


def test_CoreLinkRecord_accepts_Order_placedByLite() -> None:
    """FR-D1.5-1: CoreLinkRecord MUST 接受 Order.placedByLite link_type。"""
    order_identity = _make_identity(external_id="niushop:1:o-1")
    customer_lite_identity = _make_identity(external_id="niushop:1:m-1")
    link = CoreLinkRecord(
        link_type="Order.placedByLite",
        source_type="Order",
        source=order_identity,
        target_type="CustomerLite",
        target=customer_lite_identity,
        source_updated_at=NOW,
        cursor_external_id="niushop:1:o-1",
    )
    assert link.link_type == "Order.placedByLite"
    assert link.source_type == "Order"
    assert link.target_type == "CustomerLite"


def test_CoreLinkRecord_placedByLite_rejects_wrong_direction() -> None:
    """FR-D1.5-1: placedByLite 方向必须是 Order → CustomerLite，反向 MUST 抛 ValueError。"""
    order_identity = _make_identity(external_id="niushop:1:o-1")
    customer_lite_identity = _make_identity(external_id="niushop:1:m-1")
    with pytest.raises(ValueError, match="requires Order -> CustomerLite"):
        CoreLinkRecord(
            link_type="Order.placedByLite",
            source_type="CustomerLite",
            source=customer_lite_identity,
            target_type="Order",
            target=order_identity,
            source_updated_at=NOW,
            cursor_external_id="niushop:1:m-1",
        )


def test_CoreLinkRecord_placedByLite_rejects_cross_tenant() -> None:
    """FR-D1.5-1: placedByLite 跨租户 Link MUST 抛 ValueError（fail-closed）。"""
    order_identity = _make_identity(external_id="niushop:1:o-1")
    # 不同 workspace 的 CustomerLite
    cross_tenant_customer = ExternalIdentityKey(
        org_id="org-org",
        workspace_id="other-project",  # 跨 workspace
        platform="niushop",
        shop_or_marketplace_id="1",
        external_id="niushop:1:m-1",
    )
    with pytest.raises(ValueError, match="cross-tenant links are forbidden"):
        CoreLinkRecord(
            link_type="Order.placedByLite",
            source_type="Order",
            source=order_identity,
            target_type="CustomerLite",
            target=cross_tenant_customer,
            source_updated_at=NOW,
            cursor_external_id="niushop:1:o-1",
        )


def test_CoreLinkRecord_placedByLite_rejects_unknown_link_type() -> None:
    """FR-D1.5-1: 未知 link_type MUST 抛 ValueError（不支持自造 Link 名）。"""
    order_identity = _make_identity(external_id="niushop:1:o-1")
    customer_lite_identity = _make_identity(external_id="niushop:1:m-1")
    with pytest.raises(ValueError, match="unsupported core link type"):
        CoreLinkRecord(
            link_type="Order.placedBy",  # 故意写错名
            source_type="Order",
            source=order_identity,
            target_type="CustomerLite",
            target=customer_lite_identity,
            source_updated_at=NOW,
            cursor_external_id="niushop:1:o-1",
        )


# ═══════════════════════════════════════════════
# 6. 向后兼容：既有 7 OT 仍能构造（最小更改）
# ═══════════════════════════════════════════════


def test_existing_Shop_OT_still_constructible() -> None:
    """FR-D1.5-1 最小更改：Shop OT 仍可构造（不破坏既有契约）。"""
    record = CoreObjectRecord(
        identity=_make_identity(external_id="niushop:1:1"),
        object_type="Shop",
        source_updated_at=NOW,
        source_timezone="+00:00",
        status=ForwardEnumValue.from_raw("ACTIVE", {"ACTIVE": "active", "DELETED": "deleted"}),
        properties={
            "name": "测试店铺",
            "status": "active",
            "currency": "CNY",
            "timezone": "Asia/Shanghai",
        },
    )
    assert record.object_type == "Shop"


def test_existing_Order_fulfilledBy_link_still_constructible() -> None:
    """FR-D1.5-1 最小更改：既有 Order.fulfilledBy Link 仍可构造。"""
    order_identity = _make_identity(external_id="niushop:1:o-1")
    shipment_identity = _make_identity(external_id="niushop:1:sh-1")
    link = CoreLinkRecord(
        link_type="Order.fulfilledBy",
        source_type="Order",
        source=order_identity,
        target_type="Shipment",
        target=shipment_identity,
        source_updated_at=NOW,
        cursor_external_id="niushop:1:o-1",
    )
    assert link.link_type == "Order.fulfilledBy"
