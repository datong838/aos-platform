"""D1-W1: 派生指标计算 — Normalize/QualityGate 节点的派生字段。

按 pipeline.target_ot 分发，计算 4 个派生指标并写入 row.properties。

FR-D1-7 派生指标口径（基于 frozen/01 schema fingerprint）：
| 派生指标         | OT          | 计算口径                                                                 |
|------------------|-------------|--------------------------------------------------------------------------|
| quality_score    | Product     | evaluate > 0 时 = evaluate_haoping / evaluate；否则 null                 |
| stock_health     | ProductSku  | stock <= 0 → low；0 < stock <= alarm → watch；否则 ok                    |
| risk_score       | Order       | base=0.0；commission_risk_flag=1 → +0.40；refund_status∈{-3,3} → +0.30；   |
|                  |             | is_lock=1 → +0.20；order_status=0 AND pay_status=0 AND                    |
|                  |             | now-create_time>24h → +0.10；截断 [0,1]                                   |
| overdue_hours    | Shipment    | SLA_HOURS=48；delivery_time=0 AND Order.pay_time>0 时                     |
|                  |             | = max(0, (now - Order.pay_time - 48h) / 3600)；否则 null                   |

约束（FR-D1-7）：
- 派生指标 MUST 由 Pipeline 的 Normalize/QualityGate 节点计算后写入 OT，不能由 Logic 自行计算
- 派生公式变更等同于 OT schema 变更，需走 228-EC-核心本体与增量一致性方案 审批
- 源字段缺失时写 null，不阻塞 Pipeline
- 不修改 source_pk / external_id / source_updated_at 等核心字段
- 派生指标写入 row 的 properties 字段下（与 ec_ot_writer._build_object 的 properties 对齐）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# overdue_hours 的 SLA 阈值（frozen/01）
SLA_HOURS: int = 48
_SLA_SECONDS: int = SLA_HOURS * 3600
_24H_SECONDS: int = 24 * 3600

# risk_score 各因子权重
_RISK_COMMISSION: float = 0.40
_RISK_REFUND: float = 0.30
_RISK_LOCK: float = 0.20
_RISK_STALE_24H: float = 0.10

# pipeline.id 前缀 → target_ot 推断表（frozen/02 §通用骨架）
_PIPELINE_ID_TO_OT: dict[str, str] = {
    "p01": "Shop",
    "p02": "Product",
    "p03": "ProductSku",
    "p04": "Category",
    "p05": "Order",
    "p06": "OrderLine",
    "p07": "Shipment",
}


def _now_utc() -> datetime:
    """当前 UTC 时间（测试可 patch 此函数固定时间）。"""
    return datetime.now(timezone.utc)


def apply_derived_metrics(
    rows: list[dict[str, Any]],
    pipeline: Any,
) -> list[dict[str, Any]]:
    """对 rows 计算派生指标并写入 row.properties。

    按 pipeline 的 target_ot 分发：
    - Product → quality_score
    - ProductSku → stock_health
    - Order → risk_score
    - Shipment → overdue_hours
    - 其他（Shop/Category/OrderLine 等）→ 透传不计算

    约束：
    - 源字段缺失时写 null，不阻塞 Pipeline
    - 不修改 source_pk / external_id / source_updated_at 等核心字段
    """
    target_ot = _resolve_target_ot(pipeline)

    if target_ot == "Product":
        for row in rows:
            _apply_quality_score(row)
    elif target_ot == "ProductSku":
        for row in rows:
            _apply_stock_health(row)
    elif target_ot == "Order":
        for row in rows:
            _apply_risk_score(row)
    elif target_ot == "Shipment":
        for row in rows:
            _apply_overdue_hours(row)

    return rows


def _resolve_target_ot(pipeline: Any) -> str | None:
    """从 pipeline 解析 target_ot。

    优先用 pipeline.config.target_ot；缺失时用 pipeline.id 前缀推断
    （P01→Shop, P02→Product, P03→ProductSku, P04→Category,
     P05→Order, P06→OrderLine, P07→Shipment）。
    """
    config = getattr(pipeline, "config", None) or {}
    target_ot = config.get("target_ot") if isinstance(config, dict) else None
    if target_ot:
        return target_ot

    pid = str(getattr(pipeline, "id", "") or "").lower()
    for prefix, ot in _PIPELINE_ID_TO_OT.items():
        if pid.startswith(prefix):
            return ot
    return None


def _get_field(row: dict[str, Any], name: str, default: Any = None) -> Any:
    """从 row 取源字段值，兼容顶层和 properties 两种位置。

    优先从 row 顶层取（raw niushop 格式），其次从 properties 取（normalized 格式）。
    """
    if name in row:
        return row[name]
    props = row.get("properties") or {}
    return props.get(name, default)


def _set_property(row: dict[str, Any], name: str, value: Any) -> None:
    """将派生指标写入 row.properties（与 ec_ot_writer._build_object 对齐）。"""
    props = row.get("properties")
    if props is None:
        props = {}
        row["properties"] = props
    props[name] = value


def _to_float(value: Any) -> float | None:
    """安全转 float，None/非法值返回 None。"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    """安全转 int，None/非法值返回 None。"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_datetime(value: Any) -> datetime | None:
    """安全转 timezone-aware UTC datetime。

    支持 datetime 对象和 Unix 时间戳（秒，int/float）。
    None 或非法值返回 None。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


# ── quality_score (Product) ──────────────────────────────────────────────────


def _apply_quality_score(row: dict[str, Any]) -> None:
    """计算 quality_score = evaluate_haoping / evaluate。

    - evaluate > 0 时计算，evaluate_haoping/evaluate 截断到 [0, 1]
    - evaluate <= 0 或缺失 → null
    """
    evaluate = _to_float(_get_field(row, "evaluate"))
    evaluate_haoping = _to_float(_get_field(row, "evaluate_haoping"))

    if evaluate is not None and evaluate > 0:
        haoping = evaluate_haoping if evaluate_haoping is not None else 0.0
        score = haoping / evaluate
        if score > 1.0:
            score = 1.0
        elif score < 0.0:
            score = 0.0
        _set_property(row, "quality_score", round(score, 4))
    else:
        _set_property(row, "quality_score", None)


# ── stock_health (ProductSku) ────────────────────────────────────────────────


def _apply_stock_health(row: dict[str, Any]) -> None:
    """计算 stock_health 库存健康度。

    - stock <= 0 → low（无库存）
    - 0 < stock <= alarm → watch（库存预警）
    - stock > alarm → ok（库存健康）
    - goods_stock_alarm 缺失 → 默认 alarm=0
    - stock 缺失 → null
    """
    stock = _to_int(_get_field(row, "stock"))
    alarm = _to_int(_get_field(row, "goods_stock_alarm"))
    if alarm is None:
        alarm = 0

    if stock is None:
        _set_property(row, "stock_health", None)
        return

    if stock <= 0:
        _set_property(row, "stock_health", "low")
    elif stock <= alarm:
        _set_property(row, "stock_health", "watch")
    else:
        _set_property(row, "stock_health", "ok")


# ── risk_score (Order) ───────────────────────────────────────────────────────


def _apply_risk_score(row: dict[str, Any]) -> None:
    """计算 risk_score 订单风险分。

    base=0.0，各因子累加：
    - commission_risk_flag=1 → +0.40
    - refund_status∈{-3, 3} → +0.30
    - is_lock=1 → +0.20
    - order_status=0 AND pay_status=0 AND now-create_time>24h → +0.10
    最终截断到 [0, 1]。
    """
    score = 0.0

    if _to_int(_get_field(row, "commission_risk_flag")) == 1:
        score += _RISK_COMMISSION

    refund_status = _to_int(_get_field(row, "refund_status"))
    if refund_status is not None and refund_status in (-3, 3):
        score += _RISK_REFUND

    if _to_int(_get_field(row, "is_lock")) == 1:
        score += _RISK_LOCK

    # 24h 停滞因子：order_status=0 AND pay_status=0 AND now-create_time>24h
    order_status = _to_int(_get_field(row, "order_status"))
    pay_status = _to_int(_get_field(row, "pay_status"))
    create_time = _to_datetime(_get_field(row, "create_time"))
    if (
        order_status == 0
        and pay_status == 0
        and create_time is not None
    ):
        elapsed = (_now_utc() - create_time).total_seconds()
        if elapsed > _24H_SECONDS:
            score += _RISK_STALE_24H

    # 截断 [0, 1]
    score = max(0.0, min(1.0, score))
    _set_property(row, "risk_score", round(score, 4))


# ── overdue_hours (Shipment) ─────────────────────────────────────────────────


def _apply_overdue_hours(row: dict[str, Any]) -> None:
    """计算 overdue_hours 发货逾期小时数。

    SLA_HOURS=48。当 delivery_time=0（未发货）且 Order.pay_time>0（已支付）时：
        overdue = max(0, (now - pay_time - 48h) / 3600)
    否则 → null。

    注：source_adapter 会把 0 时间转 None，所以 delivery_time=None 也视为未发货。
    """
    delivery_time = _get_field(row, "delivery_time")
    pay_time_raw = _get_field(row, "pay_time")

    # delivery_time=0 或 None → 未发货；>0 → 已发货（不逾期）
    delivery_dt = _to_float(delivery_time)
    is_not_delivered = delivery_dt is None or delivery_dt == 0.0

    pay_time_dt = _to_datetime(pay_time_raw)
    is_paid = pay_time_dt is not None and pay_time_dt.timestamp() > 0

    if is_not_delivered and is_paid:
        elapsed = (_now_utc() - pay_time_dt).total_seconds()
        overdue = max(0.0, (elapsed - _SLA_SECONDS) / 3600)
        _set_property(row, "overdue_hours", round(overdue, 4))
    else:
        _set_property(row, "overdue_hours", None)
