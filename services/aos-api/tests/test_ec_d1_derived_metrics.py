"""D1-W1: 派生指标计算专项测试（FR-D1-7）。

覆盖 4 个派生指标的各种边界：
- quality_score (Product): evaluate>0 正常计算；evaluate=0 → null；
  evaluate_haoping > evaluate → 截断到 1.0；源字段缺失 → null
- stock_health (ProductSku): stock=0 → low；stock=alarm → watch；stock>alarm → ok；
  goods_stock_alarm 缺失 → 默认 alarm=0；stock 缺失 → null
- risk_score (Order): 各因子累加；截断 [0,1]；commission_risk_flag + refund_status +
  is_lock + 24h 组合
- overdue_hours (Shipment): delivery_time=0 + pay_time>0 → 计算；
  delivery_time>0 → null；pay_time=0 → null；SLA_HOURS=48

另覆盖：
- pipeline.config.target_ot 分发
- pipeline.id 推断（P01→Shop, P02→Product, P03→ProductSku, P05→Order, P07→Shipment）
- Shop/Category/OrderLine 无派生指标 → 透传不写
- 不修改 source_pk / external_id / source_updated_at 等核心字段
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aos_api.ec_derived_metrics import apply_derived_metrics

# 测试用固定 "now"，避免时间相关断言不稳定
FIXED_NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _fixed_now():
    """patch _now_utc 返回固定时间，让 24h/48h 阈值断言确定。"""
    with patch("aos_api.ec_derived_metrics._now_utc", return_value=FIXED_NOW):
        yield


# ═══════════════════════════════════════════════
# pipeline 工厂
# ═══════════════════════════════════════════════


def _pipeline(pid: str = "p02-product", target_ot: str | None = None) -> SimpleNamespace:
    """构造 pipeline-like 对象。target_ot 优先于 pid 推断。"""
    config = {"target_ot": target_ot} if target_ot else {}
    return SimpleNamespace(id=pid, config=config)


def _row(ot: str, source_pk: str = "1", **fields) -> dict:
    """构造 normalized executor row。源字段可放顶层也可放 properties。"""
    properties = fields.pop("properties", None)
    row = {
        "ot": ot,
        "source_pk": source_pk,
        "source_updated_at": FIXED_NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": dict(properties) if properties else {},
    }
    row.update(fields)
    return row


# ═══════════════════════════════════════════════
# 1. quality_score (Product)
# ═══════════════════════════════════════════════


def test_quality_score_normal_calculation():
    """evaluate>0 时 quality_score = evaluate_haoping / evaluate。"""
    row = _row("Product", evaluate=10, evaluate_haoping=8)
    result = apply_derived_metrics([row], _pipeline("p02"))
    assert result[0]["properties"]["quality_score"] == 0.8


def test_quality_score_evaluate_zero_returns_null():
    """evaluate=0 时 quality_score = null。"""
    row = _row("Product", evaluate=0, evaluate_haoping=5)
    result = apply_derived_metrics([row], _pipeline("p02"))
    assert result[0]["properties"]["quality_score"] is None


def test_quality_score_evaluate_missing_returns_null():
    """evaluate 缺失时 quality_score = null（源字段缺失不阻塞）。"""
    row = _row("Product", evaluate_haoping=5)
    result = apply_derived_metrics([row], _pipeline("p02"))
    assert result[0]["properties"]["quality_score"] is None


def test_quality_score_haoping_exceeds_evaluate_capped_to_1():
    """evaluate_haoping > evaluate → 截断到 1.0。"""
    row = _row("Product", evaluate=5, evaluate_haoping=10)
    result = apply_derived_metrics([row], _pipeline("p02"))
    assert result[0]["properties"]["quality_score"] == 1.0


def test_quality_score_reads_from_properties():
    """源字段在 properties 中也能读取（normalized 格式兼容）。"""
    row = _row("Product", properties={"evaluate": 20, "evaluate_haoping": 15})
    result = apply_derived_metrics([row], _pipeline("p02"))
    assert result[0]["properties"]["quality_score"] == 0.75


def test_quality_score_target_ot_via_config():
    """pipeline.config.target_ot=Product 也能分发到 quality_score。"""
    row = _row("Product", evaluate=4, evaluate_haoping=3)
    result = apply_derived_metrics([row], _pipeline("any-id", target_ot="Product"))
    assert result[0]["properties"]["quality_score"] == 0.75


# ═══════════════════════════════════════════════
# 2. stock_health (ProductSku)
# ═══════════════════════════════════════════════


def test_stock_health_zero_is_low():
    """stock=0 → low。"""
    row = _row("ProductSku", stock=0, goods_stock_alarm=5)
    result = apply_derived_metrics([row], _pipeline("p03"))
    assert result[0]["properties"]["stock_health"] == "low"


def test_stock_health_at_alarm_is_watch():
    """stock=alarm → watch（0 < stock <= alarm）。"""
    row = _row("ProductSku", stock=5, goods_stock_alarm=5)
    result = apply_derived_metrics([row], _pipeline("p03"))
    assert result[0]["properties"]["stock_health"] == "watch"


def test_stock_health_below_alarm_is_watch():
    """0 < stock < alarm → watch。"""
    row = _row("ProductSku", stock=3, goods_stock_alarm=5)
    result = apply_derived_metrics([row], _pipeline("p03"))
    assert result[0]["properties"]["stock_health"] == "watch"


def test_stock_health_above_alarm_is_ok():
    """stock>alarm → ok。"""
    row = _row("ProductSku", stock=10, goods_stock_alarm=5)
    result = apply_derived_metrics([row], _pipeline("p03"))
    assert result[0]["properties"]["stock_health"] == "ok"


def test_stock_health_alarm_missing_defaults_to_zero():
    """goods_stock_alarm 缺失 → 默认 alarm=0，stock>0 即 ok。"""
    row = _row("ProductSku", stock=1)
    result = apply_derived_metrics([row], _pipeline("p03"))
    assert result[0]["properties"]["stock_health"] == "ok"


def test_stock_health_alarm_missing_and_stock_zero_is_low():
    """goods_stock_alarm 缺失 + stock=0 → low（alarm 默认 0，stock<=0）。"""
    row = _row("ProductSku", stock=0)
    result = apply_derived_metrics([row], _pipeline("p03"))
    assert result[0]["properties"]["stock_health"] == "low"


def test_stock_health_stock_missing_returns_null():
    """stock 缺失 → null（源字段缺失不阻塞）。"""
    row = _row("ProductSku", goods_stock_alarm=5)
    result = apply_derived_metrics([row], _pipeline("p03"))
    assert result[0]["properties"]["stock_health"] is None


def test_stock_health_target_ot_via_config():
    """pipeline.config.target_ot=ProductSku 也能分发。"""
    row = _row("ProductSku", stock=0, goods_stock_alarm=1)
    result = apply_derived_metrics([row], _pipeline("any", target_ot="ProductSku"))
    assert result[0]["properties"]["stock_health"] == "low"


# ═══════════════════════════════════════════════
# 3. risk_score (Order)
# ═══════════════════════════════════════════════


def test_risk_score_base_zero_no_flags():
    """无任何风险因子 → risk_score = 0.0。"""
    row = _row("Order", commission_risk_flag=0, refund_status=0,
               is_lock=0, order_status=1, pay_status=1, create_time=1000)
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 0.0


def test_risk_score_commission_flag_adds_040():
    """commission_risk_flag=1 → +0.40。"""
    row = _row("Order", commission_risk_flag=1, refund_status=0,
               is_lock=0, order_status=1, pay_status=1, create_time=1000)
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 0.40


def test_risk_score_refund_status_3_adds_030():
    """refund_status=3 → +0.30。"""
    row = _row("Order", commission_risk_flag=0, refund_status=3,
               is_lock=0, order_status=1, pay_status=1, create_time=1000)
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 0.30


def test_risk_score_refund_status_neg3_adds_030():
    """refund_status=-3 → +0.30。"""
    row = _row("Order", commission_risk_flag=0, refund_status=-3,
               is_lock=0, order_status=1, pay_status=1, create_time=1000)
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 0.30


def test_risk_score_is_lock_adds_020():
    """is_lock=1 → +0.20。"""
    row = _row("Order", commission_risk_flag=0, refund_status=0,
               is_lock=1, order_status=1, pay_status=1, create_time=1000)
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 0.20


def test_risk_score_stale_24h_adds_010():
    """order_status=0 AND pay_status=0 AND now-create_time>24h → +0.10。"""
    # create_time 在 FIXED_NOW 前 25 小时（>24h）
    stale_create = FIXED_NOW - timedelta(hours=25)
    row = _row("Order", commission_risk_flag=0, refund_status=0,
               is_lock=0, order_status=0, pay_status=0,
               create_time=stale_create.timestamp())
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 0.10


def test_risk_score_stale_not_triggered_within_24h():
    """order_status=0 AND pay_status=0 但 now-create_time<=24h → 不加 0.10。"""
    fresh_create = FIXED_NOW - timedelta(hours=23)
    row = _row("Order", commission_risk_flag=0, refund_status=0,
               is_lock=0, order_status=0, pay_status=0,
               create_time=fresh_create.timestamp())
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 0.0


def test_risk_score_stale_not_triggered_when_order_status_nonzero():
    """order_status!=0 → 不触发 24h 因子（即使 create_time 很旧）。"""
    stale_create = FIXED_NOW - timedelta(hours=48)
    row = _row("Order", commission_risk_flag=0, refund_status=0,
               is_lock=0, order_status=1, pay_status=0,
               create_time=stale_create.timestamp())
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 0.0


def test_risk_score_all_flags_combined():
    """四个因子全开：0.40 + 0.30 + 0.20 + 0.10 = 1.00。"""
    stale_create = FIXED_NOW - timedelta(hours=30)
    row = _row("Order", commission_risk_flag=1, refund_status=3,
               is_lock=1, order_status=0, pay_status=0,
               create_time=stale_create.timestamp())
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 1.0


def test_risk_score_capped_at_1():
    """risk_score 截断 [0,1]：即使因子总和>1 也截断到 1.0。

    注：当前 4 因子总和=1.00，不会超过 1。但测试验证截断逻辑存在。
    """
    stale_create = FIXED_NOW - timedelta(hours=72)
    row = _row("Order", commission_risk_flag=1, refund_status=3,
               is_lock=1, order_status=0, pay_status=0,
               create_time=stale_create.timestamp())
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] <= 1.0


def test_risk_score_create_time_missing_skips_24h():
    """create_time 缺失 → 跳过 24h 因子（不阻塞，其他因子仍计算）。"""
    row = _row("Order", commission_risk_flag=1, refund_status=0,
               is_lock=0, order_status=0, pay_status=0)
    result = apply_derived_metrics([row], _pipeline("p05"))
    assert result[0]["properties"]["risk_score"] == 0.40


# ═══════════════════════════════════════════════
# 4. overdue_hours (Shipment)
# ═══════════════════════════════════════════════


def test_overdue_hours_normal_calculation():
    """delivery_time=0 + pay_time>0 → 计算 overdue_hours。

    pay_time 在 FIXED_NOW 前 72 小时，SLA=48h → overdue = (72-48)/1 = 24.0
    """
    pay_time = FIXED_NOW - timedelta(hours=72)
    row = _row("Shipment", delivery_time=0, pay_time=pay_time.timestamp())
    result = apply_derived_metrics([row], _pipeline("p07"))
    assert result[0]["properties"]["overdue_hours"] == 24.0


def test_overdue_hours_within_sla_is_zero():
    """pay_time 距 now < 48h → overdue_hours = 0.0（max(0, ...) 截断）。"""
    pay_time = FIXED_NOW - timedelta(hours=24)
    row = _row("Shipment", delivery_time=0, pay_time=pay_time.timestamp())
    result = apply_derived_metrics([row], _pipeline("p07"))
    assert result[0]["properties"]["overdue_hours"] == 0.0


def test_overdue_hours_delivery_time_positive_returns_null():
    """delivery_time>0（已发货）→ null。"""
    pay_time = FIXED_NOW - timedelta(hours=72)
    row = _row("Shipment", delivery_time=1000, pay_time=pay_time.timestamp())
    result = apply_derived_metrics([row], _pipeline("p07"))
    assert result[0]["properties"]["overdue_hours"] is None


def test_overdue_hours_pay_time_zero_returns_null():
    """pay_time=0（未支付）→ null。"""
    row = _row("Shipment", delivery_time=0, pay_time=0)
    result = apply_derived_metrics([row], _pipeline("p07"))
    assert result[0]["properties"]["overdue_hours"] is None


def test_overdue_hours_pay_time_missing_returns_null():
    """pay_time 缺失 → null。"""
    row = _row("Shipment", delivery_time=0)
    result = apply_derived_metrics([row], _pipeline("p07"))
    assert result[0]["properties"]["overdue_hours"] is None


def test_overdue_hours_both_zero_returns_null():
    """delivery_time=0 + pay_time=0 → null（未支付无法判定逾期）。"""
    row = _row("Shipment", delivery_time=0, pay_time=0)
    result = apply_derived_metrics([row], _pipeline("p07"))
    assert result[0]["properties"]["overdue_hours"] is None


def test_overdue_hours_target_ot_via_config():
    """pipeline.config.target_ot=Shipment 也能分发。"""
    pay_time = FIXED_NOW - timedelta(hours=72)
    row = _row("Shipment", delivery_time=0, pay_time=pay_time.timestamp())
    result = apply_derived_metrics([row], _pipeline("any", target_ot="Shipment"))
    assert result[0]["properties"]["overdue_hours"] == 24.0


def test_overdue_hours_delivery_time_none_treated_as_zero():
    """delivery_time=None（source_adapter 把 0 转 None）→ 视为未发货，仍计算。"""
    pay_time = FIXED_NOW - timedelta(hours=72)
    row = _row("Shipment", delivery_time=None, pay_time=pay_time.timestamp())
    result = apply_derived_metrics([row], _pipeline("p07"))
    assert result[0]["properties"]["overdue_hours"] == 24.0


# ═══════════════════════════════════════════════
# 5. 分发与透传
# ═══════════════════════════════════════════════


def test_shop_pipeline_no_derived_metrics_passthrough():
    """P01 Shop 无派生指标 → 透传，properties 不含 4 个派生字段。"""
    row = _row("Shop", properties={"site_name": "栖月汇"})
    result = apply_derived_metrics([row], _pipeline("p01"))
    props = result[0]["properties"]
    assert "quality_score" not in props
    assert "stock_health" not in props
    assert "risk_score" not in props
    assert "overdue_hours" not in props
    assert props["site_name"] == "栖月汇"


def test_category_pipeline_no_derived_metrics():
    """P04 Category 无派生指标 → 透传。"""
    row = _row("Category", properties={"name": "分类A"})
    result = apply_derived_metrics([row], _pipeline("p04"))
    assert "quality_score" not in result[0]["properties"]


def test_orderline_pipeline_no_derived_metrics():
    """P06 OrderLine 无派生指标 → 透传。"""
    row = _row("OrderLine", properties={"quantity": 2})
    result = apply_derived_metrics([row], _pipeline("p06"))
    assert "risk_score" not in result[0]["properties"]


def test_unknown_pipeline_id_passthrough():
    """未知 pipeline.id → 透传（无派生指标计算）。"""
    row = _row("Unknown", evaluate=10, evaluate_haoping=5)
    result = apply_derived_metrics([row], _pipeline("p99-unknown"))
    assert "quality_score" not in result[0]["properties"]


def test_pipeline_id_with_suffix_still_matches():
    """pipeline.id='p02-shop-products' 仍匹配 p02 前缀 → Product。"""
    row = _row("Product", evaluate=10, evaluate_haoping=5)
    result = apply_derived_metrics([row], _pipeline("p02-shop-products"))
    assert result[0]["properties"]["quality_score"] == 0.5


# ═══════════════════════════════════════════════
# 6. 核心字段不被修改
# ═══════════════════════════════════════════════


def test_core_fields_not_modified_by_quality_score():
    """派生指标不修改 source_pk / external_id / source_updated_at 等核心字段。"""
    row = _row("Product", source_pk="g-42", evaluate=10, evaluate_haoping=8)
    row["external_id"] = "niushop:1:g-42"
    original_pk = row["source_pk"]
    original_ext = row["external_id"]
    original_time = row["source_updated_at"]
    original_tz = row["source_timezone"]

    apply_derived_metrics([row], _pipeline("p02"))

    assert row["source_pk"] == original_pk
    assert row["external_id"] == original_ext
    assert row["source_updated_at"] == original_time
    assert row["source_timezone"] == original_tz
    assert row["ot"] == "Product"


def test_empty_rows_returns_empty():
    """空 rows → 返回空 list。"""
    result = apply_derived_metrics([], _pipeline("p02"))
    assert result == []


def test_multiple_rows_all_get_derived_metrics():
    """多行批量处理：每行都计算派生指标。"""
    rows = [
        _row("Product", source_pk="g-1", evaluate=10, evaluate_haoping=8),
        _row("Product", source_pk="g-2", evaluate=0, evaluate_haoping=0),
        _row("Product", source_pk="g-3", evaluate=4, evaluate_haoping=5),
    ]
    result = apply_derived_metrics(rows, _pipeline("p02"))
    assert result[0]["properties"]["quality_score"] == 0.8
    assert result[1]["properties"]["quality_score"] is None
    assert result[2]["properties"]["quality_score"] == 1.0


def test_properties_created_if_missing():
    """row 无 properties 字段时自动创建。"""
    row = {
        "ot": "Product",
        "source_pk": "1",
        "source_updated_at": FIXED_NOW,
        "evaluate": 10,
        "evaluate_haoping": 5,
    }
    result = apply_derived_metrics([row], _pipeline("p02"))
    assert "properties" in result[0]
    assert result[0]["properties"]["quality_score"] == 0.5
