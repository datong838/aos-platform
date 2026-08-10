"""OKF Wiki cold-start seed.

When the in-memory WikiEngine is empty (fresh boot, no Phase4 demo seed yet),
this module provides per-OT seed Wiki entries so that AIP-8 (Analyst) and the
Wiki UI never face a "select object + empty gap" dead end.

Each seed Wiki documents the OT's canonical schema (required properties, link
types, derived metrics) in Markdown — the same content that AIP agents consume
for real-data grounding.

Additionally seeds 3 procedural Wikis (versioned operational playbooks) — this
is the correct home for procedural knowledge per 06-228-AIP §1: "Procedural
knowledge lives in versioned Skill/Logic/Policy/Playbook", NOT in the runtime
memory singleton.

Design rules:
  - Pure in-memory: writes to WikiEngine singleton, no DB.
  - Idempotent: skip if a Wiki with the same fixed id already exists.
  - 12 OTs covered: Shop / Product / ProductSku / Category / Order / OrderLine
    / Shipment / CustomerLite / Weapp / SystemConfig / ProductReview / Payment.
  - 3 procedural playbooks: order anomaly triage, SKU stockout, shipment overdue.
  - Fixed ids (``wiki-coldstart-{slug}``) so re-seed is safe.
"""
from __future__ import annotations

from aos_api.ecom_core_models import (
    CORE_LINK_TYPES,
    CORE_OBJECT_TYPES,
    DERIVED_PROPERTIES,
    OPTIONAL_PROPERTIES,
    REQUIRED_PROPERTIES,
)
from aos_api.logging_facade import get_logger
from aos_api.ontology_wiki_engine import get_wiki_engine

log = get_logger("aos-api.okf_wiki_cold_start")


def _ot_links(object_type: str) -> list[str]:
    """Return link type names involving this OT."""
    return [
        lt
        for lt, (src, dst) in CORE_LINK_TYPES.items()
        if src == object_type or dst == object_type
    ]


def _build_content(ot: str) -> str:
    required = sorted(REQUIRED_PROPERTIES.get(ot, frozenset()))
    optional = sorted(OPTIONAL_PROPERTIES.get(ot, frozenset()))
    derived = sorted(DERIVED_PROPERTIES.get(ot, frozenset()))
    links = _ot_links(ot)

    lines: list[str] = [
        f"# {ot} 对象知识手册",
        "",
        f"> 本文由 OKF 冷启动自动生成，描述 **{ot}** 的本体契约。",
        "",
        "## 必填属性 (Required)",
    ]
    for prop in required:
        lines.append(f"- `{prop}`")
    if not required:
        lines.append("- 无")

    lines.append("")
    lines.append("## 可选属性 (Optional)")
    for prop in optional:
        lines.append(f"- `{prop}`")
    if not optional:
        lines.append("- 无")

    lines.append("")
    lines.append("## 派生指标 (Derived)")
    for prop in derived:
        lines.append(f"- `{prop}`")
    if not derived:
        lines.append("- 无")

    lines.append("")
    lines.append("## 关联关系 (Links)")
    for link in links:
        src, dst = CORE_LINK_TYPES[link]
        arrow = "→" if src == ot else "←"
        other = dst if src == ot else src
        lines.append(f"- `{link}` ({arrow} {other})")
    if not links:
        lines.append("- 无")

    lines.append("")
    lines.append("---")
    lines.append(
        "*本内容基于 `ecom_core_models.REQUIRED_PROPERTIES` 自动生成，"
        "可通过 Draft 审批流更新。*"
    )
    return "\n".join(lines)


_PROCEDURAL_PLAYBOOKS = [
    {
        "id": "wiki-coldstart-playbook-order-anomaly",
        "title": "订单异常分诊 Playbook",
        "object_type_id": "Order",
        "tags": ["cold-start", "procedural", "playbook", "order", "anomaly"],
        "content": (
            "# 订单异常分诊标准流程\n\n"
            "> 版本化 Playbook — 程序性知识的正确归属（非运行记忆层）\n\n"
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
    },
    {
        "id": "wiki-coldstart-playbook-sku-stockout",
        "title": "SKU 缺货检测 Playbook",
        "object_type_id": "ProductSku",
        "tags": ["cold-start", "procedural", "playbook", "sku", "stockout"],
        "content": (
            "# SKU 缺货检测标准流程\n\n"
            "> 版本化 Playbook — 程序性知识的正确归属（非运行记忆层）\n\n"
            "## 触发条件\n"
            "- ProductSku.stock_health < 0.3\n"
            "- 或 Product.stock < safety_threshold\n\n"
            "## 步骤\n"
            "1. 查询 ProductSku → Product 关联\n"
            "2. 检查近 7 天 OrderLine.quantity 趋势\n"
            "3. 计算补货建议量 = avg_daily_sales × lead_time - current_stock\n"
            "4. 输出补货建议\n"
        ),
    },
    {
        "id": "wiki-coldstart-playbook-shipment-overdue",
        "title": "物流超期预警 Playbook",
        "object_type_id": "Shipment",
        "tags": ["cold-start", "procedural", "playbook", "shipment", "overdue"],
        "content": (
            "# 物流超期预警标准流程\n\n"
            "> 版本化 Playbook — 程序性知识的正确归属（非运行记忆层）\n\n"
            "## 触发条件\n"
            "- Shipment.overdue_hours > 48\n\n"
            "## 步骤\n"
            "1. 查询 Shipment → Order 关联\n"
            "2. 检查 Order.deliveryStatus\n"
            "3. 查询承运商 (Shipment.carrier) 历史准时率\n"
            "4. 输出预警等级 + 客服话术建议\n"
        ),
    },
]


def seed_okf_wiki_cold_start() -> int:
    """Seed per-OT cold-start Wikis + procedural playbooks.

    Per-OT Wikis document each Object Type's canonical schema.
    Procedural playbooks are versioned operational flows (06 §1: Procedural
    knowledge lives in versioned assets, not runtime memory).

    Returns the count of newly seeded Wikis.
    """
    eng = get_wiki_engine()
    seeded = 0

    # 1. Per-OT schema Wikis
    for ot in sorted(CORE_OBJECT_TYPES):
        wiki_id = f"wiki-coldstart-{ot.lower()}"
        if eng.get_wiki(wiki_id) is not None:
            continue
        if eng.find_wiki_by_object_type(ot) is not None:
            continue
        eng.create_wiki(
            id=wiki_id,
            title=f"{ot} 对象知识",
            content=_build_content(ot),
            object_type_id=ot,
            tags=["cold-start", "okf", ot.lower()],
            author="okf-cold-start",
        )
        seeded += 1

    # 2. Procedural playbooks (versioned operational flows)
    for pb in _PROCEDURAL_PLAYBOOKS:
        if eng.get_wiki(pb["id"]) is not None:
            continue
        eng.create_wiki(
            id=pb["id"],
            title=pb["title"],
            content=pb["content"],
            object_type_id=pb["object_type_id"],
            tags=pb["tags"],
            author="okf-cold-start",
        )
        seeded += 1

    if seeded:
        log.info("seed_okf_wiki_cold_start_done seeded=%s", seeded)
    return seeded
