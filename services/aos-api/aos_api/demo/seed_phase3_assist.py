"""Phase 3 seed · AIP Assist — 5 条对话 + 12 条 suggestions.

种子加载到内存引擎，无数据库依赖。
"""
from __future__ import annotations

from aos_api.aip_assist_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase3_assist")


def seed_phase3_assist() -> int:
    """Idempotently seed assist engine. Returns total record count."""
    eng = get_engine()
    eng.reset()

    # welcome 已在引擎初始化中设置
    # suggestions 12 条已初始化

    # 创建 5 条对话历史
    conversations = [
        ("今天的数据流延迟如何？", [
            ("user", "今天的数据流延迟如何？"),
            ("assistant", "根据平台监控数据，当前 12 个数据流的健康状态为 100% 正常，其中 3 个增量同步任务平均延迟低于 5 秒。"),
        ]),
        ("Ontology 对象列表", [
            ("user", "帮我查看 Ontology「客户360」的对象列表"),
            ("assistant", "本 Ontology 包含 47 个对象类型，其中 8 个启用了 L4 自动化。你可以在「治理 → 角色」中查看权限映射。"),
        ]),
        ("Pipeline 构建日志", [
            ("user", "Pipeline「order-sync」最近的构建日志"),
            ("assistant", "order-sync 最近一次构建在 14:32 完成，耗时 3 分 21 秒，状态为 SUCCESS。有 2 个 WARNING 关于 schema 漂移。"),
        ]),
        ("SLA 报告", [
            ("user", "生成本周数据健康报告"),
            ("assistant", "已为你生成报告草稿，覆盖最近 7 天的 SLA 指标，请前往「草稿审查」页面确认发布。"),
        ]),
        ("ETL 影响分析", [
            ("user", "为什么昨天的增量任务失败了？"),
            ("assistant", "检测到 2 条 ETL 逻辑可能受 schema 漂移影响，建议在合并前运行影响分析。"),
        ]),
    ]

    for title, msgs in conversations:
        conv = eng.create_conversation(title=title)
        for role, content in msgs:
            eng.add_message(conv.id, role, content)

    total = len(eng.list_conversations()) + len(eng.list_suggestions())
    log.info("seed_phase3_assist_done conversations=%s suggestions=%s total=%s",
             len(eng.list_conversations()), len(eng.list_suggestions()), total)
    return total
