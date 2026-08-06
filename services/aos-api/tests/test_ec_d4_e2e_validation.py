"""D4 Phase A: 端到端验证 — 12 OT + 15 Link + 8 派生指标（A4）。

验证 D1/D1.5/D4 三波累积的全链路完整性（改动清单 A4-1）：
1. 12 OT 实例数验证：D1(8) + D1.5(1) + D4(3) = 12 OT，各构造 1 条实例，
   全部通过 REQUIRED_PROPERTIES 校验（CoreObjectRecord.validate_core_shape）。
2. 15 条 Link 完整性验证：D1(7) + D1.5(1) + D4(7，含 Product.inCategory 重断言) = 15，
   实际 unique 14（Product.inCategory 在 D1/D4 双重断言）。
   CORE_LINK_TYPES >= 14（注册 superset）；build_link_rows 构造 13 条可构造 Link
   （Shop.sellsProduct 无 builder，注册断言 + 手动构造验证覆盖）。
3. 8 派生指标非空验证：D1(4) + D1.5(2) + D4(2) = 8，
   apply_derived_metrics 后非 null 占比 >= 80%（G4）。
   review_quality_bucket 边界值: 3.0→low / 4.5→high / 4.0→mid。
   pay_duration_min 跨表关联: _order_create_time 存在→分钟差, 缺失→null。

mock 策略（照搬 D1 端到端 test_ec_d1_e2e_link_landing.py）：
- FakeStore + FakeEngine（模拟一致性内核，不连 PostgreSQL）
- 不连 MySQL，直接调 build_link_rows + sink_to_ot + apply_derived_metrics
- 12 条管道 P01~P12 的 5 节点 graph 配置工厂内嵌
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from aos_api.ec_derived_metrics import apply_derived_metrics
from aos_api.ec_link_builder import build_link_rows
from aos_api.ecom_core_models import (
    BatchCommand,
    BatchResult,
    CORE_LINK_TYPES,
    CORE_OBJECT_TYPES,
    REQUIRED_PROPERTIES,
)
from aos_api.ec_ot_writer import sink_to_ot
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)
NOW_TS = int(NOW.timestamp())
# 远过去时间戳（确保 overdue_hours 非空，_now_utc 真实时间也无影响）
PAST_TS = 1700000000  # 2023-11-14 22:13:20 UTC
TEST_SCOPE = TenantScope("dev-org", "dev-project")


# ═══════════════════════════════════════════════
# 期望集
# ═══════════════════════════════════════════════

# 12 OT（D1 8 + D1.5 1 + D4 3 = 12）
EXPECTED_12_OTS = frozenset({
    "Shop", "Product", "ProductSku", "Category",
    "Order", "OrderLine", "Shipment",
    "CustomerLite",  # D1.5
    "Weapp", "SystemConfig", "ProductReview", "Payment",  # D4
})

# 14 unique Link（D1 7 + D1.5 1 + D4 6 = 14）
# "15 条"含 Product.inCategory 在 D1/D4 双重断言（计数 15，实际 unique 14）
EXPECTED_LINK_TYPES = frozenset({
    # D1 (7)
    "Order.lines", "OrderLine.ofSku", "OrderLine.ofProduct",
    "ProductSku.ofProduct", "Product.inCategory",
    "Shop.sellsProduct", "Order.fulfilledBy",
    # D1.5 (1)
    "Order.placedByLite",
    # D4 (6 new；Product.inCategory 已在 D1 注册，不重复计入 unique)
    "Shop.hasWeapp", "Product.hasReview", "ProductReview.ofSku",
    "ProductReview.byMember", "Order.hasPayment", "Order.fromWeapp",
})

# 8 派生指标（D1 4 + D1.5 2 + D4 2 = 8）
EXPECTED_DERIVED_METRICS = frozenset({
    # D1 (4)
    "quality_score", "stock_health", "risk_score", "overdue_hours",
    # D1.5 (2)
    "order_count", "last_order_days",
    # D4 (2)
    "review_quality_bucket", "pay_duration_min",
})


# ═══════════════════════════════════════════════
# FakeStore + FakeEngine（照搬 test_ec_d1_e2e_link_landing.py）
# ═══════════════════════════════════════════════


class FakeStore:
    """记录 apply_batch / get_checkpoint 调用，模拟一致性内核行为。

    默认行为：objects_written / links_written = batch 内计数，checkpoint
    版本自增（模拟真实 store 的 CAS 推进）。
    """

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[BatchCommand] = []
        self._raises = raises
        self._checkpoints: dict[tuple, int] = {}

    def apply_batch(self, command: BatchCommand) -> BatchResult:
        self.calls.append(command)
        if self._raises is not None:
            raise self._raises
        key = command.scope.key()
        if key not in self._checkpoints:
            self._checkpoints[key] = 0
        self._checkpoints[key] += 1
        return BatchResult(
            objects_written=len(command.objects),
            links_written=len(command.links),
            checkpoint_version=self._checkpoints[key],
            checkpoint=command.next_checkpoint,
        )

    def get_checkpoint(self, command: BatchCommand) -> dict | None:
        version = self._checkpoints.get(command.scope.key())
        if version is None:
            return None
        return {"version": version}


class FakeEngine:
    """带 ecom_consistency_store 属性的 fake engine。"""

    def __init__(self, store: FakeStore) -> None:
        self.ecom_consistency_store = store


# ═══════════════════════════════════════════════
# 管道配置工厂（12 条管道 P01~P12 的 5 节点 graph）
# ═══════════════════════════════════════════════


# P01~P12 源表 → OT 映射
_PIPELINE_SPECS: dict[str, dict[str, str]] = {
    "p01": {"target_ot": "Shop", "source_table": "ns_site", "primary_key": "site_id"},
    "p02": {"target_ot": "Product", "source_table": "ns_goods", "primary_key": "goods_id"},
    "p03": {"target_ot": "ProductSku", "source_table": "ns_goods_sku", "primary_key": "sku_id"},
    "p04": {"target_ot": "Category", "source_table": "ns_goods_category", "primary_key": "category_id"},
    "p05": {"target_ot": "Order", "source_table": "ns_order", "primary_key": "order_id"},
    "p06": {"target_ot": "OrderLine", "source_table": "ns_order_goods", "primary_key": "id"},
    "p07": {"target_ot": "Shipment", "source_table": "ns_express_delivery_package", "primary_key": "id"},
    "p08": {"target_ot": "CustomerLite", "source_table": "ns_member", "primary_key": "member_id"},
    "p09": {"target_ot": "Weapp", "source_table": "ns_weapp", "primary_key": "weapp_id"},
    "p10": {"target_ot": "SystemConfig", "source_table": "ns_config", "primary_key": "id"},
    "p11": {"target_ot": "ProductReview", "source_table": "ns_goods_evaluate", "primary_key": "id"},
    "p12": {"target_ot": "Payment", "source_table": "ns_pay", "primary_key": "id"},
}


def define_pipeline_config(pid: str) -> dict:
    """构造 5 节点 graph 管道配置（source→normalize→validate→quality_gate→sink）。"""
    spec = _PIPELINE_SPECS[pid]
    target_ot = spec["target_ot"]
    source_table = spec["source_table"]
    primary_key = spec["primary_key"]
    return {
        "id": pid,
        "sourceId": f"niushop-{source_table}",
        "name": f"{pid} {target_ot} Pipeline",
        "objectTypeHint": target_ot,
        "config": {
            "target_ot": target_ot,
            "source_table": source_table,
            "primary_key": primary_key,
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": f"niushop-{source_table}",
                    "source_table": source_table,
                    "primary_key": primary_key,
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {"target_ot": target_ot},
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {"target_ot": target_ot},
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {"target_ot": target_ot},
            },
            {
                "id": "sink",
                "name": "Sink",
                "type": "sink",
                "config": {"target_ot": target_ot},
            },
        ],
        "edges": [
            {"source": "source", "target": "normalize"},
            {"source": "normalize", "target": "validate"},
            {"source": "validate", "target": "quality_gate"},
            {"source": "quality_gate", "target": "sink"},
        ],
    }


def _make_pipeline(pid: str, target_ot: str | None = None) -> SimpleNamespace:
    """构造 pipeline SimpleNamespace（config.target_ot 优先）。"""
    if target_ot is None:
        target_ot = _PIPELINE_SPECS[pid]["target_ot"]
    return SimpleNamespace(id=pid, config={"target_ot": target_ot})


# ═══════════════════════════════════════════════
# 12 OT row 工厂（含全部 REQUIRED_PROPERTIES + 派生指标源字段）
# ═══════════════════════════════════════════════


def _shop_row() -> dict:
    """P01 Shop 行（REQUIRED: name/status/currency/timezone）。"""
    return {
        "ot": "Shop",
        "source_pk": "1",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "name": "栖月汇旗舰店",
            "status": "active",
            "currency": "CNY",
            "timezone": "Asia/Shanghai",
        },
    }


def _product_row() -> dict:
    """P02 Product 行（REQUIRED: shopId/title/status/categoryId/createdAt/updatedAt）。

    含派生指标源字段 evaluate/evaluate_haoping → quality_score。
    categoryId → 构造 Product.inCategory Link。
    """
    return {
        "ot": "Product",
        "source_pk": "g-1",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "shopId": "1",
            "title": "测试商品A",
            "status": "active",
            "categoryId": "c-1",
            "createdAt": "2026-07-01T00:00:00+08:00",
            "updatedAt": "2026-08-06T10:00:00+08:00",
            # 派生指标源字段
            "evaluate": 10,
            "evaluate_haoping": 9,
        },
    }


def _sku_row() -> dict:
    """P03 ProductSku 行（REQUIRED: productId/status/barcode/price/currency/updatedAt）。

    含派生指标源字段 stock/goods_stock_alarm → stock_health。
    productId → 构造 ProductSku.ofProduct Link。
    """
    return {
        "ot": "ProductSku",
        "source_pk": "s-1",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "productId": "g-1",
            "status": "active",
            "barcode": "BC-001",
            "price": "99.00",
            "currency": "CNY",
            "updatedAt": "2026-08-06T10:00:00+08:00",
            # 派生指标源字段
            "stock": 100,
            "goods_stock_alarm": 10,
        },
    }


def _category_row() -> dict:
    """P04 Category 行（REQUIRED: parentCategoryId/name/status/updatedAt）。"""
    return {
        "ot": "Category",
        "source_pk": "c-1",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "parentCategoryId": "0",
            "name": "测试分类",
            "status": "active",
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }


def _order_row() -> dict:
    """P05 Order 行（REQUIRED: shopId/status/totalAmount/currency/createdAt/updatedAt）。

    含派生指标源字段 commission_risk_flag/refund_status/is_lock/order_status/pay_status/create_time
    → risk_score。
    memberId → 构造 Order.placedByLite Link。
    weapp_id（顶层）→ 构造 Order.fromWeapp Link。
    """
    return {
        "ot": "Order",
        "source_pk": "o-1",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        # 顶层 weapp_id → Order.fromWeapp Link
        "weapp_id": "wx_001",
        "properties": {
            "shopId": "1",
            "status": "active",
            "totalAmount": "199.00",
            "currency": "CNY",
            "createdAt": "2026-08-01T00:00:00+08:00",
            "updatedAt": "2026-08-06T10:00:00+08:00",
            # memberId → Order.placedByLite Link
            "memberId": "m-1",
            # 派生指标源字段
            "commission_risk_flag": 1,
            "refund_status": 0,
            "is_lock": 0,
            "order_status": 1,
            "pay_status": 1,
            "create_time": NOW_TS,
        },
    }


def _orderline_row() -> dict:
    """P06 OrderLine 行（REQUIRED: orderId/skuId/quantity/unitPrice/lineAmount/currency/updatedAt）。

    goodsId（额外字段，非 REQUIRED）→ 构造 OrderLine.ofProduct Link。
    orderId → 构造 Order.lines Link。
    skuId → 构造 OrderLine.ofSku Link。
    """
    return {
        "ot": "OrderLine",
        "source_pk": "og-1",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "orderId": "o-1",
            "skuId": "s-1",
            "goodsId": "g-1",
            "quantity": 2,
            "unitPrice": "99.00",
            "lineAmount": "198.00",
            "currency": "CNY",
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }


def _shipment_row() -> dict:
    """P07 Shipment 行（REQUIRED: orderId/status/carrier/trackingNo/shippedAt/updatedAt）。

    含派生指标源字段 delivery_time/pay_time → overdue_hours。
    orderId → 构造 Order.fulfilledBy Link。
    """
    return {
        "ot": "Shipment",
        "source_pk": "sh-1",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "orderId": "o-1",
            "status": "pending",
            "carrier": "SF",
            "trackingNo": "SF123456",
            "shippedAt": "2026-08-06T10:00:00+08:00",
            "updatedAt": "2026-08-06T10:00:00+08:00",
            # 派生指标源字段：未发货 + 已支付 → overdue_hours 非空
            "delivery_time": 0,
            "pay_time": PAST_TS,
        },
    }


def _customer_lite_row() -> dict:
    """P08 CustomerLite 行（REQUIRED: memberLevel/status/createdAt/updatedAt）。

    派生指标 order_count/last_order_days 需 link_aggregator 注入（D1.5 跨表聚合）。
    """
    return {
        "ot": "CustomerLite",
        "source_pk": "m-1",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "memberLevel": "1",
            "status": "active",
            "createdAt": "2026-01-01T00:00:00+08:00",
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }


def _weapp_row() -> dict:
    """P09 Weapp 行（REQUIRED: appId/name/status/updatedAt）。

    site_id（顶层）→ 构造 Shop.hasWeapp Link。
    """
    return {
        "ot": "Weapp",
        "source_pk": "wx_001",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "site_id": "1",
        "properties": {
            "appId": "wx1234567890abcdef",
            "name": "栖月汇小程序",
            "status": "active",
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }


def _config_row() -> dict:
    """P10 SystemConfig 行（REQUIRED: siteId/module/key/updatedAt）。"""
    return {
        "ot": "SystemConfig",
        "source_pk": "cfg_001",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "siteId": "1",
            "module": "shop",
            "key": "pay_key",
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }


def _review_row() -> dict:
    """P11 ProductReview 行（REQUIRED: productId/memberId/score/updatedAt）。

    含派生指标源字段 score → review_quality_bucket。
    sku_id（顶层）→ 构造 ProductReview.ofSku Link。
    productId → 构造 Product.hasReview Link。
    memberId → 构造 ProductReview.byMember Link。
    """
    return {
        "ot": "ProductReview",
        "source_pk": "rev_001",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "sku_id": "s-1",
        "properties": {
            "productId": "g-1",
            "memberId": "m-1",
            "score": "4.5",
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }


def _payment_row() -> dict:
    """P12 Payment 行（REQUIRED: orderId/outTradeNo/payStatus/updatedAt）。

    含派生指标源字段 pay_time/_order_create_time → pay_duration_min。
    orderId → 构造 Order.hasPayment Link。
    """
    return {
        "ot": "Payment",
        "source_pk": "pay_001",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        # 派生指标源字段（顶层，供 _apply_pay_duration_min 读取）
        "pay_time": NOW_TS + 600,  # 10 分钟后支付
        "_order_create_time": NOW_TS,
        "properties": {
            "orderId": "o-1",
            "outTradeNo": "otn_001",
            "payStatus": "2",
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }


# 12 OT row 工厂列表（有序，与 EXPECTED_12_OTS 对齐）
ALL_12_OT_ROWS: list[tuple[str, str, dict]] = [
    ("p01", "Shop", _shop_row()),
    ("p02", "Product", _product_row()),
    ("p03", "ProductSku", _sku_row()),
    ("p04", "Category", _category_row()),
    ("p05", "Order", _order_row()),
    ("p06", "OrderLine", _orderline_row()),
    ("p07", "Shipment", _shipment_row()),
    ("p08", "CustomerLite", _customer_lite_row()),
    ("p09", "Weapp", _weapp_row()),
    ("p10", "SystemConfig", _config_row()),
    ("p11", "ProductReview", _review_row()),
    ("p12", "Payment", _payment_row()),
]

# 有 build_link_rows builder 的 OT 列表（不含 Shop/Category/SystemConfig/CustomerLite，无 builder）
OTS_WITH_LINK_BUILDERS: list[tuple[str, str, dict]] = [
    ("p02", "Product", _product_row()),        # → Product.inCategory
    ("p03", "ProductSku", _sku_row()),          # → ProductSku.ofProduct
    ("p06", "OrderLine", _orderline_row()),     # → Order.lines + OrderLine.ofProduct + OrderLine.ofSku
    ("p07", "Shipment", _shipment_row()),       # → Order.fulfilledBy
    ("p05", "Order", _order_row()),             # → Order.placedByLite + Order.fromWeapp
    ("p09", "Weapp", _weapp_row()),             # → Shop.hasWeapp
    ("p11", "ProductReview", _review_row()),    # → Product.hasReview + ProductReview.ofSku + ProductReview.byMember
    ("p12", "Payment", _payment_row()),         # → Order.hasPayment
]


# ═══════════════════════════════════════════════
# Section 0: 管道配置工厂验证
# ═══════════════════════════════════════════════


def test_d4_e2e_12_pipeline_configs_generated():
    """12 条管道 P01~P12 的 5 节点 graph 全部可生成。"""
    for pid in _PIPELINE_SPECS:
        cfg = define_pipeline_config(pid)
        assert cfg["config"]["target_ot"] in CORE_OBJECT_TYPES
        assert len(cfg["nodes"]) == 5  # source→normalize→validate→quality_gate→sink
        assert len(cfg["edges"]) == 4


# ═══════════════════════════════════════════════
# Section 1: 12 OT 实例数验证
# ═══════════════════════════════════════════════


def test_d4_e2e_12_ot_all_registered_in_core_object_types():
    """12 OT 全部注册到 CORE_OBJECT_TYPES（跨波累积契约，subset 断言）。

    D1(8) + D1.5(1) + D4(3) = 12 OT。
    """
    assert CORE_OBJECT_TYPES >= EXPECTED_12_OTS
    assert len(CORE_OBJECT_TYPES) >= 12


def test_d4_e2e_12_ot_required_properties_keys_match():
    """REQUIRED_PROPERTIES 的 key 集合与 CORE_OBJECT_TYPES 完全对齐。"""
    assert set(REQUIRED_PROPERTIES.keys()) == set(CORE_OBJECT_TYPES)
    assert len(REQUIRED_PROPERTIES) >= 12


def test_d4_e2e_12_ot_instances_pass_required_properties():
    """12 OT 各构造 1 条实例，经 sink_to_ot → CoreObjectRecord.validate_core_shape 全部通过。

    每个 OT 的 properties 含全部 REQUIRED_PROPERTIES[ot]。
    sink_to_ot 内部构造 CoreObjectRecord 并执行 validate_core_shape（含
    REQUIRED_PROPERTIES 缺失检查），通过 = 无 ValueError。
    """
    store = FakeStore()
    eng = FakeEngine(store)

    for pid, ot, row in ALL_12_OT_ROWS:
        pipeline = _make_pipeline(pid, ot)
        result = sink_to_ot(eng, TEST_SCOPE, pipeline, [row])
        assert result["objects_written"] == 1, f"{ot} 实例未通过 REQUIRED_PROPERTIES 校验"

    # 12 次 apply_batch 调用，每次 1 个 OT 实例
    assert len(store.calls) == 12
    landed_ots = {obj.object_type for call in store.calls for obj in call.objects}
    assert landed_ots >= EXPECTED_12_OTS


# ═══════════════════════════════════════════════
# Section 2: 15 条 Link 完整性验证
# ═══════════════════════════════════════════════


def test_d4_e2e_core_link_types_contains_all_expected():
    """CORE_LINK_TYPES 至少含 14 条期望 Link（subset 断言，不破坏跨波累积）。

    "15 条"含 Product.inCategory 在 D1/D4 双重断言（计数 15，实际 unique 14）。
    """
    assert set(CORE_LINK_TYPES.keys()) >= EXPECTED_LINK_TYPES
    assert len(CORE_LINK_TYPES) >= 14


def test_d4_e2e_build_link_rows_constructs_all_links():
    """build_link_rows 构造全部可构造 Link（13 条，Shop.sellsProduct 无 builder）。

    对每个有 builder 的 OT 构造 1 行 → build_link_rows → 收集 link_types。
    期望 13 条可构造 Link（14 unique - Shop.sellsProduct 无 builder = 13）。
    """
    all_link_types: set[str] = set()
    total_link_rows = 0
    for pid, target_ot, row in OTS_WITH_LINK_BUILDERS:
        pipeline = _make_pipeline(pid, target_ot)
        rows = build_link_rows([row], pipeline)
        links = [r for r in rows if "link_type" in r]
        for link in links:
            all_link_types.add(link["link_type"])
            total_link_rows += 1

    # 13 条可构造 Link（Shop.sellsProduct 无 builder）
    constructable = EXPECTED_LINK_TYPES - {"Shop.sellsProduct"}
    assert all_link_types >= constructable, (
        f"build_link_rows 缺少 Link: {constructable - all_link_types}"
    )
    # 总 Link 行数 >= 13（每行至少 1 条 Link，OrderLine/ProductReview 各 3 条）
    assert total_link_rows >= 13


def test_d4_e2e_all_links_land_via_sink_to_ot():
    """构造的 Link 行经 sink_to_ot → CoreLinkRecord.validate_link 全部通过。

    对每个有 builder 的 OT：build_link_rows → sink_to_ot，
    验证 CoreLinkRecord 构造无异常（link_type + 方向 + 同 scope 校验通过）。
    """
    store = FakeStore()
    eng = FakeEngine(store)

    all_link_types: set[str] = set()
    for pid, target_ot, row in OTS_WITH_LINK_BUILDERS:
        pipeline = _make_pipeline(pid, target_ot)
        rows = build_link_rows([row], pipeline)
        result = sink_to_ot(eng, TEST_SCOPE, pipeline, rows)
        # 每次至少 1 Object + 1 Link 落地
        assert result["links_written"] >= 1, f"{target_ot} 的 Link 未落地"
        links = [r for r in rows if "link_type" in r]
        all_link_types |= {r["link_type"] for r in links}

    # 13 条 Link 全部通过 CoreLinkRecord.validate_link
    constructable = EXPECTED_LINK_TYPES - {"Shop.sellsProduct"}
    assert all_link_types >= constructable


def test_d4_e2e_shop_sells_product_link_valid():
    """Shop.sellsProduct 无 build_link_rows builder，手动构造 Link 行验证 CoreLinkRecord 接受。

    Shop.sellsProduct 在 CORE_LINK_TYPES 注册但无 builder（Shop OT 无 _build_*_links）。
    手动构造 link row dict → sink_to_ot → CoreLinkRecord.validate_link 通过。
    """
    store = FakeStore()
    eng = FakeEngine(store)
    pipeline = _make_pipeline("p01", "Shop")

    # 手动构造 Shop.sellsProduct Link 行
    link_row = {
        "link_type": "Shop.sellsProduct",
        "source_type": "Shop",
        "source_pk": "1",
        "target_type": "Product",
        "target_source_pk": "g-1",
        "source_updated_at": NOW,
        "is_deleted": False,
        "properties": {},
    }

    result = sink_to_ot(eng, TEST_SCOPE, pipeline, [link_row])
    assert result["links_written"] == 1
    assert len(store.calls) == 1
    link = store.calls[0].links[0]
    assert link.link_type == "Shop.sellsProduct"
    assert link.source_type == "Shop"
    assert link.target_type == "Product"
    assert link.source.external_id == "niushop:1:1"
    assert link.target.external_id == "niushop:1:g-1"


# ═══════════════════════════════════════════════
# Section 3: 8 派生指标非空验证
# ═══════════════════════════════════════════════


def _fake_link_aggregator(member_ids: frozenset[str]) -> dict[str, tuple[int, datetime]]:
    """模拟 link_aggregator：返回每个 member_id 的 (order_count, last_order_create_time)。

    用于 CustomerLite 的 order_count / last_order_days 派生指标（D1.5 跨表聚合）。
    """
    return {mid: (5, NOW - timedelta(days=3)) for mid in member_ids}


def test_d4_e2e_8_derived_metrics_non_null_rate_gte_80pct():
    """apply_derived_metrics 后 8 派生指标非 null 占比 >= 80%（G4）。

    D1(4): quality_score / stock_health / risk_score / overdue_hours
    D1.5(2): order_count / last_order_days（需 link_aggregator 注入）
    D4(2): review_quality_bucket / pay_duration_min
    """
    metrics_values: dict[str, Any] = {}

    # D1: Product → quality_score（evaluate=10, evaluate_haoping=9 → 0.9）
    row = _product_row()
    apply_derived_metrics([row], _make_pipeline("p02", "Product"))
    metrics_values["quality_score"] = row["properties"].get("quality_score")

    # D1: ProductSku → stock_health（stock=100, alarm=10 → ok）
    row = _sku_row()
    apply_derived_metrics([row], _make_pipeline("p03", "ProductSku"))
    metrics_values["stock_health"] = row["properties"].get("stock_health")

    # D1: Order → risk_score（commission_risk_flag=1 → 0.4）
    row = _order_row()
    apply_derived_metrics([row], _make_pipeline("p05", "Order"))
    metrics_values["risk_score"] = row["properties"].get("risk_score")

    # D1: Shipment → overdue_hours（delivery_time=0, pay_time=PAST_TS → 非空）
    row = _shipment_row()
    apply_derived_metrics([row], _make_pipeline("p07", "Shipment"))
    metrics_values["overdue_hours"] = row["properties"].get("overdue_hours")

    # D1.5: CustomerLite → order_count / last_order_days（需 link_aggregator）
    row = _customer_lite_row()
    apply_derived_metrics(
        [row], _make_pipeline("p08", "CustomerLite"),
        link_aggregator=_fake_link_aggregator,
    )
    metrics_values["order_count"] = row["properties"].get("order_count")
    metrics_values["last_order_days"] = row["properties"].get("last_order_days")

    # D4: ProductReview → review_quality_bucket（score=4.5 → high）
    row = _review_row()
    apply_derived_metrics([row], _make_pipeline("p11", "ProductReview"))
    metrics_values["review_quality_bucket"] = row["properties"].get("review_quality_bucket")

    # D4: Payment → pay_duration_min（pay_time - _order_create_time = 600s = 10min）
    row = _payment_row()
    apply_derived_metrics([row], _make_pipeline("p12", "Payment"))
    metrics_values["pay_duration_min"] = row["properties"].get("pay_duration_min")

    # 验证 8 派生指标字段全部存在
    assert set(metrics_values.keys()) >= EXPECTED_DERIVED_METRICS

    # 非空占比 >= 80%（G4）
    non_null = sum(1 for v in metrics_values.values() if v is not None)
    rate = non_null / len(EXPECTED_DERIVED_METRICS)
    assert rate >= 0.8, (
        f"派生指标非空率 {rate:.0%} < 80%: "
        f"非空 {non_null}/{len(EXPECTED_DERIVED_METRICS)}, "
        f"值={metrics_values}"
    )


# ── review_quality_bucket 边界值（D4 DM1，frozen/02 §3.6）──


def _make_review_row(score: str) -> dict:
    """构造 ProductReview 行（指定 score），供边界值测试。"""
    return {
        "ot": "ProductReview",
        "source_pk": "rev_boundary",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "productId": "g-1",
            "memberId": "m-1",
            "score": score,
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }


def test_d4_e2e_review_quality_bucket_boundary_3_0_low():
    """边界值: score=3.0 → low（<=3.0，含等号，frozen/02 §3.6）。"""
    row = _make_review_row("3.0")
    apply_derived_metrics([row], _make_pipeline("p11", "ProductReview"))
    assert row["properties"]["review_quality_bucket"] == "low"


def test_d4_e2e_review_quality_bucket_boundary_4_5_high():
    """边界值: score=4.5 → high（>=4.5，含等号，frozen/02 §3.6）。"""
    row = _make_review_row("4.5")
    apply_derived_metrics([row], _make_pipeline("p11", "ProductReview"))
    assert row["properties"]["review_quality_bucket"] == "high"


def test_d4_e2e_review_quality_bucket_boundary_4_0_mid():
    """边界值: score=4.0 → mid（3.0 < score < 4.5，frozen/02 §3.6）。"""
    row = _make_review_row("4.0")
    apply_derived_metrics([row], _make_pipeline("p11", "ProductReview"))
    assert row["properties"]["review_quality_bucket"] == "mid"


# ── pay_duration_min 跨表关联（D4 DM2，管道内关联）──


def test_d4_e2e_pay_duration_min_cross_table_success():
    """pay_duration_min 跨表关联成功：_order_create_time + pay_time → 分钟差。

    场景：normalize 阶段已关联查到 Order.create_time，挂到 row._order_create_time。
    pay_time = NOW_TS + 600（10 分钟后支付），_order_create_time = NOW_TS → 10 分钟。
    """
    row = {
        "ot": "Payment",
        "source_pk": "pay_001",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "pay_time": NOW_TS + 600,
        "_order_create_time": NOW_TS,
        "properties": {
            "orderId": "o-1",
            "outTradeNo": "otn_001",
            "payStatus": "2",
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }
    apply_derived_metrics([row], _make_pipeline("p12", "Payment"))
    assert row["properties"]["pay_duration_min"] == 10


def test_d4_e2e_pay_duration_min_null_when_order_create_time_missing():
    """pay_duration_min 跨表关联失败：_order_create_time 缺失 → null（不阻塞 Pipeline）。

    场景：relate_id 为空或查不到 order → _order_create_time 未挂载 → null。
    """
    row = {
        "ot": "Payment",
        "source_pk": "pay_002",
        "source_updated_at": NOW,
        "source_timezone": "+00:00",
        "pay_time": NOW_TS + 600,
        # 不挂载 _order_create_time（模拟关联失败）
        "properties": {
            "orderId": "o-unknown",
            "outTradeNo": "otn_002",
            "payStatus": "2",
            "updatedAt": "2026-08-06T10:00:00+08:00",
        },
    }
    apply_derived_metrics([row], _make_pipeline("p12", "Payment"))
    assert row["properties"]["pay_duration_min"] is None
