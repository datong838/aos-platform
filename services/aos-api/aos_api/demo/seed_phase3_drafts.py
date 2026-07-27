"""Phase 3 seed · AIP Drafts — 15 个审查任务."""
from __future__ import annotations

from aos_api.aip_drafts_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase3_drafts")


def seed_phase3_drafts() -> int:
    """Seed 15 draft reviews. Returns count."""
    eng = get_engine()
    eng.reset()

    drafts_data = [
        ("SLA 周报草稿", "report", "data-bot", "analyst-1", "draft", "本周 SLA 达成率 98.5%"),
        ("客户360 Schema 变更", "config", "schema-bot", "admin-1", "approved", "新增 phone 字段"),
        ("Pipeline order-sync v2", "pipeline", "build-bot", "analyst-2", "draft", "优化增量逻辑"),
        ("安全审计报告 2026Q2", "report", "audit-bot", "admin-1", "approved", "覆盖 47 个对象"),
        ("Ontology 权限调整", "config", "perm-bot", "admin-2", "draft", "新增 viewer 角色"),
        ("ETL 脚本重构", "code", "etl-bot", "dev-1", "rejected", "需修复 schema 引用"),
        ("月度数据健康报告", "report", "health-bot", "analyst-1", "draft", "12 条数据流全绿"),
        ("成本分析配置更新", "config", "cost-bot", "admin-1", "approved", "预算告警阈值调整"),
        ("自动化触发器新增", "config", "auto-bot", "admin-2", "draft", "新增 build.failed 触发器"),
        ("部署审批 order-sync", "pipeline", "deploy-bot", "dev-1", "approved", "v2.1.0"),
        ("ML 特征工程草稿", "code", "ml-bot", "dev-2", "draft", "新增 5 个特征"),
        ("数据质量规则更新", "config", "quality-bot", "analyst-2", "draft", "新增 3 条期望规则"),
        ("审计日志查询草稿", "report", "audit-bot", "admin-1", "rejected", "时间范围需调整"),
        ("Webhook 配置草稿", "config", "webhook-bot", "dev-1", "draft", "新增 deploy.success webhook"),
        ("Copilot 响应模板", "code", "copilot-bot", "dev-2", "approved", "新增 3 个 FAQ 模板"),
    ]

    for title, dtype, author, reviewer, status, content in drafts_data:
        draft = eng.create(title=title, draft_type=dtype, author=author, reviewer=reviewer, content=content)
        if status == "approved":
            eng.approve(draft.id, reviewer=reviewer)
        elif status == "rejected":
            eng.reject(draft.id, reviewer=reviewer, reason="Seed rejected")

    log.info("seed_phase3_drafts_done count=%s", len(eng.list()))
    return len(eng.list())
