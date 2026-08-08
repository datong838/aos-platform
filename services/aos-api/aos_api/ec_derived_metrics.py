"""D1-W1 + D1.5: 派生指标计算 — Normalize/QualityGate 节点的派生字段。

按 pipeline.target_ot 分发，计算派生指标并写入 row.properties。

FR-D1-7 单行派生指标口径（基于 frozen/01 schema fingerprint）：
| 派生指标         | OT          | 计算口径                                                                 |
|------------------|-------------|--------------------------------------------------------------------------|
| quality_score    | Product     | evaluate > 0 时 = evaluate_haoping / evaluate；否则 null                 |
| stock_health     | ProductSku  | stock <= 0 → low；0 < stock <= alarm → watch；否则 ok                    |
| risk_score       | Order       | base=0.0；commission_risk_flag=1 → +0.40；refund_status∈{-3,3} → +0.30；   |
|                  |             | is_lock=1 → +0.20；order_status=0 AND pay_status=0 AND                    |
|                  |             | now-create_time>24h → +0.10；截断 [0,1]                                   |
| overdue_hours    | Shipment    | SLA_HOURS=48；delivery_time=0 AND Order.pay_time>0 时                     |
|                  |             | = max(0, (now - Order.pay_time - 48h) / 3600)；否则 null                   |

FR-D1.5-4 跨表聚合派生指标（D1.5 新增，CustomerLite OT）：
| 派生指标         | OT            | 计算口径                                                                  |
|------------------|---------------|---------------------------------------------------------------------------|
| order_count Δ    | CustomerLite  | 由 placedByLite Link 反向聚合，按 member_id 计算 Order 数量              |
| last_order_days Δ| CustomerLite  | now - max(Order.create_time)，按天；无订单时为 null                      |

架构差异：D1 已有 4 个派生指标为单行派生（row 内字段计算）；
D1.5 新增 2 个派生指标为跨表聚合（需查 ecom_link 表）。
采用 link_aggregator 注入式接口保持派生指标模块的纯函数性与可测性。

约束（FR-D1-7 + FR-D1.5-4）：
- 派生指标 MUST 由 Pipeline 的 Normalize/QualityGate 节点计算后写入 OT，不能由 Logic 自行计算
- 派生公式变更等同于 OT schema 变更，需走 228-EC-核心本体与增量一致性方案 审批
- 源字段缺失时写 null，不阻塞 Pipeline
- 不修改 source_pk / external_id / source_updated_at 等核心字段
- 派生指标写入 row 的 properties 字段下（与 ec_ot_writer._build_object 的 properties 对齐）
- apply_derived_metrics 签名向后兼容：link_aggregator 为 keyword-only 可选参数，默认 None
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

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
    # D1.5: P08 CustomerLite（frozen/02 §P08）
    "p08": "CustomerLite",
    # D4: P09~P12（frozen/02 §P09~P12）
    "p09": "Weapp",
    "p10": "SystemConfig",
    "p11": "ProductReview",
    "p12": "Payment",
}

# D1.5: link_aggregator 接口契约（FR-D1.5-4）
# 输入：member_ids 集合（来自 row.source_pk）
# 输出：{member_id: (order_count, last_order_create_time)}
#   - member_id 不在返回 dict 中 → null（无订单数据）
#   - member_id 在返回 dict 中且 order_count=0 → 0（有数据但订单数为 0）
LinkAggregator = Callable[
    [frozenset[str]],
    dict[str, tuple[int, datetime | None]],
]


def _now_utc() -> datetime:
    """当前 UTC 时间（测试可 patch 此函数固定时间）。"""
    return datetime.now(timezone.utc)


def apply_derived_metrics(
    rows: list[dict[str, Any]],
    pipeline: Any,
    *,
    link_aggregator: LinkAggregator | None = None,
) -> list[dict[str, Any]]:
    """对 rows 计算派生指标并写入 row.properties。

    按 pipeline 的 target_ot 分发：
    - Product → quality_score（FR-D1-7 单行派生）
    - ProductSku → stock_health（FR-D1-7 单行派生）
    - Order → risk_score（FR-D1-7 单行派生）
    - Shipment → overdue_hours（FR-D1-7 单行派生）
    - CustomerLite → order_count Δ / last_order_days Δ（FR-D1.5-4 跨表聚合）
    - 其他（Shop/Category/OrderLine 等）→ 透传不计算

    约束：
    - 源字段缺失时写 null，不阻塞 Pipeline
    - 不修改 source_pk / external_id / source_updated_at 等核心字段
    - link_aggregator 为 keyword-only 可选参数（D1.5 新增）：
      * 默认 None 时，CustomerLite 行写 null（字段存在但为 null）
      * 提供时，批量查询 member_ids 聚合结果，按行写入实际值
    - 非 CustomerLite OT 不读 link_aggregator（D1 行为不变）
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
    elif target_ot == "CustomerLite":
        _apply_order_count_and_last_order_days(rows, link_aggregator)
    elif target_ot == "ProductReview":
        for row in rows:
            _apply_review_quality_bucket(row)
    elif target_ot == "Payment":
        for row in rows:
            _apply_pay_duration_min(row)

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
    支持常见别名：score↔scores（Niushop ns_goods_evaluate 用 scores）。
    """
    if name in row:
        return row[name]
    # 别名兼容
    _aliases = {"score": "scores", "scores": "score"}
    alias = _aliases.get(name)
    if alias and alias in row:
        return row[alias]
    props = row.get("properties") or {}
    if name in props:
        return props[name]
    if alias and alias in props:
        return props[alias]
    return default


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

    支持 datetime 对象、Unix 时间戳（秒，int/float）和 ISO 8601 字符串。
    None 或非法值返回 None。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        # Try ISO 8601 format (e.g., "2026-01-24T14:49:35.000000Z")
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
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


# ── order_count Δ / last_order_days Δ (CustomerLite, D1.5) ─────────────────────


def _apply_order_count_and_last_order_days(
    rows: list[dict[str, Any]],
    link_aggregator: LinkAggregator | None,
) -> None:
    """计算 order_count Δ / last_order_days Δ 入口（FR-D1.5-4，跨表聚合派生指标）。

    架构差异：与 D1 单行派生不同，本派生指标需要查 ecom_link 表聚合
    placedByLite Link，因此通过 link_aggregator 注入式接口解耦。

    合并入口：共享一次 link_aggregator 批量查询（避免 N+1），
    然后分发到 _apply_order_count 和 _apply_last_order_days 子函数。

    行为契约：
    - link_aggregator=None：所有行写 null（字段存在但为 null，满足 AC-D1.5-4）
    - link_aggregator 提供：
      * 收集 rows 中所有有效 source_pk（member_id）集合
      * 批量调用 link_aggregator(member_ids) 一次
      * member_id 不在聚合结果中 → 子函数写 null
      * member_id 在聚合结果中 → 子函数写实际值

    fail-closed：link_aggregator 抛异常时不吞，向上传播。
    """
    # 收集有效 member_ids（source_pk 非空、非 None）
    member_ids: set[str] = set()
    for row in rows:
        source_pk = row.get("source_pk")
        if source_pk is None:
            continue
        pk_str = str(source_pk).strip()
        if pk_str:
            member_ids.add(pk_str)

    # 无有效 member_id 或无 link_aggregator：所有行写 null
    if not member_ids or link_aggregator is None:
        for row in rows:
            _apply_order_count(row, None)
            _apply_last_order_days(row, None, _now_utc())
        return

    # 批量查询（只调用一次，避免 N+1）
    aggregation = link_aggregator(frozenset(member_ids))

    now = _now_utc()
    for row in rows:
        source_pk = row.get("source_pk")
        pk_str = str(source_pk).strip() if source_pk is not None else ""
        # member_id 无效或不在聚合结果中 → entry=None，子函数写 null
        entry = aggregation.get(pk_str) if pk_str else None
        _apply_order_count(row, entry)
        _apply_last_order_days(row, entry, now)


def _apply_order_count(
    row: dict[str, Any],
    entry: tuple[int, datetime | None] | None,
) -> None:
    """写入 order_count（FR-D1.5-4 派生指标）。

    - entry=None（member_id 无效或不在聚合结果中）→ null
    - entry 提供 → 写 order_count（int，≥0；0 表示有聚合数据但订单数为 0）

    语义区分：
    - member_id 不在聚合结果 → null（无订单数据）
    - member_id 在聚合结果且 order_count=0 → 0（有数据但订单数为 0）
    """
    if entry is None:
        _set_property(row, "order_count", None)
        return
    order_count, _ = entry
    _set_property(row, "order_count", order_count)


def _apply_last_order_days(
    row: dict[str, Any],
    entry: tuple[int, datetime | None] | None,
    now: datetime,
) -> None:
    """写入 last_order_days（FR-D1.5-4 派生指标）。

    - entry=None → null
    - entry 提供 且 last_order_create_time=None → null（无订单）
    - entry 提供 且 last_order_create_time 有效 → max(0, (now - last_order_create_time).days)

    按天计算（timedelta.days，向下取整到整天），未来时间截断到 0。
    """
    if entry is None:
        _set_property(row, "last_order_days", None)
        return
    _, last_order_create_time = entry
    if last_order_create_time is None:
        _set_property(row, "last_order_days", None)
        return
    delta = now - last_order_create_time
    # timedelta.days 对负值会向下取整（如 -1天23小时 → -2），
    # 因此先取 total_seconds 判断，负值截断到 0
    if delta.total_seconds() < 0:
        days = 0
    else:
        days = delta.days
    _set_property(row, "last_order_days", days)


# ── review_quality_bucket (ProductReview · D4) ──────────────────────────────


def _apply_review_quality_bucket(row: dict[str, Any]) -> None:
    """计算 review_quality_bucket 好评/中评/差评分桶（FR-D4-DM1）。

    口径（frozen/02 §3.6）：
    - score >= 4.5 → "high"（好评）
    - score <= 3.0 → "low"（差评）
    - 3.0 < score < 4.5 → "mid"（中评）
    - score 缺失或非法 → null

    边界值：3.0 算 low，4.5 算 high（含等号）。
    """
    score = _to_float(_get_field(row, "score"))
    if score is None:
        _set_property(row, "review_quality_bucket", None)
        return

    if score >= 4.5:
        bucket = "high"
    elif score <= 3.0:
        bucket = "low"
    else:
        bucket = "mid"
    _set_property(row, "review_quality_bucket", bucket)


# ── pay_duration_min (Payment · D4) ─────────────────────────────────────────


def _apply_pay_duration_min(row: dict[str, Any]) -> None:
    """计算 pay_duration_min 创单→支付耗时分钟差（FR-D4-DM2）。

    口径（frozen/02 §3.6）：Order.create_time → Payment.pay_time 的分钟差。

    管道内关联（用户 2026-08-06 拍板）：
    - normalize 阶段已用 ns_pay.relate_id（≈order_id）关联查 ns_order.create_time，
      结果挂到 row._order_create_time（内部字段，不进 properties）。
    - 此函数直接读 row._order_create_time 和 row.pay_time 计算分钟差。
    - 关联失败（relate_id 为空或查不到 order）→ null，不阻塞 Pipeline。
    - pay_time 缺失或非法 → null。
    - 负值（pay_time 早于 create_time，异常数据）→ 截断到 0。
    """
    pay_time = _to_datetime(_get_field(row, "pay_time"))
    # 管道内关联挂载的内部字段（normalize 阶段填充）
    order_create_time = _to_datetime(row.get("_order_create_time"))

    if pay_time is None or order_create_time is None:
        _set_property(row, "pay_duration_min", None)
        return

    delta = pay_time - order_create_time
    if delta.total_seconds() < 0:
        # 异常数据：支付早于创单，截断到 0
        minutes = 0
    else:
        minutes = int(delta.total_seconds() // 60)
    _set_property(row, "pay_duration_min", minutes)
