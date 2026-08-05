"""D1-W1: link_type 映射层专项测试（FR-D1 Phase C）。

验证 ec_link_builder 的 _make_link 映射层：把 frozen/02 简短名转换为
CORE_LINK_TYPES 点号名，并对 hasSku/ships 反转 source/target 方向。

映射规则（与 ecom_core_models.CORE_LINK_TYPES 对齐）：
| frozen/02 简短名 | 方向             | CORE 点号名           | CORE 方向             | 处理     |
|------------------|------------------|-----------------------|-----------------------|----------|
| hasSku           | Product→ProductSku | ProductSku.ofProduct  | ProductSku→Product    | 反转方向 |
| inCategory       | Product→Category | Product.inCategory    | Product→Category      | 同向改名 |
| contains         | Order→OrderLine  | Order.lines           | Order→OrderLine       | 同向改名 |
| forProduct       | OrderLine→Product | OrderLine.ofProduct   | OrderLine→Product     | 同向改名 |
| forSku           | OrderLine→ProductSku | OrderLine.ofSku     | OrderLine→ProductSku  | 同向改名 |
| ships            | Shipment→Order   | Order.fulfilledBy     | Order→Shipment        | 反转方向 |

约束：
- 未知 link_type 透传原值（不映射、不反转）
- 映射层在 _make_link 内部，所有 6 条 Link 构造器自动受益
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from aos_api.ec_link_builder import build_link_rows

NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════
# row 工厂（与 test_ec_d1_link_builder.py 对齐）
# ═══════════════════════════════════════════════


def _sku_row(*, source_pk: str = "s-1", product_id: str = "g-1") -> dict:
    return {
        "ot": "ProductSku",
        "source_pk": source_pk,
        "source_updated_at": NOW,
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


def _product_row(*, source_pk: str = "g-1", category_id: str = "c-1") -> dict:
    return {
        "ot": "Product",
        "source_pk": source_pk,
        "source_updated_at": NOW,
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


def _orderline_row(
    *,
    source_pk: str = "og-1",
    order_id: str = "o-1",
    goods_id: str = "g-1",
    sku_id: str = "s-1",
) -> dict:
    return {
        "ot": "OrderLine",
        "source_pk": source_pk,
        "source_updated_at": NOW,
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


def _shipment_row(*, source_pk: str = "sh-1", order_id: str = "o-1") -> dict:
    return {
        "ot": "Shipment",
        "source_pk": source_pk,
        "source_updated_at": NOW,
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


def _make_pipeline(pid: str, target_ot: str) -> SimpleNamespace:
    return SimpleNamespace(id=pid, config={"target_ot": target_ot})


def _links(rows: list[dict]) -> list[dict]:
    return [r for r in rows if "link_type" in r]


def _link_by_type(rows: list[dict], link_type: str) -> dict:
    """按 link_type 精确匹配取唯一 Link 行。"""
    matches = [r for r in _links(rows) if r["link_type"] == link_type]
    assert len(matches) == 1, f"期望 1 条 {link_type}，实际 {len(matches)} 条"
    return matches[0]


# ═══════════════════════════════════════════════
# 1. hasSku → ProductSku.ofProduct（反转方向）
# ═══════════════════════════════════════════════


def test_hasSku_maps_to_ProductSku_ofProduct_and_reverses_direction() -> None:
    """hasSku: 简短名 → ProductSku.ofProduct，且 source/target 反转。

    frozen/02: Product(g-1) → ProductSku(s-1)
    CORE:      ProductSku(s-1) → Product(g-1)
    """
    rows = [_sku_row(source_pk="s-1", product_id="g-1")]
    pipeline = _make_pipeline("P03", "ProductSku")

    result = build_link_rows(rows, pipeline)

    link = _link_by_type(result, "ProductSku.ofProduct")
    # 反转后：source 是 ProductSku，target 是 Product
    assert link["source_type"] == "ProductSku"
    assert link["source_pk"] == "s-1"
    assert link["target_type"] == "Product"
    assert link["target_source_pk"] == "g-1"
    assert link["source_updated_at"] == NOW
    assert link["is_deleted"] is False
    assert link["properties"] == {}


def test_hasSku_no_short_name_in_output() -> None:
    """hasSku: 映射后输出不含简短名 'hasSku'。"""
    rows = [_sku_row(source_pk="s-1", product_id="g-1")]
    pipeline = _make_pipeline("P03", "ProductSku")

    result = build_link_rows(rows, pipeline)

    link_types = {r["link_type"] for r in _links(result)}
    assert "hasSku" not in link_types
    assert "ProductSku.ofProduct" in link_types


# ═══════════════════════════════════════════════
# 2. ships → Order.fulfilledBy（反转方向）
# ═══════════════════════════════════════════════


def test_ships_maps_to_Order_fulfilledBy_and_reverses_direction() -> None:
    """ships: 简短名 → Order.fulfilledBy，且 source/target 反转。

    frozen/02: Shipment(sh-1) → Order(o-1)
    CORE:      Order(o-1) → Shipment(sh-1)
    """
    rows = [_shipment_row(source_pk="sh-1", order_id="o-1")]
    pipeline = _make_pipeline("P07", "Shipment")

    result = build_link_rows(rows, pipeline)

    link = _link_by_type(result, "Order.fulfilledBy")
    # 反转后：source 是 Order，target 是 Shipment
    assert link["source_type"] == "Order"
    assert link["source_pk"] == "o-1"
    assert link["target_type"] == "Shipment"
    assert link["target_source_pk"] == "sh-1"
    assert link["source_updated_at"] == NOW
    assert link["is_deleted"] is False
    assert link["properties"] == {}


def test_ships_no_short_name_in_output() -> None:
    """ships: 映射后输出不含简短名 'ships'。"""
    rows = [_shipment_row(source_pk="sh-1", order_id="o-1")]
    pipeline = _make_pipeline("P07", "Shipment")

    result = build_link_rows(rows, pipeline)

    link_types = {r["link_type"] for r in _links(result)}
    assert "ships" not in link_types
    assert "Order.fulfilledBy" in link_types


# ═══════════════════════════════════════════════
# 3. inCategory → Product.inCategory（同向）
# ═══════════════════════════════════════════════


def test_inCategory_maps_to_Product_inCategory_same_direction() -> None:
    """inCategory: 简短名 → Product.inCategory，source/target 不变。"""
    rows = [_product_row(source_pk="g-1", category_id="c-1")]
    pipeline = _make_pipeline("P02", "Product")

    result = build_link_rows(rows, pipeline)

    link = _link_by_type(result, "Product.inCategory")
    assert link["source_type"] == "Product"
    assert link["source_pk"] == "g-1"
    assert link["target_type"] == "Category"
    assert link["target_source_pk"] == "c-1"


# ═══════════════════════════════════════════════
# 4. contains → Order.lines（同向）
# ═══════════════════════════════════════════════


def test_contains_maps_to_Order_lines_same_direction() -> None:
    """contains: 简短名 → Order.lines，source/target 不变。"""
    rows = [_orderline_row(source_pk="og-1", order_id="o-1", goods_id="", sku_id="0")]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    link = _link_by_type(result, "Order.lines")
    assert link["source_type"] == "Order"
    assert link["source_pk"] == "o-1"
    assert link["target_type"] == "OrderLine"
    assert link["target_source_pk"] == "og-1"


# ═══════════════════════════════════════════════
# 5. forProduct → OrderLine.ofProduct（同向）
# ═══════════════════════════════════════════════


def test_forProduct_maps_to_OrderLine_ofProduct_same_direction() -> None:
    """forProduct: 简短名 → OrderLine.ofProduct，source/target 不变。"""
    rows = [_orderline_row(source_pk="og-1", order_id="0", goods_id="g-1", sku_id="0")]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    link = _link_by_type(result, "OrderLine.ofProduct")
    assert link["source_type"] == "OrderLine"
    assert link["source_pk"] == "og-1"
    assert link["target_type"] == "Product"
    assert link["target_source_pk"] == "g-1"


# ═══════════════════════════════════════════════
# 6. forSku → OrderLine.ofSku（同向）
# ═══════════════════════════════════════════════


def test_forSku_maps_to_OrderLine_ofSku_same_direction() -> None:
    """forSku: 简短名 → OrderLine.ofSku，source/target 不变。"""
    rows = [_orderline_row(source_pk="og-1", order_id="0", goods_id="0", sku_id="s-1")]
    pipeline = _make_pipeline("P06", "OrderLine")

    result = build_link_rows(rows, pipeline)

    link = _link_by_type(result, "OrderLine.ofSku")
    assert link["source_type"] == "OrderLine"
    assert link["source_pk"] == "og-1"
    assert link["target_type"] == "ProductSku"
    assert link["target_source_pk"] == "s-1"


# ═══════════════════════════════════════════════
# 7. 未知 link_type 透传（不映射、不反转）
# ═══════════════════════════════════════════════


def test_unknown_link_type_passthrough() -> None:
    """未知 link_type 透传原值（不在 _FROZEN_TO_CORE 中的不映射）。

    通过直接调用 _make_link 验证（绕过 6 个构造器的已知 link_type）。
    """
    from aos_api.ec_link_builder import _make_link

    row = {"source_updated_at": NOW}
    result = _make_link(
        link_type="customLink",
        source_type="Foo",
        source_pk="f-1",
        target_type="Bar",
        target_source_pk="b-1",
        row=row,
    )

    assert result["link_type"] == "customLink"
    assert result["source_type"] == "Foo"
    assert result["source_pk"] == "f-1"
    assert result["target_type"] == "Bar"
    assert result["target_source_pk"] == "b-1"


def test_unknown_link_type_no_reverse() -> None:
    """未知 link_type 即使名字像需要反转也不反转（只对 _REVERSED_LINKS 中的反转）。"""
    from aos_api.ec_link_builder import _make_link

    row = {"source_updated_at": NOW}
    # 用一个不在映射表里的名字
    result = _make_link(
        link_type="unknownLink",
        source_type="Src",
        source_pk="s-1",
        target_type="Tgt",
        target_source_pk="t-1",
        row=row,
    )

    # 未知 link_type 不反转
    assert result["source_type"] == "Src"
    assert result["source_pk"] == "s-1"
    assert result["target_type"] == "Tgt"
    assert result["target_source_pk"] == "t-1"


# ═══════════════════════════════════════════════
# 8. 6 条 Link 综合场景：所有映射 + 方向正确
# ═══════════════════════════════════════════════


def test_all_six_link_types_mapped_correctly() -> None:
    """综合：6 条 Link 全部映射为点号名，方向与 CORE_LINK_TYPES 一致。

    构造场景：
    - P03 ProductSku: 1 条 hasSku → ProductSku.ofProduct
    - P02 Product: 1 条 inCategory → Product.inCategory
    - P06 OrderLine: 3 条 contains/forProduct/forSku
    - P07 Shipment: 1 条 ships → Order.fulfilledBy
    """
    # P03: hasSku
    sku_rows = [_sku_row(source_pk="s-1", product_id="g-1")]
    sku_pipeline = _make_pipeline("P03", "ProductSku")
    sku_result = build_link_rows(sku_rows, sku_pipeline)

    # P02: inCategory
    product_rows = [_product_row(source_pk="g-1", category_id="c-1")]
    product_pipeline = _make_pipeline("P02", "Product")
    product_result = build_link_rows(product_rows, product_pipeline)

    # P06: contains + forProduct + forSku
    orderline_rows = [_orderline_row(source_pk="og-1", order_id="o-1", goods_id="g-1", sku_id="s-1")]
    orderline_pipeline = _make_pipeline("P06", "OrderLine")
    orderline_result = build_link_rows(orderline_rows, orderline_pipeline)

    # P07: ships
    shipment_rows = [_shipment_row(source_pk="sh-1", order_id="o-1")]
    shipment_pipeline = _make_pipeline("P07", "Shipment")
    shipment_result = build_link_rows(shipment_rows, shipment_pipeline)

    # 汇总所有 Link
    all_links = (
        _links(sku_result)
        + _links(product_result)
        + _links(orderline_result)
        + _links(shipment_result)
    )

    # 6 条 Link，全部是点号名
    link_types = {link["link_type"] for link in all_links}
    assert link_types == {
        "ProductSku.ofProduct",
        "Product.inCategory",
        "Order.lines",
        "OrderLine.ofProduct",
        "OrderLine.ofSku",
        "Order.fulfilledBy",
    }

    # 验证反转的 2 条方向正确
    has_sku_link = _link_by_type(sku_result, "ProductSku.ofProduct")
    assert has_sku_link["source_type"] == "ProductSku"
    assert has_sku_link["target_type"] == "Product"

    ships_link = _link_by_type(shipment_result, "Order.fulfilledBy")
    assert ships_link["source_type"] == "Order"
    assert ships_link["target_type"] == "Shipment"

    # 验证同向的 4 条方向不变
    in_cat_link = _link_by_type(product_result, "Product.inCategory")
    assert in_cat_link["source_type"] == "Product"
    assert in_cat_link["target_type"] == "Category"

    contains_link = _link_by_type(orderline_result, "Order.lines")
    assert contains_link["source_type"] == "Order"
    assert contains_link["target_type"] == "OrderLine"

    for_product_link = _link_by_type(orderline_result, "OrderLine.ofProduct")
    assert for_product_link["source_type"] == "OrderLine"
    assert for_product_link["target_type"] == "Product"

    for_sku_link = _link_by_type(orderline_result, "OrderLine.ofSku")
    assert for_sku_link["source_type"] == "OrderLine"
    assert for_sku_link["target_type"] == "ProductSku"


def test_all_output_link_types_are_dotted_names() -> None:
    """所有输出的 link_type 都是点号名（不含简短名）。

    遍历 4 个构造器的输出，确认没有任何简短名残留。
    """
    test_cases = [
        ([_sku_row()], _make_pipeline("P03", "ProductSku")),
        ([_product_row()], _make_pipeline("P02", "Product")),
        ([_orderline_row()], _make_pipeline("P06", "OrderLine")),
        ([_shipment_row()], _make_pipeline("P07", "Shipment")),
    ]

    short_names = {"hasSku", "inCategory", "contains", "forProduct", "forSku", "ships"}

    for rows, pipeline in test_cases:
        result = build_link_rows(rows, pipeline)
        for link in _links(result):
            assert link["link_type"] not in short_names, (
                f"link_type {link['link_type']!r} 不应是简短名"
            )
            assert "." in link["link_type"], (
                f"link_type {link['link_type']!r} 应是点号名（含 '.'）"
            )
