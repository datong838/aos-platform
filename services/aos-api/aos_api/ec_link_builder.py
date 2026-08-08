"""D1-W3: Link 行构造 — 根据源表行流构造核心 Link 行。

按 pipeline.target_ot 分发构造 6 条核心 Link（frozen/02 规格）：

| Link         | From → To                | 来源字段      | 构造时机                    |
|--------------|--------------------------|---------------|-----------------------------|
| hasSku       | Product → ProductSku     | goods_id      | P03 ProductSku 读取时       |
| inCategory   | Product → Category       | category_id   | P02 Product 读取时（多值拆分）|
| contains     | Order → OrderLine        | order_id      | P06 OrderLine 读取时        |
| forProduct   | OrderLine → Product      | goods_id      | P06 OrderLine 读取时        |
| forSku       | OrderLine → ProductSku   | sku_id        | P06 OrderLine 读取时（sku_id=0 跳过）|
| ships        | Shipment → Order         | order_id      | P07 Shipment 读取时         |

> placedByLite（Order → CustomerLite）在 D1 P05 侧保留 member_id 关联键，D1.5 才落地 Link。

约定（与 ec_ot_writer._normalize_rows 对齐）：
- Link 行含 ``link_type`` 字段 → ec_ot_writer 识别为 Link 行
- Link 行字段：link_type / source_type / source_pk / target_type / target_source_pk /
  source_updated_at / is_deleted / properties
- Link 行不含 ``ot`` 字段（Object 行才有）
- 悬挂 Link（target 不存在）由 ec_ot_writer / ecom_consistency_store 拒绝，本模块只负责构造
"""

from __future__ import annotations

from typing import Any, Callable

# pipeline.id → target_ot 推断表（无 config.target_ot 时回退）
# O1-A: key 改为小写 + startswith 前缀匹配（与 ec_dataset_sink / ec_normalizer 对齐）
_PID_TO_OT: dict[str, str] = {
    "p02": "Product",
    "p03": "ProductSku",
    "p04": "Category",
    "p05": "Order",
    "p06": "OrderLine",
    "p07": "Shipment",
    # D4: P09~P12（frozen/02 §P09~P12）
    "p09": "Weapp",
    "p10": "SystemConfig",
    "p11": "ProductReview",
    "p12": "Payment",
}

# frozen/02 简短名 → CORE_LINK_TYPES 点号名映射（与 ecom_core_models.CORE_LINK_TYPES 对齐）
_FROZEN_TO_CORE: dict[str, str] = {
    "hasSku": "ProductSku.ofProduct",
    "inCategory": "Product.inCategory",
    "contains": "Order.lines",
    "forProduct": "OrderLine.ofProduct",
    "forSku": "OrderLine.ofSku",
    "ships": "Order.fulfilledBy",
    # D1.5: Order → CustomerLite（frozen/02 §P08，同向不反转）
    "placedByLite": "Order.placedByLite",
    # D1: Shop → Product（O1-A: 补 sellsProduct）
    "sellsProduct": "Shop.sellsProduct",
    # D4: 6 条新 Link（frozen/02 §3.5）
    "hasWeapp": "Shop.hasWeapp",
    "hasReview": "Product.hasReview",
    "ofSku": "ProductReview.ofSku",
    "byMember": "ProductReview.byMember",
    "hasPayment": "Order.hasPayment",
    "fromWeapp": "Order.fromWeapp",
}

# 需要反转 source/target 方向的简短名（frozen/02 方向与 CORE 方向相反）
# hasSku: frozen/02 是 Product→ProductSku，CORE 是 ProductSku.ofProduct（子→父），方向相反需反转
# ships:  frozen/02 是 Shipment→Order，CORE 是 Order.fulfilledBy（父→子），方向相反需反转
# D4 的 hasWeapp/hasReview/hasPayment：frozen/02 与 CORE 方向一致（父→子），不反转
_REVERSED_LINKS: frozenset[str] = frozenset({"hasSku", "ships"})


def build_link_rows(
    rows: list[dict[str, Any]],
    pipeline: Any,
) -> list[dict[str, Any]]:
    """根据 rows 构造 Link 行并追加到 rows 末尾。

    按 pipeline.config.target_ot（优先）或 pipeline.id（推断）分发到对应构造器。
    未识别的 target_ot 不构造任何 Link（透传 rows）。
    """
    target_ot = _resolve_target_ot(pipeline)

    builder: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = {
        # O1-A: Product 同时构造 inCategory + sellsProduct
        "Product": _build_product_links,
        "ProductSku": _build_has_sku_links,
        "OrderLine": _build_orderline_links,
        "Shipment": _build_ships_links,
        # D1.5: P05 Order 读取时构造 placedByLite Link（Order → CustomerLite）
        # D4: P05 Order 同时构造 fromWeapp Link（Order → Weapp）
        "Order": _build_order_links,
        # D4: P09 Weapp 读取时构造 hasWeapp Link（Shop → Weapp）
        "Weapp": _build_has_weapp_links,
        # D4: P11 ProductReview 读取时构造 hasReview/ofSku/byMember 三条 Link
        "ProductReview": _build_review_links,
        # D4: P12 Payment 读取时构造 hasPayment Link（Order → Payment）
        "Payment": _build_has_payment_links,
    }.get(target_ot) if target_ot else None

    if builder is None or not rows:
        return rows

    links = builder(rows)
    if not links:
        return rows
    return [*rows, *links]


