"""D1-W1: 派生指标计算 — Normalize/QualityGate 节点的派生字段。

骨架阶段：透传 rows，不计算派生指标（与原 ec_live_executor 行为等价）。
Worker W1 实现：按 pipeline.target_ot 分发，计算 4 个派生指标并写入 row。

FR-D1-7 派生指标口径（基于 frozen/01 schema fingerprint）：
| 派生指标         | OT          | 计算口径                                                                 |
|------------------|-------------|--------------------------------------------------------------------------|
| quality_score    | Product     | evaluate > 0 时 = evaluate_haoping / evaluate；否则 null                 |
| stock_health     | ProductSku  | stock <= goods_stock_alarm → low；0 < stock <= alarm → watch；否则 ok    |
| risk_score       | Order       | base=0.0；commission_risk_flag=1 → +0.40；refund_status∈{-3,3} → +0.30；   |
|                  |             | is_lock=1 → +0.20；order_status=0 AND pay_status=0 AND                    |
|                  |             | now-create_time>24h → +0.10；截断 [0,1]                                   |
| overdue_hours    | Shipment    | SLA_HOURS=48；delivery_time=0 AND Order.pay_time>0 时                     |
|                  |             | = max(0, (now - Order.pay_time - 48h) / 3600)；否则 null                   |

约束（FR-D1-7）：
- 派生指标 MUST 由 Pipeline 的 Normalize/QualityGate 节点计算后写入 OT，不能由 Logic 自行计算
- 派生公式变更等同于 OT schema 变更，需走 228-EC-核心本体与增量一致性方案 审批
"""

from __future__ import annotations

from typing import Any


def apply_derived_metrics(
    rows: list[dict[str, Any]],
    pipeline: Any,
) -> list[dict[str, Any]]:
    """对 rows 计算派生指标并写入字段。

    骨架阶段：透传 rows（不计算派生指标），与原 ec_live_executor 行为等价。
    Worker W1 实现：按 pipeline.target_ot 分发到 _apply_product / _apply_sku /
    _apply_order / _apply_shipment，计算对应派生指标写入 row。

    约束：
    - 源字段缺失时写 null，不阻塞 Pipeline（NFR: 派生指标缺失率 < 5%）
    - 不修改 source_pk / external_id / source_updated_at 等核心字段
    """
    # 骨架：透传，不计算派生指标
    return rows
