"""AIP 四层记忆冷启动 seed.

在引擎首次启动时灌入初始记忆条目，使 AIP 分析师/数字同事开机即有
领域知识基础，而非空容器。

分层灌入策略：
  - **Semantic** (语义记忆): 7 个核心 OT 的领域事实（从 ecom_core_models 派生）。
  - **Procedural** (程序记忆): 3 条标准操作流程（订单异常分诊 / SKU 缺货检测 / 物流超期）。
  - **Episodic** (情景记忆): 1 条系统初始化事件（记录冷启动时间戳）。
  - **Working** (工作记忆): 空——由运行时会话按需写入。

幂等：通过固定 id 前缀 + tags 标记，重复执行不重复插入。
"""
from __future__ import annotations

import time

from aos_api.aip_long_memory import MemoryLayer, get_engine
from aos_api.ecom_core_models import REQUIRED_PROPERTIES, DERIVED_PROPERTIES
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_memory_cold_start")

_SEED_TAG = "cold-start-seed"


def _seed_semantic() -> int:
    """灌入语义记忆：每个核心 OT 的必填字段 + 派生指标事实。"""
    eng = get_engine()
    count = 0
    existing_ids = {item.id for item in eng.list_semantic()}

    for ot, required in sorted(REQUIRED_PROPERTIES.items()):
        item_id = f"mem-semantic-{ot.lower()}"
        if item_id in existing_ids:
            continue
        derived = sorted(DERIVED_PROPERTIES.get(ot, frozenset()))
        content = (
            f"# {ot} 领域事实\n\n"
            f"## 必填属性 ({len(required)} 个)\n"
            + "\n".join(f"- `{r}`" for r in sorted(required))
            + "\n\n"
        )
        if derived:
            content += f"## 派生指标 ({len(derived)} 个)\n" + "\n".join(
                f"- `{d}`" for d in derived
            )
        eng.create(
            name=f"{ot} 本体契约",
            config={"object_type": ot, "required_count": len(required)},
            layer=MemoryLayer.SEMANTIC.value,
            content=content,
            object_type=ot,
            tags=[_SEED_TAG, "ontology", ot.lower()],
        )
        count += 1
    return count


def _seed_procedural() -> int:
    """灌入程序记忆：标准操作流程。"""
    eng = get_engine()
    existing_ids = {item.id for item in eng.list_procedural()}

    procedures = [
        {
            "id": "mem-procedural-order-anomaly",
            "name": "订单异常分诊流程",
            "content": (
                "# 订单异常分诊标准流程\n\n"
                "## 触发条件\n"
                "- Order.risk_score > 0.7\n"
                "- 或 Order.totalAmount 异常偏高 (>3σ)\n\n"
                "## 步骤\n"
                "1. 查询 Order + OrderLine + Shipment 三关联\n"
                "2. 检查 CustomerLite.order_count（新客首单？）\n"
                "3. 检查 Shipment.overdue_hours（跨境发货延迟？）\n"
                "4. 查询 ProductReview.review_quality_bucket（商品评价？）\n"
                "5. 输出分诊结论 + 建议操作\n"
            ),
            "object_type": "Order",
            "tags": [_SEED_TAG, "order", "anomaly", "triage"],
        },
        {
            "id": "mem-procedural-sku-stockout",
            "name": "SKU 缺货检测流程",
            "content": (
                "# SKU 缺货检测标准流程\n\n"
                "## 触发条件\n"
                "- ProductSku.stock_health < 0.3\n"
                "- 或 Product.stock < safety_threshold\n\n"
                "## 步骤\n"
                "1. 查询 ProductSku → Product 关联\n"
                "2. 检查近 7 天 OrderLine.quantity 趋势\n"
                "3. 计算补货建议量 = avg_daily_sales × lead_time - current_stock\n"
                "4. 输出补货建议\n"
            ),
            "object_type": "ProductSku",
            "tags": [_SEED_TAG, "sku", "stockout", "inventory"],
        },
        {
            "id": "mem-procedural-shipment-overdue",
            "name": "物流超期预警流程",
            "content": (
                "# 物流超期预警标准流程\n\n"
                "## 触发条件\n"
                "- Shipment.overdue_hours > 48\n\n"
                "## 步骤\n"
                "1. 查询 Shipment → Order 关联\n"
                "2. 检查 Order.deliveryStatus\n"
                "3. 查询承运商 (Shipment.carrier) 历史准时率\n"
                "4. 输出预警等级 + 客服话术建议\n"
            ),
            "object_type": "Shipment",
            "tags": [_SEED_TAG, "shipment", "overdue", "logistics"],
        },
    ]

    count = 0
    for proc in procedures:
        if proc["id"] in existing_ids:
            continue
        eng.create(
            name=proc["name"],
            config={},
            layer=MemoryLayer.PROCEDURAL.value,
            content=proc["content"],
            object_type=proc["object_type"],
            tags=proc["tags"],
        )
        count += 1
    return count


def _seed_episodic() -> int:
    """灌入情景记忆：系统初始化事件。"""
    eng = get_engine()
    existing = [item for item in eng.list_episodic() if _SEED_TAG in item.tags]
    if existing:
        return 0

    eng.create(
        name="系统冷启动初始化",
        config={"boot_timestamp": time.time()},
        layer=MemoryLayer.EPISODIC.value,
        content=(
            f"# 系统冷启动\n\n"
            f"- **时间**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
            f"- **事件**: AIP 四层记忆引擎首次启动\n"
            f"- **动作**: 灌入语义记忆 (12 OT 契约) + 程序记忆 (3 流程) + 本事件\n"
        ),
        tags=[_SEED_TAG, "system", "boot"],
    )
    return 1


def seed_memory_cold_start() -> dict[str, int]:
    """执行四层记忆冷启动灌入。返回各层灌入计数。"""
    semantic = _seed_semantic()
    procedural = _seed_procedural()
    episodic = _seed_episodic()
    total = semantic + procedural + episodic
    if total:
        log.info(
            "seed_memory_cold_start_done semantic=%s procedural=%s episodic=%s total=%s",
            semantic,
            procedural,
            episodic,
            total,
        )
    return {"semantic": semantic, "procedural": procedural, "episodic": episodic, "total": total}