def _resolve_target_ot(pipeline: Any) -> str | None:
    """从 pipeline 解析 target_ot：config.target_ot 优先，否则用 pipeline.id startswith 前缀匹配。

    O1-A: 从精确匹配改为 startswith 前缀匹配，以处理形如 'p02_qyh_niushop_goods' 的 Pipeline ID。
    """
    config = getattr(pipeline, "config", None) or {}
    target_ot = config.get("target_ot") if isinstance(config, dict) else None
    if target_ot:
        return str(target_ot)
    pid = str(getattr(pipeline, "id", "") or "").lower()
    # startswith 前缀匹配（与 ec_dataset_sink / ec_normalizer 对齐）
    for prefix, ot in _PID_TO_OT.items():
        if pid.startswith(prefix):
            return ot
    return None


# ═══════════════════════════════════════════════
# Link 构造器
# ═══════════════════════════════════════════════


def _build_product_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """O1-A: Product builder — 同时构造 inCategory + sellsProduct。"""
    links: list[dict[str, Any]] = []
    links.extend(_build_in_category_links(rows))
    links.extend(_build_sells_product_links(rows))
    return links


def _build_sells_product_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """sellsProduct: Shop → Product（O1-A: P02 Product 读取时构造）。

    source_pk = row.properties.shopId（site_id，Shop 的 PK）
    target_source_pk = row.source_pk（goods_id，Product 的 PK）
    shopId 缺失时回退默认值 "1"（栖月汇 site_id=1）。
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        goods_id = row.get("source_pk")
        if not _is_valid_pk(goods_id):
            continue
        props = row.get("properties") or {}
        shop_id = str(props.get("shopId") or props.get("siteId") or "1")
        links.append(_make_link(
            link_type="sellsProduct",
            source_type="Shop",
            source_pk=shop_id,
            target_type="Product",
            target_source_pk=goods_id,
            row=row,
        ))
    return links


def _build_has_sku_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """hasSku: Product → ProductSku（P03 ProductSku 读取时，每行一条）。

    source_pk = row.properties.productId（goods_id，Product 的 PK）
    target_source_pk = row.source_pk（sku_id，ProductSku 的 PK）
    productId 为空/0/缺失时跳过。
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        props = row.get("properties") or {}
        product_id = props.get("productId")
        if not _is_valid_pk(product_id):
            continue
        sku_id = row.get("source_pk")
        if not _is_valid_pk(sku_id):
            continue
        links.append(_make_link(
            link_type="hasSku",
            source_type="Product",
            source_pk=product_id,
            target_type="ProductSku",
            target_source_pk=sku_id,
            row=row,
        ))
    return links


def _build_in_category_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """inCategory: Product → Category（P02 Product 读取时，category_id 多值拆分）。

    source_pk = row.source_pk（goods_id）
    target_source_pk = row.properties.categoryId 拆分后的每个 category_id
    categoryId 为空/缺失时跳过。
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        goods_id = row.get("source_pk")
        if not _is_valid_pk(goods_id):
            continue
        props = row.get("properties") or {}
        category_id_raw = props.get("categoryId")
        if category_id_raw is None:
            continue
        for category_id in _split_multi_value(str(category_id_raw)):
            links.append(_make_link(
                link_type="inCategory",
                source_type="Product",
                source_pk=goods_id,
                target_type="Category",
                target_source_pk=category_id,
                row=row,
            ))
    return links


def _build_orderline_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """P06 OrderLine 读取时同时构造 contains + forProduct + forSku 三条 Link。

    contains:   Order → OrderLine（source=orderId, target=order_goods_id）
    forProduct: OrderLine → Product（source=order_goods_id, target=goodsId）
    forSku:     OrderLine → ProductSku（source=order_goods_id, target=skuId；sku_id=0 跳过）
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        order_goods_id = row.get("source_pk")
        props = row.get("properties") or {}
        order_id = props.get("orderId")
        goods_id = props.get("goodsId")
        sku_id = props.get("skuId")

        # contains: Order → OrderLine
        if _is_valid_pk(order_id) and _is_valid_pk(order_goods_id):
            links.append(_make_link(
                link_type="contains",
                source_type="Order",
                source_pk=order_id,
                target_type="OrderLine",
                target_source_pk=order_goods_id,
                row=row,
            ))

        # forProduct: OrderLine → Product
        if _is_valid_pk(order_goods_id) and _is_valid_pk(goods_id):
            links.append(_make_link(
                link_type="forProduct",
                source_type="OrderLine",
                source_pk=order_goods_id,
                target_type="Product",
                target_source_pk=goods_id,
                row=row,
            ))

        # forSku: OrderLine → ProductSku（sku_id=0 跳过）
        if _is_valid_pk(order_goods_id) and _is_valid_non_zero_pk(sku_id):
            links.append(_make_link(
                link_type="forSku",
                source_type="OrderLine",
                source_pk=order_goods_id,
                target_type="ProductSku",
                target_source_pk=sku_id,
                row=row,
            ))
    return links


