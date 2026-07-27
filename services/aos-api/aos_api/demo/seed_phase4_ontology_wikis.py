"""Phase 4 seed · Ontology Wikis — 15 wiki + 25 版本历史 (合计 40)."""
from __future__ import annotations

from aos_api.ontology_wiki_engine import get_wiki_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase4_ontology_wikis")


_WIKIS_SPEC: list[dict] = [
    {
        "title": "Customer Object Guide",
        "content": "# Customer\n\n客户对象包含基础信息、联系信息、分类信息。\n\n## 属性\n- customer_id: 唯一标识\n- tier: 客户等级\n- annual_revenue: 年收入",
        "tags": ["customer", "guide"],
        "author": "alice",
    },
    {
        "title": "Order Lifecycle",
        "content": "# Order\n\n订单从 pending 到 delivered 的生命周期。\n\n## 状态机\npending → confirmed → shipped → delivered",
        "tags": ["order", "lifecycle"],
        "author": "bob",
    },
    {
        "title": "Product Catalog",
        "content": "# Product\n\n产品目录定义。\n\n## 分类\n- Electronics\n- Apparel\n- Home",
        "tags": ["product", "catalog"],
        "author": "carol",
    },
    {
        "title": "Supplier Onboarding",
        "content": "# Supplier\n\n供应商入库流程。\n\n## 评级\nrating: 1.0 - 5.0",
        "tags": ["supplier", "onboarding"],
        "author": "dave",
    },
    {
        "title": "Shipment Tracking",
        "content": "# Shipment\n\n运单追踪说明。\n\n## 承运商\nFedEx, UPS, DHL, SF Express",
        "tags": ["shipment", "tracking"],
        "author": "alice",
    },
    {
        "title": "Invoice Management",
        "content": "# Invoice\n\n发票管理。\n\n## 状态\ndraft → sent → paid",
        "tags": ["invoice", "finance"],
        "author": "eve",
    },
    {
        "title": "Data Governance",
        "content": "# Governance\n\n数据治理策略。\n\n## 标记\n- PII: customer.email\n- Confidential: annual_revenue",
        "tags": ["governance", "policy"],
        "author": "frank",
    },
    {
        "title": "Ontology Best Practices",
        "content": "# Best Practices\n\n本体建模最佳实践。\n\n## 命名规范\n- snake_case\n- 复数对象集合",
        "tags": ["ontology", "best-practices"],
        "author": "grace",
    },
    {
        "title": "Branch Strategy",
        "content": "# Branches\n\n本体分支策略。\n\n## 工作流\nfeature → review → merge to main",
        "tags": ["branches", "workflow"],
        "author": "henry",
    },
    {
        "title": "Functions Cookbook",
        "content": "# Functions\n\n常用 Function 示例。\n\n## 示例\n- compute_discount(amount, tier)\n- format_address(...)",
        "tags": ["functions", "cookbook"],
        "author": "ivy",
    },
    {
        "title": "Actions Manual",
        "content": "# Actions\n\nAction 触发手册。\n\n## 类型\n- writeback\n- notification",
        "tags": ["actions", "manual"],
        "author": "jack",
    },
    {
        "title": "Links Reference",
        "content": "# Links\n\n对象关系参考。\n\n## 类型\n- customer → order\n- order → shipment",
        "tags": ["links", "reference"],
        "author": "karen",
    },
    {
        "title": "Graph Health",
        "content": "# Graph Health\n\n图谱健康检查。\n\n## 指标\n- orphan_count: 0\n- mapping_coverage: 1.0",
        "tags": ["graph", "health"],
        "author": "leo",
    },
    {
        "title": "Migration Guide",
        "content": "# Migration\n\n本体迁移指南。\n\n## 步骤\n1. Export schema\n2. Map properties\n3. Validate",
        "tags": ["migration", "ops"],
        "author": "mia",
    },
    {
        "title": "FAQ",
        "content": "# FAQ\n\n常见问题。\n\n## Q1\n如何添加新属性？\nA: 调用 POST /object-types/:id/properties",
        "tags": ["faq", "help"],
        "author": "noah",
    },
]


def seed_phase4_ontology_wikis() -> int:
    """Seed 15 wikis + create 25 additional versions. Returns total count."""
    eng = get_wiki_engine()
    total = 0
    wiki_ids: list[str] = []
    for spec in _WIKIS_SPEC:
        w = eng.create_wiki(**spec)
        wiki_ids.append(w.id)
        total += 1  # 初始版本计入

    # 为前 10 个 wiki 创建额外版本（共 26 次更新）
    updates_done = 0
    target_updates = 26
    i = 0
    while updates_done < target_updates and wiki_ids:
        wid = wiki_ids[i % len(wiki_ids)]
        # 跳过 main（第 0 个不动）以避免影响 main，其实都可更新
        extra_v = f"\n\n## Update {updates_done + 1}\n新增内容段落 #{updates_done + 1}。"
        eng.update_wiki(wid, content=eng.get_wiki(wid).content + extra_v, message=f"Auto update {updates_done + 1}")
        eng.list_versions(wid)  # 触发版本记录
        updates_done += 1
        total += 1  # 每次更新产生一个新版本
        i += 1

    log.info("seed_phase4_ontology_wikis_done wikis=%s versions_total=%s", len(wiki_ids), total)
    return total
