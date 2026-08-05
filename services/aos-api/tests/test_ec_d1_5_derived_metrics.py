"""D1.5: 派生指标 order_count Δ / last_order_days Δ 专项测试（FR-D1.5-4）。

覆盖 D1.5 新增的 2 个派生指标（CustomerLite OT，跨表聚合）：
- order_count Δ: 由 placedByLite Link 反向聚合，按 member_id 计算 Order 数量
- last_order_days Δ: now - max(Order.create_time)，按天；无订单时为 null

架构差异（与 D1 4 个单行派生指标对比）：
- D1 已有 4 个派生指标（quality_score/stock_health/risk_score/overdue_hours）均为单行派生
- D1.5 新增 2 个派生指标为跨表聚合（需查 ecom_link 表）
- 采用 link_aggregator 注入式接口保持派生指标模块的纯函数性与可测性

约束（frozen/02 §P08 + FR-D1.5-4）：
- apply_derived_metrics 签名向后兼容：D1 调用方 apply_derived_metrics(rows, pipeline) 不变
- link_aggregator 为 keyword-only 可选参数，默认 None
- link_aggregator=None 时 CustomerLite 行写 null（字段存在但为 null，满足 AC-D1.5-4）
- link_aggregator 提供 时写实际值
- link_aggregator 抛异常时不吞异常（fail-closed）
- 非 CustomerLite OT 不读 link_aggregator（D1 行为不变）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from aos_api.ec_derived_metrics import apply_derived_metrics

# 测试用固定 "now"，避免时间相关断言不稳定
FIXED_NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _fixed_now():
    """patch _now_utc 返回固定时间，让 last_order_days 断言确定。"""
    with patch("aos_api.ec_derived_metrics._now_utc", return_value=FIXED_NOW):
        yield


# ═══════════════════════════════════════════════
# pipeline / row 工厂
# ═══════════════════════════════════════════════


def _pipeline(pid: str = "p08-customer-lite", target_ot: str | None = None) -> SimpleNamespace:
    """构造 pipeline-like 对象。target_ot 优先于 pid 推断。"""
    config = {"target_ot": target_ot} if target_ot else {}
    return SimpleNamespace(id=pid, config=config)


def _customer_lite_row(
    member_id: str = "1001",
    *,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """P08 CustomerLite 规范化行：ot=CustomerLite, source_pk=member_id。"""
    props = dict(properties) if properties else {}
    # 默认补齐 REQUIRED_PROPERTIES（测试不关注 OT 落地，只关注派生指标写入）
    props.setdefault("memberLevel", "1")
    props.setdefault("status", "active")
    props.setdefault("createdAt", "2026-01-01T00:00:00+08:00")
    props.setdefault("updatedAt", "2026-07-31T18:00:00+08:00")
    return {
        "ot": "CustomerLite",
        "source_pk": member_id,
        "source_updated_at": FIXED_NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": props,
    }


def _aggregator_returning(
    mapping: dict[str, tuple[int, datetime | None]],
) -> Any:
    """构造 link_aggregator，记录调用并按 mapping 返回。

    mapping: {member_id: (order_count, last_order_create_time)}
    未在 mapping 中的 member_id 不在返回 dict 中（视为无订单数据 → null）。

    语义区分：
    - member_id 不在返回 dict 中 → null（无订单数据）
    - member_id 在返回 dict 中且 order_count=0 → 0（有数据但订单数为 0）
    """
    calls: list[frozenset[str]] = []

    def aggregator(member_ids: frozenset[str]) -> dict[str, tuple[int, datetime | None]]:
        calls.append(member_ids)
        return {mid: mapping[mid] for mid in member_ids if mid in mapping}

    aggregator.calls = calls  # type: ignore[attr-defined]
    return aggregator


# ═══════════════════════════════════════════════
# Section 1: link_aggregator 注入式接口（FR-D1.5-4 核心新增）
# ═══════════════════════════════════════════════


def test_apply_derived_metrics_accepts_link_aggregator_keyword() -> None:
    """FR-D1.5-4: apply_derived_metrics MUST 接受 link_aggregator keyword 参数（向后兼容）。"""
    row = _customer_lite_row("1001")
    # 不抛异常即可（默认 None）
    result = apply_derived_metrics([row], _pipeline(), link_aggregator=None)
    assert len(result) == 1


def test_customer_lite_writes_null_when_no_link_aggregator() -> None:
    """FR-D1.5-4: link_aggregator=None 时 CustomerLite 行写 null（字段存在但为 null）。

    满足 AC-D1.5-4 "字段存在 / 无订单的 CustomerLite 字段为 null"。
    """
    row = _customer_lite_row("1001")

    result = apply_derived_metrics([row], _pipeline(), link_aggregator=None)

    props = result[0]["properties"]
    assert "order_count" in props
    assert props["order_count"] is None
    assert "last_order_days" in props
    assert props["last_order_days"] is None


def test_customer_lite_writes_order_count_from_aggregator() -> None:
    """FR-D1.5-4: link_aggregator 提供时 CustomerLite 行写入 order_count 实际值。"""
    last_order = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    aggregator = _aggregator_returning({"1001": (5, last_order)})
    row = _customer_lite_row("1001")

    result = apply_derived_metrics([row], _pipeline(), link_aggregator=aggregator)

    assert result[0]["properties"]["order_count"] == 5


def test_customer_lite_writes_last_order_days_from_aggregator() -> None:
    """FR-D1.5-4: last_order_days = (now - last_order_create_time).days，按天。

    FIXED_NOW=2026-08-05 10:00 UTC，last_order=2026-08-01 12:00 UTC
    差 = 3 天 22 小时 = 3.917 天 → .days = 3
    """
    last_order = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    aggregator = _aggregator_returning({"1001": (1, last_order)})
    row = _customer_lite_row("1001")

    result = apply_derived_metrics([row], _pipeline(), link_aggregator=aggregator)

    assert result[0]["properties"]["last_order_days"] == 3


def test_link_aggregator_receives_member_ids_from_rows() -> None:
    """FR-D1.5-4: link_aggregator 收到 rows 中所有 source_pk（member_id）集合。"""
    aggregator = _aggregator_returning({})
    rows = [
        _customer_lite_row("1001"),
        _customer_lite_row("1002"),
        _customer_lite_row("1003"),
    ]

    apply_derived_metrics(rows, _pipeline(), link_aggregator=aggregator)

    assert len(aggregator.calls) == 1
    received = aggregator.calls[0]
    assert received == frozenset({"1001", "1002", "1003"})


def test_customer_lite_member_not_in_aggregator_result_writes_null() -> None:
    """FR-D1.5-4: member_id 在 rows 中但不在聚合结果中（无订单）→ 写 null。

    注：link_aggregator 返回的 dict 不含该 member_id 时，视为无订单。
    """
    # aggregator 返回空 dict（所有 member_id 都无订单）
    aggregator = _aggregator_returning({})
    row = _customer_lite_row("1001")

    result = apply_derived_metrics([row], _pipeline(), link_aggregator=aggregator)

    props = result[0]["properties"]
    # 无订单：order_count=null, last_order_days=null
    assert props["order_count"] is None
    assert props["last_order_days"] is None


def test_customer_lite_member_with_zero_orders_writes_zero() -> None:
    """FR-D1.5-4: order_count=0（有聚合结果但订单数为 0）→ 写 0（不是 null）。

    区分语义：
    - member_id 不在聚合结果 → null（无订单数据）
    - member_id 在聚合结果且 order_count=0 → 0（有数据但订单数为 0）
    """
    # aggregator 显式返回 order_count=0
    aggregator = _aggregator_returning({"1001": (0, None)})
    row = _customer_lite_row("1001")

    result = apply_derived_metrics([row], _pipeline(), link_aggregator=aggregator)

    props = result[0]["properties"]
    assert props["order_count"] == 0
    assert props["last_order_days"] is None


def test_last_order_days_is_non_negative() -> None:
    """FR-D1.5-4: last_order_days >= 0（即使 last_order_create_time 是未来时间也截断到 0）。

    边界：last_order_create_time 在 now 之后（数据异常），last_order_days 不为负。
    """
    future_order = FIXED_NOW + timedelta(days=2)
    aggregator = _aggregator_returning({"1001": (1, future_order)})
    row = _customer_lite_row("1001")

    result = apply_derived_metrics([row], _pipeline(), link_aggregator=aggregator)

    assert result[0]["properties"]["last_order_days"] == 0


def test_link_aggregator_exception_propagates() -> None:
    """FR-D1.5-4: link_aggregator 抛异常时 apply_derived_metrics MUST NOT 吞异常（fail-closed）。"""

    def failing_aggregator(member_ids: frozenset[str]) -> dict[str, tuple[int, datetime | None]]:
        raise RuntimeError("ecom_link query failed")

    row = _customer_lite_row("1001")

    with pytest.raises(RuntimeError, match="ecom_link query failed"):
        apply_derived_metrics([row], _pipeline(), link_aggregator=failing_aggregator)


def test_link_aggregator_called_once_per_batch() -> None:
    """FR-D1.5-4: link_aggregator 只调用一次（批量查询，不是每行一次）。

    性能约束：避免 N+1 查询。
    """
    aggregator = _aggregator_returning({"1001": (1, FIXED_NOW)})
    rows = [
        _customer_lite_row("1001"),
        _customer_lite_row("1002"),
        _customer_lite_row("1003"),
    ]

    apply_derived_metrics(rows, _pipeline(), link_aggregator=aggregator)

    assert len(aggregator.calls) == 1


def test_customer_lite_rows_share_single_aggregator_query() -> None:
    """FR-D1.5-4: 多行 CustomerLite 共享一次聚合查询结果，按 member_id 分发写入。"""
    last_order_1 = datetime(2026, 7, 30, 0, 0, tzinfo=timezone.utc)  # 6 天前
    last_order_2 = datetime(2026, 8, 4, 0, 0, tzinfo=timezone.utc)  # 1 天前
    aggregator = _aggregator_returning({
        "1001": (3, last_order_1),
        "1002": (1, last_order_2),
        # 1003 无聚合结果 → null
    })
    rows = [
        _customer_lite_row("1001"),
        _customer_lite_row("1002"),
        _customer_lite_row("1003"),
    ]

    result = apply_derived_metrics(rows, _pipeline(), link_aggregator=aggregator)

    assert result[0]["properties"]["order_count"] == 3
    assert result[0]["properties"]["last_order_days"] == 6
    assert result[1]["properties"]["order_count"] == 1
    assert result[1]["properties"]["last_order_days"] == 1
    assert result[2]["properties"]["order_count"] is None
    assert result[2]["properties"]["last_order_days"] is None


# ═══════════════════════════════════════════════
# Section 2: 向后兼容 & D1 零回归
# ═══════════════════════════════════════════════


def test_d1_quality_score_still_works() -> None:
    """D1 零回归：Product 行 quality_score 仍正确计算。"""
    row = {
        "ot": "Product",
        "source_pk": "g-1",
        "source_updated_at": FIXED_NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {"shopId": "1", "title": "T", "status": "active", "categoryId": "c-1",
                       "createdAt": "2026-07-01T00:00:00Z", "updatedAt": "2026-07-01T00:00:00Z"},
        "evaluate": 10,
        "evaluate_haoping": 8,
    }

    result = apply_derived_metrics([row], _pipeline("p02-product"))

    assert result[0]["properties"]["quality_score"] == 0.8


def test_d1_stock_health_still_works() -> None:
    """D1 零回归：ProductSku 行 stock_health 仍正确计算。"""
    row = {
        "ot": "ProductSku",
        "source_pk": "s-1",
        "source_updated_at": FIXED_NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {"productId": "g-1", "status": "active", "barcode": "B", "price": "1.00",
                       "currency": "CNY", "updatedAt": "2026-07-01T00:00:00Z"},
        "stock": 5,
        "goods_stock_alarm": 10,
    }

    result = apply_derived_metrics([row], _pipeline("p03-sku"))

    assert result[0]["properties"]["stock_health"] == "watch"


def test_d1_risk_score_still_works() -> None:
    """D1 零回归：Order 行 risk_score 仍正确计算。"""
    row = {
        "ot": "Order",
        "source_pk": "o-1",
        "source_updated_at": FIXED_NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {"shopId": "1", "status": "active", "totalAmount": "100.00", "currency": "CNY",
                       "createdAt": "2026-07-01T00:00:00Z", "updatedAt": "2026-07-01T00:00:00Z"},
        "commission_risk_flag": 1,
    }

    result = apply_derived_metrics([row], _pipeline("p05-order"))

    assert result[0]["properties"]["risk_score"] == 0.4


def test_d1_overdue_hours_still_works() -> None:
    """D1 零回归：Shipment 行 overdue_hours 仍正确计算。"""
    pay_time = (FIXED_NOW - timedelta(hours=50)).timestamp()  # 50h 前支付
    row = {
        "ot": "Shipment",
        "source_pk": "sh-1",
        "source_updated_at": FIXED_NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {"orderId": "o-1", "status": "active", "carrier": "SF",
                       "trackingNo": "T123", "shippedAt": "2026-07-01T00:00:00Z",
                       "updatedAt": "2026-07-01T00:00:00Z"},
        "delivery_time": 0,  # 未发货
        "pay_time": pay_time,
    }

    result = apply_derived_metrics([row], _pipeline("p07-shipment"))

    # 50h - 48h SLA = 2h 逾期
    assert result[0]["properties"]["overdue_hours"] == 2.0


def test_non_customer_lite_pipeline_ignores_link_aggregator() -> None:
    """FR-D1.5-4: 非 CustomerLite OT MUST NOT 调用 link_aggregator（D1 行为不变）。"""
    aggregator_called = False

    def aggregator(member_ids: frozenset[str]) -> dict[str, tuple[int, datetime | None]]:
        raise AssertionError("link_aggregator MUST NOT be called for non-CustomerLite OT")

    # Product 行（不应触发 link_aggregator）
    row = {
        "ot": "Product",
        "source_pk": "g-1",
        "source_updated_at": FIXED_NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {"shopId": "1", "title": "T", "status": "active", "categoryId": "c-1",
                       "createdAt": "2026-07-01T00:00:00Z", "updatedAt": "2026-07-01T00:00:00Z"},
        "evaluate": 0,
    }

    # 传入 link_aggregator 但 Product 行不应调用它
    result = apply_derived_metrics([row], _pipeline("p02-product"), link_aggregator=aggregator)

    # quality_score=null（evaluate=0），但 link_aggregator 未被调用（未抛 AssertionError）
    assert result[0]["properties"]["quality_score"] is None


# ═══════════════════════════════════════════════
# Section 3: 边界
# ═══════════════════════════════════════════════


def test_empty_rows_returns_empty() -> None:
    """边界：空 rows 返回空 list。"""
    result = apply_derived_metrics([], _pipeline(), link_aggregator=None)
    assert result == []


def test_customer_lite_row_missing_source_pk_skips_aggregator() -> None:
    """FR-D1.5-4: CustomerLite 行 source_pk 缺失时跳过 link_aggregator 调用，写 null。

    边界：source_pk 缺失视为无效 member_id，不传入 link_aggregator。
    """
    aggregator = _aggregator_returning({})
    row = _customer_lite_row("")
    # 修正 source_pk 为空字符串
    row["source_pk"] = ""

    result = apply_derived_metrics([row], _pipeline(), link_aggregator=aggregator)

    # link_aggregator 未被调用（无有效 member_id）
    assert len(aggregator.calls) == 0
    props = result[0]["properties"]
    assert props["order_count"] is None
    assert props["last_order_days"] is None


def test_customer_lite_does_not_write_d1_metrics() -> None:
    """FR-D1.5-4: CustomerLite 行 MUST NOT 写入 D1 派生指标（quality_score 等）。

    隔离约束：派生指标按 target_ot 分发，CustomerLite 只写 order_count/last_order_days。
    """
    row = _customer_lite_row("1001")

    result = apply_derived_metrics([row], _pipeline(), link_aggregator=None)

    props = result[0]["properties"]
    # 不应写入 D1 派生指标
    assert "quality_score" not in props
    assert "stock_health" not in props
    assert "risk_score" not in props
    assert "overdue_hours" not in props
    # 只写 D1.5 派生指标
    assert "order_count" in props
    assert "last_order_days" in props


def test_customer_lite_preserves_existing_properties() -> None:
    """FR-D1.5-4: 派生指标写入 MUST NOT 覆盖 row 已有的 properties 字段。"""
    row = _customer_lite_row(
        "1001",
        properties={
            "memberLevel": "vip",
            "status": "active",
            "createdAt": "2026-01-01T00:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
            "customField": "保留我",
        },
    )

    result = apply_derived_metrics([row], _pipeline(), link_aggregator=None)

    props = result[0]["properties"]
    # 原有字段保留
    assert props["memberLevel"] == "vip"
    assert props["customField"] == "保留我"
    # 派生指标写入
    assert "order_count" in props
    assert "last_order_days" in props


def test_customer_lite_pipeline_id_inference() -> None:
    """FR-D1.5-4: pipeline.id 以 'p08' 开头时推断 target_ot=CustomerLite。"""
    row = _customer_lite_row("1001")

    # 不传 target_ot，靠 pipeline.id 推断
    result = apply_derived_metrics([row], _pipeline("p08-customer-lite"), link_aggregator=None)

    props = result[0]["properties"]
    assert "order_count" in props
    assert "last_order_days" in props