def _build_ships_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ships: Shipment → Order（P07 Shipment 读取时，每行一条）。

    source_pk = row.source_pk（shipment id）
    target_source_pk = row.properties.orderId
    orderId 为空/0/缺失时跳过。
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        shipment_id = row.get("source_pk")
        if not _is_valid_pk(shipment_id):
            continue
        props = row.get("properties") or {}
        order_id = props.get("orderId")
        if not _is_valid_pk(order_id):
            continue
        links.append(_make_link(
            link_type="ships",
            source_type="Shipment",
            source_pk=shipment_id,
            target_type="Order",
            target_source_pk=order_id,
            row=row,
        ))
    return links


def _build_placed_by_lite_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """placedByLite: Order → CustomerLite（P05 Order 读取时，每行一条）。

    source_pk = row.source_pk（order_id，Order 的 PK）
    target_source_pk = row.properties.memberId（member_id，CustomerLite 的 PK）

    完整性门禁（frozen/02 §P08 + FR-D1.5-3）：
    - memberId 缺失或为 0 时跳过 Link 构造（不进 DLQ，因 D1 P05 已声明保留关联键）
    - P08 未落地前 CustomerLite 不存在时，Link 由 ec_ot_writer/consistency_store 拒绝（本模块只构造）
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        order_id = row.get("source_pk")
        if not _is_valid_pk(order_id):
            continue
        props = row.get("properties") or {}
        member_id = props.get("memberId")
        if not _is_valid_pk(member_id):
            continue
        links.append(_make_link(
            link_type="placedByLite",
            source_type="Order",
            source_pk=order_id,
            target_type="CustomerLite",
            target_source_pk=member_id,
            row=row,
        ))
    return links


# ═══════════════════════════════════════════════
# D4: 6 条新 Link 构造器（frozen/02 §3.5）
# ═══════════════════════════════════════════════


def _build_order_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """P05 Order 读取时构造 placedByLite + fromWeapp 两条 Link（D1.5 + D4 组合）。

    - placedByLite: Order → CustomerLite（member_id）
    - fromWeapp:    Order → Weapp（weapp_id）
    """
    return [*_build_placed_by_lite_links(rows), *_build_from_weapp_links(rows)]


def _build_from_weapp_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """fromWeapp: Order → Weapp（P05 Order 读取时，每行一条）。

    source_pk = row.source_pk（order_id，Order 的 PK）
    target_source_pk = row 顶层的 weapp_id（ns_order.weapp_id 字段）

    weapp_id 缺失或为 0 时跳过（not all orders have weapp）。
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        order_id = row.get("source_pk")
        if not _is_valid_pk(order_id):
            continue
        weapp_id = row.get("weapp_id")
        if not _is_valid_pk(weapp_id):
            continue
        links.append(_make_link(
            link_type="fromWeapp",
            source_type="Order",
            source_pk=order_id,
            target_type="Weapp",
            target_source_pk=weapp_id,
            row=row,
        ))
    return links


