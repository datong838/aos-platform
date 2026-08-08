"""D1-W3: Link 行构造专项测试（FR-D1-8）。

覆盖 6 条核心 Link 的构造逻辑与边界：
- hasSku: Product → ProductSku（P03 读取时构造）
- inCategory: Product → Category（P02 读取时构造，多值字符串拆分）
- contains: Order → OrderLine（P06 读取时构造）
- forProduct: OrderLine → Product（P06 读取时构造）
- forSku: OrderLine → ProductSku（P06 读取时构造，sku_id=0 跳过）
- ships: Shipment → Order（P07 读取时构造）

约束：
- build_link_rows 只构造 Link 行 dict，不验证 link_type 是否被 CoreLinkRecord 支持
- 悬挂 Link（target 不存在）由 ec_ot_writer / ecom_consistency_store 拒绝，本模块只负责构造
- 不构造 placedByLite Link（D1.5 才落地）
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from aos_api.ec_link_builder import build_link_rows

NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════
# row 工厂（OT 行格式，与 sink_to_ot 兼容）
# ═══════════════════════════════════════════════


def product_row(*, source_pk: str = "g-1", category_id: str = "c-1", when: datetime = NOW) -> dict:
    """P02 Product 行：categoryId 多值字符串。"""
    return {
        "ot": "Product",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "shopId": "1",
            "title": "测试商品",
            "status": "active",
            "categoryId": category_id,
            "createdAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def sku_row(*, source_pk: str = "s-1", product_id: str = "g-1", when: datetime = NOW) -> dict:
    """P03 ProductSku 行：productId 指向 Product。"""
    return {
        "ot": "ProductSku",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "productId": product_id,
            "status": "active",
            "barcode": "BC-001",
            "price": "99.00",
            "currency": "CNY",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def orderline_row(
    *,
    source_pk: str = "og-1",
    order_id: str = "o-1",
    goods_id: str = "g-1",
    sku_id: str = "s-1",
    when: datetime = NOW,
) -> dict:
    """P06 OrderLine 行：orderId/goodsId/skuId 指向多端。"""
    return {
        "ot": "OrderLine",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "orderId": order_id,
            "skuId": sku_id,
            "goodsId": goods_id,
            "quantity": 1,
            "unitPrice": "99.00",
            "lineAmount": "99.00",
            "currency": "CNY",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def shipment_row(*, source_pk: str = "sh-1", order_id: str = "o-1", when: datetime = NOW) -> dict:
    """P07 Shipment 行：orderId 指向 Order。"""
    return {
        "ot": "Shipment",
        "source_pk": source_pk,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "properties": {
            "orderId": order_id,
            "status": "shipped",
            "carrier": "SF",
            "trackingNo": "SF123",
            "shippedAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def _make_pipeline(pid: str = "", target_ot: str | None = None) -> SimpleNamespace:
    """构造 pipeline mock：config 有 target_ot 时优先，否则用 pid 推断。"""
    config = {"target_ot": target_ot} if target_ot else {}
    return SimpleNamespace(id=pid, config=config)


def _links(rows: list[dict]) -> list[dict]:
    """从 build_link_rows 输出中提取 Link 行。"""
    return [r for r in rows if "link_type" in r]


# ═══════════════════════════════════════════════
# 1. hasSku: Product → ProductSku
# ═══════════════════════════════════════════════


def test_hasSku_normal_construction() -> None:
    """hasSku: P03 ProductSku 行构造一条 ProductSku → Product Link（W1 反转后）。"""
    rows = [sku_row(source_pk="s-1", product_id="g-1")]
    pipeline = _make_pipeline("P03", "ProductSku")

    result = build_link_rows(rows, pipeline)

    assert len(result) == 2  # 1 原始行 + 1 Link
    link = _links(result)[0]
    assert link["link_type"] == "ProductSku.ofProduct"
    assert link["source_type"] == "ProductSku"
    assert link["source_pk"] == "s-1"
    assert link["target_type"] == "Product"
    assert link["target_source_pk"] == "g-1"
    assert link["source_updated_at"] == NOW
    assert link["is_deleted"] is False
    assert link["properties"] == {}


def test_hasSku_skips_empty_product_id() -> None:
    """hasSku: productId 为空/0/缺失时跳过。"""
    rows = [
        sku_row(source_pk="s-1", product_id=""),
        sku_row(source_pk="s-2", product_id="0"),
        {"ot": "ProductSku", "source_pk": "s-3", "source_updated_at": NOW, "properties": {}},
    ]
    pipeline = _make_pipeline("P03", "ProductSku")

    result = build_link_rows(rows, pipeline)

    assert len(result) == 3  # 3 原始行，无 Link 追加
    assert _links(result) == []


def test_hasSku_multiple_skus_same_product() -> None:
    """hasSku: 多个 SKU 指向同一 Product，构造多条 Link（W1 反转后 source 是各 SKU）。"""
    rows = [
        sku_row(source_pk="s-1", product_id="g-1"),
        sku_row(source_pk="s-2", product_id="g-1"),
        sku_row(source_pk="s-3", product_id="g-1"),
    ]
    pipeline = _make_pipeline("P03", "ProductSku")

    result = build_link_rows(rows, pipeline)

    links = _links(result)
    assert len(links) == 3
    for link in links:
        assert link["link_type"] == "ProductSku.ofProduct"
        assert link["target_source_pk"] == "g-1"
    assert {link["source_pk"] for link in links} == {"s-1", "s-2", "s-3"}


# ═══════════════════════════════════════════════
# 2. inCategory: Product → Category
# ═══════════════════════════════════════════════


def test_inCategory_single_value() -> None:
    """inCategory: 单值 categoryId 构造一条 Link + O1-A sellsProduct。"""
    rows = [product_row(source_pk="g-1", category_id="c-1")]
    pipeline = _make_pipeline("P02", "Product")

    result = build_link_rows(rows, pipeline)

    links = _links(result)
    # O1-A: Product builder 同时构造 inCategory + sellsProduct
    in_cat = [l for l in links if l["link_type"] == "Product.inCategory"]
    sells = [l for l in links if l["link_type"] == "Shop.sellsProduct"]
    assert len(in_cat) == 1
    assert len(sells) == 1

    link = in_cat[0]
    assert link["source_type"] == "Product"
    assert link["source_pk"] == "g-1"
    assert link["target_type"] == "Category"
    assert link["target_source_pk"] == "c-1"

    sell_link = sells[0]
    assert sell_link["source_type"] == "Shop"
    assert sell_link["target_type"] == "Product"
    assert sell_link["target_source_pk"] == "g-1"


def test_inCategory_multi_value_split() -> None:
    """inCategory: 多值字符串 '1,2,3' 拆分为 3 条 Link + 1 条 sellsProduct。"""
    rows = [product_row(source_pk="g-1", category_id="1,2,3")]
    pipeline = _make_pipeline("P02", "Product")

    result = build_link_rows(rows, pipeline)

    links = _links(result)
    in_cat = [l for l in links if l["link_type"] == "Product.inCategory"]
    sells = [l for l in links if l["link_type"] == "Shop.sellsProduct"]
    assert len(in_cat) == 3
    assert len(sells) == 1
    assert {link["target_source_pk"] for link in in_cat} == {"1", "2", "3"}
    for link in in_cat:
        assert link["source_pk"] == "g-1"


def test_inCategory_empty_value() -> None:
    """inCategory: categoryId 为空/缺失时跳过（sellsProduct 仍生成）。"""
    rows = [
        product_row(source_pk="g-1", category_id=""),
        {"ot": "Product", "source_pk": "g-2", "source_updated_at": NOW, "properties": {}},
    ]
    pipeline = _make_pipeline("P02", "Product")

    result = build_link_rows(rows, pipeline)

    # O1-A: sellsProduct 对每个 product 行生成一条 Link（inCategory 为空）
    links = _links(result)
    in_cat = [l for l in links if l["link_type"] == "Product.inCategory"]
    sells = [l for l in links if l["link_type"] == "Shop.sellsProduct"]
    assert len(in_cat) == 0
    assert len(sells) == 2


def test_inCategory_abnormal_value() -> None:
    """inCategory: 异常值（含空格/连续逗号）正确拆分 + sellsProduct。"""
    rows = [product_row(source_pk="g-1", category_id=" 1 , , 2 , 3 ")]
    pipeline = _make_pipeline("P02", "Product")

    result = build_link_rows(rows, pipeline)

    links = _links(result)
    in_cat = [l for l in links if l["link_type"] == "Product.inCategory"]
    sells = [l for l in links if l["link_type"] == "Shop.sellsProduct"]
    assert len(in_cat) == 3
    assert len(sells) == 1
    assert {link["target_source_pk"] for link in in_cat} == {"1", "2", "3"}


# ═══════════════════════════════════════════════
# 3. contains: Order → OrderLine
# ═══════════════════════════════════════════════


def test_contains_normal_construction() -> None:
    """contains: P06 OrderLine 行构造一条 Order → OrderLine Link。"""
    rows = [orderline_row(source_pk="og-1", order_id="o-1")]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    contains_links = [r for r in _links(result) if r["link_type"] == "Order.lines"]
    assert len(contains_links) == 1
    link = contains_links[0]
    assert link["source_type"] == "Order"
    assert link["source_pk"] == "o-1"
    assert link["target_type"] == "OrderLine"
    assert link["target_source_pk"] == "og-1"


def test_contains_skips_empty_order_id() -> None:
    """contains: orderId 为空/0/缺失时跳过。"""
    rows = [
        orderline_row(source_pk="og-1", order_id=""),
        orderline_row(source_pk="og-2", order_id="0"),
        {"ot": "OrderLine", "source_pk": "og-3", "source_updated_at": NOW, "properties": {}},
    ]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    contains_links = [r for r in _links(result) if r["link_type"] == "Order.lines"]
    assert contains_links == []


# ═══════════════════════════════════════════════
# 4. forProduct: OrderLine → Product
# ═══════════════════════════════════════════════


def test_forProduct_normal_construction() -> None:
    """forProduct: P06 OrderLine 行构造一条 OrderLine → Product Link。"""
    rows = [orderline_row(source_pk="og-1", goods_id="g-1")]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    fp_links = [r for r in _links(result) if r["link_type"] == "OrderLine.ofProduct"]
    assert len(fp_links) == 1
    link = fp_links[0]
    assert link["source_type"] == "OrderLine"
    assert link["source_pk"] == "og-1"
    assert link["target_type"] == "Product"
    assert link["target_source_pk"] == "g-1"


def test_forProduct_skips_empty_goods_id() -> None:
    """forProduct: goodsId 为空/0/缺失时跳过。"""
    rows = [
        orderline_row(source_pk="og-1", goods_id=""),
        orderline_row(source_pk="og-2", goods_id="0"),
    ]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    fp_links = [r for r in _links(result) if r["link_type"] == "OrderLine.ofProduct"]
    assert fp_links == []


# ═══════════════════════════════════════════════
# 5. forSku: OrderLine → ProductSku
# ═══════════════════════════════════════════════


def test_forSku_normal_construction() -> None:
    """forSku: P06 OrderLine 行构造一条 OrderLine → ProductSku Link。"""
    rows = [orderline_row(source_pk="og-1", sku_id="s-1")]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    fs_links = [r for r in _links(result) if r["link_type"] == "OrderLine.ofSku"]
    assert len(fs_links) == 1
    link = fs_links[0]
    assert link["source_type"] == "OrderLine"
    assert link["source_pk"] == "og-1"
    assert link["target_type"] == "ProductSku"
    assert link["target_source_pk"] == "s-1"


def test_forSku_skips_zero_sku_id() -> None:
    """forSku: sku_id=0 时跳过（frozen/02 规则需样本核验）。"""
    rows = [
        orderline_row(source_pk="og-1", sku_id="0"),
        orderline_row(source_pk="og-2", sku_id=0),
        orderline_row(source_pk="og-3", sku_id=""),
    ]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    fs_links = [r for r in _links(result) if r["link_type"] == "OrderLine.ofSku"]
    assert fs_links == []


# ═══════════════════════════════════════════════
# 6. ships: Shipment → Order
# ═══════════════════════════════════════════════


def test_ships_normal_construction() -> None:
    """ships: P07 Shipment 行构造一条 Order → Shipment Link（W1 反转后）。"""
    rows = [shipment_row(source_pk="sh-1", order_id="o-1")]
    pipeline = _make_pipeline("P07", "Shipment")

    result = build_link_rows(rows, pipeline)

    links = _links(result)
    assert len(links) == 1
    link = links[0]
    assert link["link_type"] == "Order.fulfilledBy"
    assert link["source_type"] == "Order"
    assert link["source_pk"] == "o-1"
    assert link["target_type"] == "Shipment"
    assert link["target_source_pk"] == "sh-1"


def test_ships_skips_empty_order_id() -> None:
    """ships: orderId 为空/0/缺失时跳过。"""
    rows = [
        shipment_row(source_pk="sh-1", order_id=""),
        shipment_row(source_pk="sh-2", order_id="0"),
        {"ot": "Shipment", "source_pk": "sh-3", "source_updated_at": NOW, "properties": {}},
    ]
    pipeline = _make_pipeline("P07", "Shipment")

    result = build_link_rows(rows, pipeline)

    assert _links(result) == []


# ═══════════════════════════════════════════════
# 7. 分发逻辑
# ═══════════════════════════════════════════════


def test_dispatch_by_config_target_ot() -> None:
    """分发：pipeline.config.target_ot 优先。"""
    rows = [sku_row(source_pk="s-1", product_id="g-1")]
    pipeline = _make_pipeline("any-pid", "ProductSku")

    result = build_link_rows(rows, pipeline)

    assert len(_links(result)) == 1


def test_dispatch_by_pipeline_id_inference() -> None:
    """分发：无 target_ot 时用 pipeline.id 推断（P03 → ProductSku）。"""
    rows = [sku_row(source_pk="s-1", product_id="g-1")]
    pipeline = _make_pipeline("P03")  # 无 config.target_ot

    result = build_link_rows(rows, pipeline)

    assert len(_links(result)) == 1


def test_dispatch_unknown_target_ot_no_links() -> None:
    """分发：未知 target_ot（如 P01 Shop）不构造任何 Link。"""
    rows = [{"ot": "Shop", "source_pk": "1", "source_updated_at": NOW, "properties": {}}]
    pipeline = _make_pipeline("P01", "Shop")

    result = build_link_rows(rows, pipeline)

    assert _links(result) == []


def test_dispatch_empty_rows_returns_empty() -> None:
    """分发：空 rows 返回空 list。"""
    pipeline = _make_pipeline("P03", "ProductSku")

    result = build_link_rows([], pipeline)

    assert result == []


def test_orderline_constructs_three_link_types() -> None:
    """P06 OrderLine 行同时构造 contains + forProduct + forSku 三条 Link。"""
    rows = [orderline_row(source_pk="og-1", order_id="o-1", goods_id="g-1", sku_id="s-1")]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    link_types = {link["link_type"] for link in _links(result)}
    assert link_types == {"Order.lines", "OrderLine.ofProduct", "OrderLine.ofSku"}


def test_link_row_has_no_ot_field() -> None:
    """Link 行不含 ot 字段（ec_ot_writer 根据 link_type 字段存在区分 Object/Link 行）。"""
    rows = [sku_row(source_pk="s-1", product_id="g-1")]
    pipeline = _make_pipeline("P03", "ProductSku")

    result = build_link_rows(rows, pipeline)

    link = _links(result)[0]
    assert "ot" not in link


def test_link_source_updated_at_inherited_from_row() -> None:
    """Link 的 source_updated_at 取 source 行的 source_updated_at。"""
    custom_when = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    rows = [sku_row(source_pk="s-1", product_id="g-1", when=custom_when)]
    pipeline = _make_pipeline("P03", "ProductSku")

    result = build_link_rows(rows, pipeline)

    link = _links(result)[0]
    assert link["source_updated_at"] == custom_when


def test_pipeline_mock_without_config_attr() -> None:
    """pipeline 可能是无 config 属性的 mock：getattr 安全取值，不抛异常。"""
    rows = [sku_row(source_pk="s-1", product_id="g-1")]
    pipeline = SimpleNamespace(id="P03")  # 无 config 属性

    result = build_link_rows(rows, pipeline)

    assert len(_links(result)) == 1


def test_pipeline_mock_without_id_attr() -> None:
    """pipeline 可能是无 id 属性的 mock：getattr 安全取值，不构造 Link。"""
    rows = [sku_row(source_pk="s-1", product_id="g-1")]
    pipeline = SimpleNamespace(config={})  # 无 id 属性

    result = build_link_rows(rows, pipeline)

    assert _links(result) == []
