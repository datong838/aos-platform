"""D2.5: ec_normalizer 单测 — 8 OT mapper + 幂等 + 派发 + raw 字段保留。

覆盖：
1. 8 OT mapper（raw ns_xxx 行 → normalized OT 行字段断言）
2. normalize_rows 幂等（已 normalized 行透传，不重复处理）
3. normalize_rows 派发（pipeline.config.target_ot 优先 + pipeline.id 推断）
4. normalize_rows 透传（未识别 target_ot）
5. raw 字段保留（apply_derived_metrics._get_field 依赖顶层 raw 字段）

约束（D2.5 规格文档 §3.1）：
- 行已含 ``ot`` 字段 → 跳过 mapper（幂等）
- 行无 ``ot`` 字段 → 应用对应 mapper
- target_ot 未识别 → 全部透传
- mapper 保留原始 raw 字段（dict(row) 浅拷贝）
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from aos_api.ec_normalizer import (
    _money,
    _resolve_target_ot,
    _str,
    _ts,
    normalize_rows,
    to_category,
    to_customer_lite,
    to_order,
    to_order_line,
    to_product,
    to_product_review,
    to_product_sku,
    to_shipment,
    to_shop,
    to_system_config,
    to_weapp,
)


# ═══════════════════════════════════════════════
# 8 OT mapper 测试
# ═══════════════════════════════════════════════


def test_to_shop_maps_site_id_and_create_time():
    """ns_site raw 行 → Shop OT normalized 行。"""
    raw = {
        "site_id": 1,
        "site_name": "栖月汇商贸",
        "create_time": 1700000000,
        "site_status": 1,
    }
    out = to_shop(raw)

    assert out["ot"] == "Shop"
    assert out["source_pk"] == "1"
    assert isinstance(out["source_updated_at"], datetime)
    assert out["source_updated_at"].tzinfo is not None  # UTC
    assert out["source_timezone"] == "+08:00"
    assert out["is_deleted"] is False
    assert out["properties"] == {
        "name": "栖月汇商贸",
        "status": "active",
        "currency": "CNY",
        "timezone": "+08:00",
    }
    # raw 字段保留
    assert out["site_id"] == 1
    assert out["site_name"] == "栖月汇商贸"
    assert out["create_time"] == 1700000000


def test_to_category_uses_now_when_no_time_column():
    """ns_goods_category 无时间列 → source_updated_at 用 now。"""
    raw = {
        "category_id": 11,
        "pid": "0",
        "category_name": "女装",
    }
    before = datetime.now(timezone.utc)
    out = to_category(raw)
    after = datetime.now(timezone.utc)

    assert out["ot"] == "Category"
    assert out["source_pk"] == "11"
    assert before <= out["source_updated_at"] <= after
    assert out["properties"] == {
        "parentCategoryId": "0",
        "name": "女装",
        "status": "active",
    }


def test_to_product_maps_goods_id_and_modify_time():
    """ns_goods raw 行 → Product OT normalized 行，properties 含 shopId/categoryId。"""
    raw = {
        "goods_id": 65,
        "goods_name": "测试商品",
        "goods_class_name": "服饰内衣",
        "category_id": "11,22",
        "site_id": 1,
        "price": "59.00",
        "market_price": "89.00",
        "cost_price": "30.00",
        "goods_stock": 120,
        "sale_num": 18,
        "unit": "件",
        "goods_state": 1,
        "is_delete": 0,
        "modify_time": 1700001000,
        "create_time": 1700000000,
        "evaluate": 10,
        "evaluate_haoping": 8,
    }
    out = to_product(raw)

    assert out["ot"] == "Product"
    assert out["source_pk"] == "65"
    assert out["schema_version"] == 2
    # modify_time 优先
    assert out["source_updated_at"] == datetime.fromtimestamp(1700001000, tz=timezone.utc)
    assert out["properties"]["shopId"] == "1"
    assert out["properties"]["categoryId"] == "11,22"
    assert out["properties"]["title"] == "测试商品"
    assert out["properties"]["goodsClassName"] == "服饰内衣"
    assert out["properties"]["price"] == "59.00"
    assert out["properties"]["marketPrice"] == "89.00"
    assert out["properties"]["costPrice"] == "30.00"
    assert out["properties"]["stock"] == "120"
    assert out["properties"]["saleNum"] == "18"
    assert out["properties"]["unit"] == "件"
    assert out["properties"]["state"] == "1"
    assert out["properties"]["isDelete"] == "0"
    assert out["properties"]["createdAt"] == "2023-11-14T22:13:20Z"
    assert out["properties"]["updatedAt"] == "2023-11-14T22:30:00Z"
    assert out["properties"]["sourceModifiedAt"] == "2023-11-14T22:30:00Z"
    # raw 字段保留（供 apply_derived_metrics._get_field 读取 evaluate/evaluate_haoping）
    assert out["evaluate"] == 10
    assert out["evaluate_haoping"] == 8


def test_to_product_uses_snapshot_observation_without_losing_source_business_time():
    raw = {
        "goods_id": 65,
        "goods_name": "测试商品",
        "modify_time": 1700001000,
        "create_time": 1700000000,
        "goods_stock": 120,
        "sale_num": 18,
        "_aos_observed_at": 1700005000.0,
    }

    out = to_product(raw)

    assert out["source_updated_at"] == datetime.fromtimestamp(1700005000, tz=timezone.utc)
    assert out["properties"]["createdAt"] == "2023-11-14T22:13:20Z"
    assert out["properties"]["updatedAt"] == "2023-11-14T22:30:00Z"
    assert out["properties"]["sourceModifiedAt"] == "2023-11-14T22:30:00Z"
    assert "_aos_observed_at" not in out["properties"]
    assert "_aos_observed_at" not in out


@pytest.mark.parametrize(
    ("mapper", "raw", "business_time", "business_property"),
    [
        (to_shop, {"site_id": 1, "create_time": 1700000000}, 1700000000, None),
        (
            to_product_sku,
            {"sku_id": 1, "goods_id": 2, "modify_time": 1700001000},
            1700001000,
            "updatedAt",
        ),
        (
            to_order,
            {"order_id": 1, "modify_time": 1700002000, "create_time": 1700000000},
            1700002000,
            "updatedAt",
        ),
        (
            to_customer_lite,
            {"member_id": 1, "reg_time": 1700003000},
            1700003000,
            "updatedAt",
        ),
        (
            to_weapp,
            {"weapp_id": 1, "modify_time": 1700004000},
            1700004000,
            "updatedAt",
        ),
        (
            to_system_config,
            {"id": 1, "modify_time": 1700005000},
            1700005000,
            "updatedAt",
        ),
        (
            to_product_review,
            {"evaluate_id": 1, "create_time": 1700006000},
            1700006000,
            "updatedAt",
        ),
    ],
)
def test_snapshot_observation_mappers_preserve_source_business_time(
    mapper, raw, business_time, business_property
):
    observed_at = 1700010000
    out = mapper({**raw, "_aos_observed_at": observed_at})

    assert out["source_updated_at"] == datetime.fromtimestamp(observed_at, tz=timezone.utc)
    assert "_aos_observed_at" not in out
    assert "_aos_observed_at" not in out["properties"]
    if business_property is not None:
        assert out["properties"][business_property] == datetime.fromtimestamp(
            business_time, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_to_product_sku_maps_sku_id_and_price():
    """ns_goods_sku raw 行 → ProductSku OT normalized 行。"""
    raw = {
        "sku_id": 73,
        "goods_id": 65,
        "sku_no": "SKU001",
        "price": "99.50",
        "stock": 100,
        "goods_stock_alarm": 10,
        "modify_time": 1700002000,
    }
    out = to_product_sku(raw)

    assert out["ot"] == "ProductSku"
    assert out["source_pk"] == "73"
    assert out["properties"]["productId"] == "65"
    assert out["properties"]["barcode"] == "SKU001"
    assert out["properties"]["price"] == "99.50"
    assert out["properties"]["currency"] == "CNY"
    assert out["properties"]["stock"] == "100"
    assert out["properties"]["stockAlarm"] == "10"
    # raw 字段保留（供 apply_derived_metrics 读取 stock/goods_stock_alarm）
    assert out["stock"] == 100
    assert out["goods_stock_alarm"] == 10


def test_to_product_sku_normalizes_integral_decimal_inventory_without_loss():
    out = to_product_sku({
        "sku_id": 73,
        "goods_id": 65,
        "stock": Decimal("497.000"),
        "goods_stock_alarm": Decimal("10.0"),
        "modify_time": 1700002000,
    })

    assert out["properties"]["stock"] == "497"
    assert out["properties"]["stockAlarm"] == "10"


def test_to_product_sku_preserves_missing_inventory_as_unknown():
    out = to_product_sku({"sku_id": 73, "goods_id": 65, "modify_time": 1700002000})

    assert "stock" not in out["properties"]
    assert "stockAlarm" not in out["properties"]


@pytest.mark.parametrize("value", [Decimal("1.5"), -1, "not-a-number"])
def test_to_product_sku_rejects_lossy_or_invalid_inventory(value: object):
    with pytest.raises(ValueError, match="stock must be a non-negative integer"):
        to_product_sku({
            "sku_id": 73,
            "goods_id": 65,
            "stock": value,
            "goods_stock_alarm": 0,
            "modify_time": 1700002000,
        })


def test_to_customer_lite_maps_member_id_and_reg_time():
    """ns_member raw 行 → CustomerLite OT normalized 行（PII 字段已在 source_adapter drop）。"""
    raw = {
        "member_id": 1001,
        "member_level": 2,
        "status": 1,
        "reg_time": 1700000000,
        "last_visit_time": 1700005000,
    }
    out = to_customer_lite(raw)

    assert out["ot"] == "CustomerLite"
    assert out["source_pk"] == "1001"
    # reg_time 优先
    assert out["source_updated_at"] == datetime.fromtimestamp(1700000000, tz=timezone.utc)
    assert out["properties"]["memberLevel"] == "2"
    assert out["properties"]["status"] == "active"


def test_to_order_maps_order_id_and_member_id_for_link():
    """ns_order raw 行 → Order OT normalized 行，properties 含 memberId（供 placedByLite Link）。"""
    raw = {
        "order_id": 177,
        "order_no": "ORD001",
        "member_id": 1001,
        "order_money": "199.00",
        "order_status": 1,
        "pay_status": 2,
        "delivery_status": 0,
        "site_id": 1,
        "modify_time": 1700003000,
        "create_time": 1700002500,
        "commission_risk_flag": 1,
        "refund_status": 0,
        "is_lock": 0,
    }
    out = to_order(raw)

    assert out["ot"] == "Order"
    assert out["source_pk"] == "177"
    assert out["properties"]["memberId"] == "1001"
    assert out["properties"]["shopId"] == "1"
    assert out["properties"]["orderNo"] == "ORD001"
    assert out["properties"]["totalAmount"] == "199.00"
    assert out["properties"]["orderStatus"] == "1"
    assert out["properties"]["payStatus"] == "2"
    # raw 字段保留（供 apply_derived_metrics._get_field 读取 risk_score 源字段）
    assert out["commission_risk_flag"] == 1
    assert out["refund_status"] == 0
    assert out["is_lock"] == 0


def test_to_order_line_maps_order_goods_id_and_links_keys():
    """ns_order_goods raw 行 → OrderLine OT normalized 行，properties 含 orderId/skuId。"""
    raw = {
        "order_goods_id": 227,
        "order_id": 177,
        "sku_id": 73,
        "goods_id": 65,
        "num": 2,
        "price": "99.50",
        "real_goods_money": "199.00",
        "goods_money": "199.00",
        "create_time": 1700002800,
    }
    out = to_order_line(raw)

    assert out["ot"] == "OrderLine"
    assert out["source_pk"] == "227"
    assert out["properties"]["orderId"] == "177"
    assert out["properties"]["skuId"] == "73"
    assert out["properties"]["quantity"] == "2"
    assert out["properties"]["unitPrice"] == "99.50"
    assert out["properties"]["lineAmount"] == "199.00"


def test_to_shipment_maps_id_and_order_id():
    """ns_express_delivery_package raw 行 → Shipment OT normalized 行。"""
    raw = {
        "id": 19,
        "order_id": 177,
        "delivery_time": 1700004000,
        "express_company_id": "SF",
        "express_company_name": "顺丰",
        "delivery_no": "SF1234567890",
    }
    out = to_shipment(raw)

    assert out["ot"] == "Shipment"
    assert out["source_pk"] == "19"
    assert out["source_updated_at"] == datetime.fromtimestamp(1700004000, tz=timezone.utc)
    assert out["properties"]["orderId"] == "177"
    assert out["properties"]["carrier"] == "SF"
    assert out["properties"]["trackingNo"] == "SF1234567890"
    # raw 字段保留（供 apply_derived_metrics._get_field 读取 delivery_time）
    assert out["delivery_time"] == 1700004000


# ═══════════════════════════════════════════════
# normalize_rows 入口测试
# ═══════════════════════════════════════════════


def test_normalize_rows_idempotent_skips_already_normalized_rows():
    """幂等契约：行已含 ``ot`` 字段 → 跳过 mapper，原样透传。"""
    raw_shop = {"site_id": 1, "site_name": "shop", "create_time": 1700000000}
    already_normalized = {
        "ot": "CustomerLite",
        "source_pk": "9999",
        "source_updated_at": datetime.now(timezone.utc),
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {"memberLevel": "5", "status": "active"},
        "custom_field": "should_be_preserved",
    }
    pipeline = SimpleNamespace(id="p01-shop", config={"target_ot": "Shop"})

    result = normalize_rows([raw_shop, already_normalized], pipeline)

    # 第 1 行：raw → normalized（Shop）
    assert result[0]["ot"] == "Shop"
    assert result[0]["source_pk"] == "1"
    # 第 2 行：已 normalized → 透传（不被 to_shop 覆盖）
    assert result[1]["ot"] == "CustomerLite"
    assert result[1]["source_pk"] == "9999"
    assert result[1]["properties"] == {"memberLevel": "5", "status": "active"}
    assert result[1]["custom_field"] == "should_be_preserved"


def test_normalize_rows_dispatches_by_config_target_ot():
    """派发：pipeline.config.target_ot 优先。"""
    raw = {"goods_id": 65, "goods_name": "p", "modify_time": 1700000000, "site_id": 1, "category_id": "0"}
    pipeline = SimpleNamespace(id="custom-id", config={"target_ot": "Product"})

    result = normalize_rows([raw], pipeline)

    assert result[0]["ot"] == "Product"
    assert result[0]["source_pk"] == "65"


def test_normalize_rows_dispatches_by_pipeline_id_prefix():
    """派发：缺失 config.target_ot 时用 pipeline.id 前缀推断（小写）。"""
    raw = {"order_id": 177, "modify_time": 1700000000, "site_id": 1, "member_id": "0"}
    pipeline = SimpleNamespace(id="p05-order-qyh", config={})

    result = normalize_rows([raw], pipeline)

    assert result[0]["ot"] == "Order"
    assert result[0]["source_pk"] == "177"


def test_normalize_rows_passes_through_when_target_ot_unrecognized():
    """透传：未识别 target_ot → 全部透传（与 ec_link_builder 一致）。"""
    raw = {"foo": "bar", "baz": 1}
    pipeline = SimpleNamespace(id="unknown-pipeline", config={})

    result = normalize_rows([raw], pipeline)

    assert len(result) == 1
    assert result[0] == raw  # 原样透传，不追加 ot 字段
    assert "ot" not in result[0]


def test_normalize_rows_passes_through_when_no_normalizer_registered():
    """透传：target_ot 识别但无 mapper 注册（理论上不会发生，但防御性测试）。"""
    raw = {"foo": "bar"}
    # target_ot="Unknown" 不在 _NORMALIZERS 中
    pipeline = SimpleNamespace(id="p99-unknown", config={"target_ot": "Unknown"})

    result = normalize_rows([raw], pipeline)

    assert len(result) == 1
    assert result[0] == raw


def test_normalize_rows_returns_new_list_not_mutating_input():
    """normalize_rows 返回新 list，不修改入参 rows。"""
    raw = {"site_id": 1, "site_name": "s", "create_time": 1700000000}
    pipeline = SimpleNamespace(id="p01-shop", config={})
    original_rows = [raw]

    result = normalize_rows(original_rows, pipeline)

    assert result is not original_rows
    assert original_rows[0] is raw  # 入参 list 不变
    assert "ot" not in raw  # 入参 raw dict 不被修改（mapper 浅拷贝了）


def test_normalize_rows_preserves_raw_fields_for_derived_metrics():
    """raw 字段保留契约：apply_derived_metrics._get_field 依赖顶层 raw 字段。

    场景：Product raw 行含 evaluate/evaluate_haoping，normalize 后必须保留在顶层。
    """
    raw = {
        "goods_id": 65,
        "goods_name": "p",
        "modify_time": 1700000000,
        "site_id": 1,
        "category_id": "0",
        "evaluate": 10,
        "evaluate_haoping": 8,
    }
    pipeline = SimpleNamespace(id="p02-product", config={})

    result = normalize_rows([raw], pipeline)

    # 顶层 raw 字段保留（apply_derived_metrics._get_field 优先从顶层读）
    assert result[0]["evaluate"] == 10
    assert result[0]["evaluate_haoping"] == 8
    # 同时 properties 也填充了
    assert result[0]["properties"]["shopId"] == "1"
    assert result[0]["properties"]["categoryId"] == "0"


def test_normalize_rows_handles_empty_rows():
    """空 rows 输入 → 空输出。"""
    pipeline = SimpleNamespace(id="p01-shop", config={})
    assert normalize_rows([], pipeline) == []


# ═══════════════════════════════════════════════
# 工具函数测试
# ═══════════════════════════════════════════════


def test_ts_returns_first_valid_timestamp():
    """_ts 从多个字段取首个有效 unix 秒转 UTC datetime。"""
    row = {"create_time": 0, "modify_time": 1700000000}
    dt = _ts(row, "create_time", "modify_time")
    assert dt == datetime.fromtimestamp(1700000000, tz=timezone.utc)


def test_ts_returns_now_when_all_invalid():
    """_ts 全字段无效（0/None/缺失）→ now。"""
    row = {"create_time": 0, "modify_time": None}
    before = datetime.now(timezone.utc)
    dt = _ts(row, "create_time", "modify_time")
    after = datetime.now(timezone.utc)
    assert before <= dt <= after


def test_money_handles_none_empty_invalid():
    """_money 兜底：None/空/非法 → '0'。"""
    assert _money(None) == "0"
    assert _money("") == "0"
    assert _money("invalid") == "0"
    assert _money("99.50") == "99.50"
    assert _money(100) == "100"


def test_str_handles_none_and_empty():
    """_str 兜底：None/空 → default。"""
    assert _str(None) == ""
    assert _str("") == ""
    assert _str("  hello  ") == "hello"
    assert _str(None, "default") == "default"
    assert _str("", "default") == "default"


# ═══════════════════════════════════════════════
# _resolve_target_ot 派发函数测试
# ═══════════════════════════════════════════════


@pytest.mark.parametrize(
    "pid,expected_ot",
    [
        ("p01-shop", "Shop"),
        ("p02-product", "Product"),
        ("p03-sku", "ProductSku"),
        ("p04-category", "Category"),
        ("p05-order", "Order"),
        ("p06-orderline", "OrderLine"),
        ("p07-shipment", "Shipment"),
        ("p08-customer", "CustomerLite"),
        # 大写前缀也兼容（lower 后匹配）
        ("P01-Shop", "Shop"),
        ("P05-Order", "Order"),
    ],
)
def test_resolve_target_ot_by_pipeline_id_prefix(pid: str, expected_ot: str):
    """_resolve_target_ot：缺失 config.target_ot 时用 pipeline.id 前缀推断。"""
    pipeline = SimpleNamespace(id=pid, config={})
    assert _resolve_target_ot(pipeline) == expected_ot


def test_resolve_target_ot_config_takes_priority():
    """_resolve_target_ot：config.target_ot 优先于 pipeline.id 推断。"""
    pipeline = SimpleNamespace(id="p01-shop", config={"target_ot": "Order"})
    assert _resolve_target_ot(pipeline) == "Order"


def test_resolve_target_ot_returns_none_for_unknown():
    """_resolve_target_ot：未识别返回 None。"""
    pipeline = SimpleNamespace(id="unknown-xxx", config={})
    assert _resolve_target_ot(pipeline) is None