def _build_has_weapp_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """hasWeapp: Shop → Weapp（P09 Weapp 读取时，每行一条）。

    source_pk = row 顶层的 site_id（ns_weapp.site_id 字段，Shop 的 PK）
    target_source_pk = row.source_pk（weapp_id，Weapp 的 PK）

    site_id 缺失时默认 '1'（栖月汇单租户）；weapp_id 无效时跳过。
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        weapp_id = row.get("source_pk")
        if not _is_valid_pk(weapp_id):
            continue
        site_id = row.get("site_id")
        if not _is_valid_pk(site_id):
            site_id = "1"  # 默认租户
        links.append(_make_link(
            link_type="hasWeapp",
            source_type="Shop",
            source_pk=site_id,
            target_type="Weapp",
            target_source_pk=weapp_id,
            row=row,
        ))
    return links


def _build_review_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """P11 ProductReview 读取时同时构造 hasReview + ofSku + byMember 三条 Link。

    - hasReview: Product → ProductReview（source=goods_id, target=review_id）
    - ofSku:     ProductReview → ProductSku（source=review_id, target=sku_id；sku_id=0 跳过）
    - byMember:  ProductReview → CustomerLite（source=review_id, target=member_id）
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        review_id = row.get("source_pk")
        if not _is_valid_pk(review_id):
            continue
        props = row.get("properties") or {}
        product_id = props.get("productId")
        sku_id = row.get("sku_id")
        member_id = props.get("memberId")

        # hasReview: Product → ProductReview
        if _is_valid_pk(product_id):
            links.append(_make_link(
                link_type="hasReview",
                source_type="Product",
                source_pk=product_id,
                target_type="ProductReview",
                target_source_pk=review_id,
                row=row,
            ))

        # ofSku: ProductReview → ProductSku（sku_id=0 跳过）
        if _is_valid_non_zero_pk(sku_id):
            links.append(_make_link(
                link_type="ofSku",
                source_type="ProductReview",
                source_pk=review_id,
                target_type="ProductSku",
                target_source_pk=sku_id,
                row=row,
            ))

        # byMember: ProductReview → CustomerLite
        if _is_valid_pk(member_id):
            links.append(_make_link(
                link_type="byMember",
                source_type="ProductReview",
                source_pk=review_id,
                target_type="CustomerLite",
                target_source_pk=member_id,
                row=row,
            ))
    return links


def _build_has_payment_links(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """hasPayment: Order → Payment（P12 Payment 读取时，每行一条）。

    source_pk = row.properties.orderId（relate_id≈order_id，Order 的 PK）
    target_source_pk = row.source_pk（pay_id，Payment 的 PK）

    orderId 缺失时跳过（无法关联订单）。
    """
    links: list[dict[str, Any]] = []
    for row in rows:
        pay_id = row.get("source_pk")
        if not _is_valid_pk(pay_id):
            continue
        props = row.get("properties") or {}
        order_id = props.get("orderId")
        if not _is_valid_pk(order_id):
            continue
        links.append(_make_link(
            link_type="hasPayment",
            source_type="Order",
            source_pk=order_id,
            target_type="Payment",
            target_source_pk=pay_id,
            row=row,
        ))
    return links


# ═══════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════


def _make_link(
    *,
    link_type: str,
    source_type: str,
    source_pk: Any,
    target_type: str,
    target_source_pk: Any,
    row: dict[str, Any],
) -> dict[str, Any]:
    """构造 Link 行 dict（与 ec_ot_writer._normalize_rows 对齐）。

    应用 frozen/02 → CORE 点号名映射（``_FROZEN_TO_CORE``）；
    对 hasSku/ships 反转 source/target 方向（``_REVERSED_LINKS``），
    使输出方向与 ``ecom_core_models.CORE_LINK_TYPES`` 一致。
    未知 link_type 透传原值（不映射、不反转）。
    """
    if link_type in _REVERSED_LINKS:
        source_type, target_type = target_type, source_type
        source_pk, target_source_pk = target_source_pk, source_pk
    core_link_type = _FROZEN_TO_CORE.get(link_type, link_type)
    return {
        "link_type": core_link_type,
        "source_type": source_type,
        "source_pk": source_pk,
        "target_type": target_type,
        "target_source_pk": target_source_pk,
        "source_updated_at": row.get("source_updated_at"),
        "is_deleted": False,
        "properties": {},
    }


def _is_valid_pk(value: Any) -> bool:
    """判断 PK 是否有效：非空、非 None、非空字符串、非 '0'/0。

    空字符串、None、'0'、0 都视为无效（跳过 Link 构造）。
    """
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != "" and value.strip() != "0"
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _is_valid_non_zero_pk(value: Any) -> bool:
    """判断 PK 是否有效且非零（forSku 专用：sku_id=0 跳过）。

    与 _is_valid_pk 一致，但显式表达 forSku 的 sku_id=0 跳过规则。
    """
    return _is_valid_pk(value)


def _split_multi_value(raw: str) -> list[str]:
    """拆分多值字符串：逗号分隔，去空格，跳过空段。

    '1,2,3' → ['1', '2', '3']
    ' 1 , , 2 , 3 ' → ['1', '2', '3']
    '' → []
    """
    if not raw or not raw.strip():
        return []
    parts: list[str] = []
    for segment in raw.split(","):
        cleaned = segment.strip()
        if cleaned:
            parts.append(cleaned)
    return parts
