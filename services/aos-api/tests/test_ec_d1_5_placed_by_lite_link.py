"""D1.5: placedByLite Link 构造专项测试（FR-D1.5-3）。

验证 ec_link_builder 对 P05 Order 行构造 placedByLite Link（Order → CustomerLite）：

| Link         | From → To             | 来源字段   | 构造时机          |
|--------------|-----------------------|------------|-------------------|
| placedByLite | Order → CustomerLite  | member_id  | P05 Order 读取时  |

约束（frozen/02 §P08 + FR-D1.5-3）：
- source_type=Order, source_pk=order_id（row.source_pk）
- target_type=CustomerLite, target_source_pk=member_id（row.properties.memberId）
- 完整性门禁：member_id 缺失或为 0 时跳过 Link 构造（不进 DLQ，因 D1 P05 已声明保留关联键）
- Link 行追加到 rows 末尾，原 rows 不变
- link_type 输出为点号名 "Order.placedByLite"（非简短名 "placedByLite"）
- 方向不反转（Order→CustomerLite 与 CORE_LINK_TYPES 一致）
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from aos_api.ec_link_builder import build_link_rows

NOW = datetime(2026, 8, 6, 10, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════
# row 工厂与 helper
# ═══════════════════════════════════════════════


def order_row(
    *,
    order_id: str = "100",
    member_id: Any = "1001",
    when: datetime = NOW,
) -> dict[str, Any]:
    """P05 Order 规范化行：ot=Order, source_pk=order_id, properties 含 memberId 关联键。

    member_id=None 时省略 memberId 键（模拟缺失）。
    """
    props: dict[str, Any] = {
        "shopId": "1",
        "status": "active",
        "totalAmount": "199.00",
        "currency": "CNY",
        "createdAt": "2026-07-31T18:00:00+08:00",
        "updatedAt": "2026-07-31T18:00:00+08:00",
    }
    if member_id is not None:
        props["memberId"] = member_id
    return {
        "ot": "Order",
        "source_pk": order_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": props,
    }


def _make_pipeline(pid: str = "P05", target_ot: str = "Order") -> SimpleNamespace:
    return SimpleNamespace(id=pid, config={"target_ot": target_ot})


def _links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if "link_type" in r]


def _placed_by_lite_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in _links(rows) if r["link_type"] == "Order.placedByLite"]


# ═══════════════════════════════════════════════
# Section 1: placedByLite Link 构造（FR-D1.5-3）
# ═══════════════════════════════════════════════


def test_p05_order_row_constructs_placed_by_lite_link() -> None:
    """FR-D1.5-3: P05 Order 行含 memberId MUST 构造 placedByLite Link。"""
    rows = [order_row(order_id="100", member_id="1001")]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    links = _placed_by_lite_links(result)
    assert len(links) == 1


def test_placed_by_lite_link_direction_is_order_to_customer_lite() -> None:
    """FR-D1.5-3: placedByLite 方向 = Order → CustomerLite（与 CORE_LINK_TYPES 一致）。"""
    rows = [order_row(order_id="100", member_id="1001")]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    link = _placed_by_lite_links(result)[0]
    assert link["source_type"] == "Order"
    assert link["target_type"] == "CustomerLite"


def test_placed_by_lite_link_uses_order_id_as_source_pk() -> None:
    """FR-D1.5-3: source_pk = order_id（row.source_pk）。"""
    rows = [order_row(order_id="100", member_id="1001")]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    link = _placed_by_lite_links(result)[0]
    assert link["source_pk"] == "100"


def test_placed_by_lite_link_uses_member_id_as_target_source_pk() -> None:
    """FR-D1.5-3: target_source_pk = member_id（row.properties.memberId）。"""
    rows = [order_row(order_id="100", member_id="1001")]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    link = _placed_by_lite_links(result)[0]
    assert link["target_source_pk"] == "1001"


def test_placed_by_lite_link_type_is_dot_format() -> None:
    """FR-D1.5-3: link_type 输出点号名 "Order.placedByLite"（非简短名 "placedByLite"）。"""
    rows = [order_row(order_id="100", member_id="1001")]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    link = _placed_by_lite_links(result)[0]
    assert link["link_type"] == "Order.placedByLite"
    # 简短名不应出现在输出
    link_types = {r["link_type"] for r in _links(result)}
    assert "placedByLite" not in link_types


def test_placed_by_lite_link_appended_after_original_rows() -> None:
    """FR-D1.5-3: Link 行追加到 rows 末尾，原 Object 行不变。"""
    rows = [order_row(order_id="100", member_id="1001")]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    # 第一项是原 Object 行（含 ot 字段），后续是 Link 行
    assert result[0]["ot"] == "Order"
    assert "link_type" not in result[0]
    # 末尾是 placedByLite Link 行
    assert result[-1]["link_type"] == "Order.placedByLite"


def test_placed_by_lite_link_carries_source_updated_at() -> None:
    """FR-D1.5-3: Link 行携带 source_updated_at（与 D1 6 条 Link 一致）。"""
    rows = [order_row(order_id="100", member_id="1001", when=NOW)]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    link = _placed_by_lite_links(result)[0]
    assert link["source_updated_at"] == NOW
    assert link["is_deleted"] is False
    assert link["properties"] == {}


# ═══════════════════════════════════════════════
# Section 2: 完整性门禁（FR-D1.5-3 跳过逻辑）
# ═══════════════════════════════════════════════


def test_member_id_missing_skips_link_construction() -> None:
    """FR-D1.5-3: memberId 缺失时跳过 Link 构造（不进 DLQ，因 D1 P05 已声明保留关联键）。"""
    rows = [order_row(order_id="100", member_id=None)]  # 省略 memberId 键
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    assert _placed_by_lite_links(result) == []


def test_member_id_zero_string_skips_link_construction() -> None:
    """FR-D1.5-3: memberId="0" 时跳过 Link 构造。"""
    rows = [order_row(order_id="100", member_id="0")]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    assert _placed_by_lite_links(result) == []


def test_member_id_zero_int_skips_link_construction() -> None:
    """FR-D1.5-3: memberId=0（int）时跳过 Link 构造。"""
    rows = [order_row(order_id="100", member_id=0)]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    assert _placed_by_lite_links(result) == []


def test_member_id_empty_string_skips_link_construction() -> None:
    """FR-D1.5-3: memberId="" 时跳过 Link 构造。"""
    rows = [order_row(order_id="100", member_id="")]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    assert _placed_by_lite_links(result) == []


def test_skipped_link_does_not_add_error_rows() -> None:
    """FR-D1.5-3: 跳过的 Link 不产生错误行（只是不构造，不进 DLQ）。

    原 Object 行原样保留，无额外错误/Link 行混入。
    """
    rows = [order_row(order_id="100", member_id=None)]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    # 只有原 Object 行，无任何 Link 行
    assert len(result) == 1
    assert "link_type" not in result[0]


# ═══════════════════════════════════════════════
# Section 3: 多行场景
# ═══════════════════════════════════════════════


def test_multiple_order_rows_each_get_placed_by_lite_link() -> None:
    """FR-D1.5-3: 多行 Order 各自构造 placedByLite Link。"""
    rows = [
        order_row(order_id="100", member_id="1001"),
        order_row(order_id="101", member_id="1002"),
        order_row(order_id="102", member_id="1003"),
    ]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    links = _placed_by_lite_links(result)
    assert len(links) == 3
    # 每条 Link 的 source_pk/target_source_pk 对应
    pairs = {(l["source_pk"], l["target_source_pk"]) for l in links}
    assert pairs == {("100", "1001"), ("101", "1002"), ("102", "1003")}


def test_mixed_valid_invalid_rows_only_valid_get_links() -> None:
    """FR-D1.5-3: 有效/无效 memberId 混合时，仅有效行构造 Link。"""
    rows = [
        order_row(order_id="100", member_id="1001"),  # 有效
        order_row(order_id="101", member_id=None),     # 缺失
        order_row(order_id="102", member_id="0"),      # 0
        order_row(order_id="103", member_id="1004"),    # 有效
    ]
    pipeline = _make_pipeline()

    result = build_link_rows(rows, pipeline)

    links = _placed_by_lite_links(result)
    assert len(links) == 2
    source_pks = {l["source_pk"] for l in links}
    assert source_pks == {"100", "103"}


# ═══════════════════════════════════════════════
# Section 4: dispatch 集成
# ═══════════════════════════════════════════════


def test_build_link_rows_dispatches_order_to_placed_by_lite() -> None:
    """FR-D1.5-3: build_link_rows 对 target_ot=Order 分发到 placedByLite 构造器。"""
    rows = [order_row(order_id="100", member_id="1001")]
    pipeline = _make_pipeline(target_ot="Order")

    result = build_link_rows(rows, pipeline)

    assert len(_placed_by_lite_links(result)) == 1


def test_build_link_rows_dispatches_by_pipeline_id_p05() -> None:
    """FR-D1.5-3: pipeline.id=P05（无 config.target_ot）也能推断为 Order → 构造 placedByLite。"""
    rows = [order_row(order_id="100", member_id="1001")]
    pipeline = SimpleNamespace(id="P05")  # 无 config，靠 id 推断

    result = build_link_rows(rows, pipeline)

    assert len(_placed_by_lite_links(result)) == 1


def test_non_order_target_ot_does_not_construct_placed_by_lite() -> None:
    """FR-D1.5-3: target_ot 非 Order（如 ProductSku）不构造 placedByLite。"""
    rows = [order_row(order_id="100", member_id="1001")]
    pipeline = _make_pipeline(target_ot="ProductSku")

    result = build_link_rows(rows, pipeline)

    assert _placed_by_lite_links(result) == []
