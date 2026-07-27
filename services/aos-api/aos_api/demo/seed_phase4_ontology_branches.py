"""Phase 4 seed · Ontology Branches — 3 分支 + 状态."""
from __future__ import annotations

from aos_api.ontology_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase4_ontology_branches")


_BRANCHES_SPEC: list[dict] = [
    {
        "name": "main",
        "parent_branch": "",
        "status": "active",
        "description": "Production branch",
        "created_by": "system",
    },
    {
        "name": "dev-customer-enrichment",
        "parent_branch": "main",
        "status": "active",
        "description": "添加客户增强属性",
        "created_by": "alice",
    },
    {
        "name": "feature-shipment-v2",
        "parent_branch": "main",
        "status": "active",
        "description": "运单模型重构",
        "created_by": "bob",
    },
    {
        "name": "release-q1",
        "parent_branch": "main",
        "status": "merged",
        "description": "Q1 发布分支",
        "created_by": "carol",
    },
    {
        "name": "hotfix-invoice-tax",
        "parent_branch": "main",
        "status": "merged",
        "description": "发票税额修复",
        "created_by": "dave",
    },
    {
        "name": "exp-product-categories",
        "parent_branch": "main",
        "status": "active",
        "description": "产品分类扩展实验",
        "created_by": "eve",
    },
    {
        "name": "refactor-supplier-rating",
        "parent_branch": "dev-customer-enrichment",
        "status": "active",
        "description": "供应商评级重构",
        "created_by": "frank",
    },
    {
        "name": "chore-cleanup-props",
        "parent_branch": "main",
        "status": "abandoned",
        "description": "属性命名清理（已废弃）",
        "created_by": "grace",
    },
    {
        "name": "feat-order-discount",
        "parent_branch": "main",
        "status": "active",
        "description": "订单折扣逻辑",
        "created_by": "henry",
    },
    {
        "name": "release-q2",
        "parent_branch": "main",
        "status": "active",
        "description": "Q2 发布分支",
        "created_by": "ivy",
    },
]


def seed_phase4_ontology_branches() -> int:
    """Seed 3 branches. Returns count."""
    eng = get_engine()
    count = 0
    for spec in _BRANCHES_SPEC:
        eng.create_branch(**spec)
        count += 1
    log.info("seed_phase4_ontology_branches_done branches=%s", count)
    return count
