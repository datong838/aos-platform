"""D2.5: Normalize 节点 — raw ns_xxx 行 → OT normalized 行。

Pipeline 骨架节点之一（pipeline-skeleton.json）：
  Source → TenantFilter → Normalize → Validate → Deduplicate
        → QualityGate ┬→ DatasetSink + OTWriter
                     └→ DLQ

职责（pipeline-skeleton.json#Normalize）：
- 字段标准化：Unix 秒转 UTC（0 转 null 已在 source_adapter._clean_rows 完成）
- 金额 decimal 非负（_money 兜底）
- 状态枚举映射
- 追加 OT 元字段：ot / source_pk / source_updated_at / source_timezone / is_deleted
- 计算 OT 业务属性 properties（按 target_ot 派发到 8 OT mapper）
- 保留原始 raw 字段（供 apply_derived_metrics._get_field 从顶层读取派生指标源字段）

幂等契约：
- 行已含 ``ot`` 字段（已 normalized）→ 跳过 mapper，原样透传
- 行无 ``ot`` 字段（raw 行）→ 应用对应 mapper
- target_ot 未识别 → 全部透传（与 ec_link_builder 一致）

派发依据：pipeline.config.target_ot 优先，否则用 pipeline.id 前缀推断
（P01→Shop, P02→Product, P03→ProductSku, P04→Category,
 P05→Order, P06→OrderLine, P07→Shipment, P08→CustomerLite）
与 ec_derived_metrics._resolve_target_ot / ec_link_builder._resolve_target_ot 对齐。

8 OT mapper 契约（与 scripts/d2_qiyuehui_init_load.py 对齐）：
| Mapper         | source_pk        | source_updated_at 来源                | properties 关联键    |
|----------------|------------------|---------------------------------------|----------------------|
| to_shop        | site_id          | create_time                           | —                    |
| to_category    | category_id      | 无时间列 → now                        | —                    |
| to_product     | goods_id         | modify_time / create_time             | shopId, categoryId   |
| to_product_sku | sku_id           | modify_time / create_time             | productId            |
| to_customer_lite| member_id       | reg_time / last_visit_time / login_time | —                  |
| to_order       | order_id         | modify_time / create_time             | memberId, shopId     |
| to_order_line  | order_goods_id   | create_time                           | orderId, skuId       |
| to_shipment    | id               | delivery_time                         | orderId              |
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.ec-normalizer")

# Niushop 源命名空间常量（frozen/02 §通用骨架：site_id=1）
SOURCE_TIMEZONE: str = "+08:00"
CURRENCY: str = "CNY"

# pipeline.id 前缀 → target_ot 推断表（与 ec_derived_metrics._PIPELINE_ID_TO_OT 对齐）
_PIPELINE_ID_TO_OT: dict[str, str] = {
    "p01": "Shop",
    "p02": "Product",
    "p03": "ProductSku",
    "p04": "Category",
    "p05": "Order",
    "p06": "OrderLine",
    "p07": "Shipment",
    # D1.5: P08 CustomerLite（frozen/02 §P08）
    "p08": "CustomerLite",
}


def normalize_rows(
    rows: list[dict[str, Any]],
    pipeline: Any,
) -> list[dict[str, Any]]:
    """Pipeline Normalize 节点入口（幂等）。

    1. _resolve_target_ot(pipeline) 派发
    2. 未识别 target_ot → 透传 rows（与 ec_link_builder 一致）
    3. 已识别 → 对每行：
       - 行已含 ``ot`` 字段 → 跳过（幂等，已 normalized 行不重复处理）
       - 行无 ``ot`` 字段 → 应用对应 mapper

    返回新 list（不修改入参 rows）；行 dict 由 mapper 浅拷贝构造（保留 raw 字段）。
    """
    target_ot = _resolve_target_ot(pipeline)
    if not target_ot:
        return list(rows)

    normalizer = _NORMALIZERS.get(target_ot)
    if normalizer is None:
        return list(rows)

    result: list[dict[str, Any]] = []
    for row in rows:
        # 幂等：行已含 ot 字段（已 normalized）→ 跳过 mapper
        if isinstance(row, dict) and row.get("ot"):
            result.append(row)
            continue
        result.append(normalizer(row))
    return result


def _resolve_target_ot(pipeline: Any) -> str | None:
    """从 pipeline 解析 target_ot。

    优先用 pipeline.config.target_ot；缺失时用 pipeline.id 前缀推断
    （P01→Shop, P02→Product, P03→ProductSku, P04→Category,
     P05→Order, P06→OrderLine, P07→Shipment, P08→CustomerLite）。

    与 ec_derived_metrics._resolve_target_ot 逻辑一致（小写 prefix + lower + startswith）。
    """
    config = getattr(pipeline, "config", None) or {}
    target_ot = config.get("target_ot") if isinstance(config, dict) else None
    if target_ot:
        return str(target_ot)

    pid = str(getattr(pipeline, "id", "") or "").lower()
    for prefix, ot in _PIPELINE_ID_TO_OT.items():
        if pid.startswith(prefix):
            return ot
    return None


# ═══════════════════════════════════════════════
# 通用工具函数（从 scripts/d2_qiyuehui_init_load.py 搬入）
# ═══════════════════════════════════════════════


def _ts(row: dict[str, Any], *fields: str) -> datetime:
    """从 row 的时间字段（unix 秒）取首个有效值转 UTC datetime；全无效则 now。"""
    for f in fields:
        v = row.get(f)
        if isinstance(v, (int, float)) and v > 0:
            return datetime.fromtimestamp(float(v), tz=timezone.utc)
    return datetime.now(timezone.utc)


def _money(v: Any) -> str:
    """金额兜底：None/空/非法 → '0'；合法则转字符串（避免 float 进 Money 校验）。"""
    if v is None:
        return "0"
    if isinstance(v, Decimal):
        return str(v)
    s = str(v).strip()
    if s == "":
        return "0"
    try:
        Decimal(s)
        return s
    except (InvalidOperation, ValueError):
        return "0"


def _str(v: Any, default: str = "") -> str:
    """字符串兜底：None/空 → default；否则去空格。"""
    if v is None:
        return default
    s = str(v).strip()
    return s if s != "" else default


def _base(row: dict[str, Any], ot: str, pk: Any, when: datetime) -> dict[str, Any]:
    """在 raw row 基础上追加 OT 元字段，保留原始 raw 字段。

    追加：ot / source_pk / source_updated_at / source_timezone / is_deleted / properties
    保留：所有 raw ns_xxx 字段（供 apply_derived_metrics._get_field 从顶层读取派生指标源字段）
    """
    out = dict(row)
    out["ot"] = ot
    out["source_pk"] = _str(pk)
    out["source_updated_at"] = when
    out["source_timezone"] = SOURCE_TIMEZONE
    out["is_deleted"] = False
    out["properties"] = {}
    return out


# ═══════════════════════════════════════════════
# 8 OT mapper（从 scripts/d2_qiyuehui_init_load.py 行 153-248 原样搬入）
# ═══════════════════════════════════════════════


def to_shop(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "Shop", row.get("site_id"), _ts(row, "create_time"))
    o["properties"] = {
        "name": _str(row.get("site_name"), "栖月汇商贸"),
        "status": "active",
        "currency": CURRENCY,
        "timezone": SOURCE_TIMEZONE,
    }
    return o


def to_category(row: dict[str, Any]) -> dict[str, Any]:
    # ns_goods_category 无时间列 → source_updated_at 用 now
    o = _base(row, "Category", row.get("category_id"), _ts(row))
    o["properties"] = {
        "parentCategoryId": _str(row.get("pid"), "0"),
        "name": _str(row.get("category_name"), _str(row.get("category_id"))),
        "status": "active",
    }
    return o


def to_product(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "Product", row.get("goods_id"), _ts(row, "modify_time", "create_time"))
    o["properties"] = {
        "shopId": _str(row.get("site_id"), "1"),
        "title": _str(row.get("goods_name"), _str(row.get("goods_id"))),
        "status": "active",
        "categoryId": _str(row.get("category_id"), "0"),
    }
    return o


def to_product_sku(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "ProductSku", row.get("sku_id"), _ts(row, "modify_time", "create_time"))
    o["properties"] = {
        "productId": _str(row.get("goods_id"), "0"),
        "status": "active",
        "barcode": _str(row.get("sku_no"), ""),
        "price": _money(row.get("price")),
        "currency": CURRENCY,
    }
    return o


def to_customer_lite(row: dict[str, Any]) -> dict[str, Any]:
    # ns_member 无 create_time/modify_time → 用 reg_time 等
    o = _base(
        row,
        "CustomerLite",
        row.get("member_id"),
        _ts(row, "reg_time", "last_visit_time", "login_time", "last_login_time"),
    )
    o["properties"] = {
        "memberLevel": _str(row.get("member_level"), "0"),
        "status": "active",
    }
    return o


def to_order(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "Order", row.get("order_id"), _ts(row, "modify_time", "create_time"))
    o["properties"] = {
        "shopId": _str(row.get("site_id"), "1"),
        "status": "active",
        "totalAmount": _money(row.get("order_money")),
        "currency": CURRENCY,
        "orderNo": _str(row.get("order_no")),
        "memberId": _str(row.get("member_id")),
        "orderStatus": _str(row.get("order_status")),
        "payStatus": _str(row.get("pay_status")),
        "deliveryStatus": _str(row.get("delivery_status")),
        "isDelete": _str(row.get("is_delete"), "0"),
    }
    return o


def to_order_line(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "OrderLine", row.get("order_goods_id"), _ts(row, "create_time"))
    o["properties"] = {
        "orderId": _str(row.get("order_id")),
        "skuId": _str(row.get("sku_id"), "0"),
        "quantity": _str(row.get("num"), "0"),
        "unitPrice": _money(row.get("price")),
        "lineAmount": _money(row.get("real_goods_money") or row.get("goods_money")),
        "currency": CURRENCY,
    }
    return o


def to_shipment(row: dict[str, Any]) -> dict[str, Any]:
    o = _base(row, "Shipment", row.get("id"), _ts(row, "delivery_time"))
    o["properties"] = {
        "orderId": _str(row.get("order_id")),
        "status": "active",
        "carrier": _str(row.get("express_company_id"), _str(row.get("express_company_name"))),
        "trackingNo": _str(row.get("delivery_no")),
    }
    return o


# 8 OT mapper 注册表（normalize_rows 派发用）
_NORMALIZERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "Shop": to_shop,
    "Category": to_category,
    "Product": to_product,
    "ProductSku": to_product_sku,
    "CustomerLite": to_customer_lite,
    "Order": to_order,
    "OrderLine": to_order_line,
    "Shipment": to_shipment,
}
