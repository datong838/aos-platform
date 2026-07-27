"""Phase 3 seed · AIP Lineage — 20 条决策 trace（每条 6 段）."""
from __future__ import annotations

from aos_api.aip_lineage_engine import get_engine, TraceSegment
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase3_lineage")


def seed_phase3_lineage() -> int:
    """Seed 20 lineage records. Returns count."""
    eng = get_engine()
    eng.reset()

    queries = [
        ("aip-agent-001", "今天的数据流延迟如何？", "ok", 430, 347),
        ("aip-agent-002", "Pipeline order-sync 构建日志", "ok", 520, 410),
        ("aip-agent-003", "Ontology 对象列表", "ok", 180, 120),
        ("aip-agent-001", "为什么增量任务失败？", "degraded", 680, 520),
        ("aip-agent-004", "生成本周 SLA 报告", "ok", 890, 650),
        ("aip-agent-005", "安全审计检查", "ok", 410, 280),
        ("aip-agent-001", "Schema 漂移影响分析", "ok", 350, 240),
        ("aip-agent-002", "构建诊断 order-sync", "degraded", 720, 500),
        ("aip-agent-006", "ML 特征推荐", "ok", 1200, 890),
        ("aip-agent-007", "SQL 查询优化", "ok", 350, 230),
        ("aip-agent-001", "数据血缘追溯", "ok", 150, 90),
        ("aip-agent-008", "成本分析", "ok", 700, 480),
        ("aip-agent-003", "权限映射查询", "ok", 200, 140),
        ("aip-agent-005", "PII 检测报告", "failed", 320, 50),
        ("aip-agent-009", "知识库检索", "ok", 450, 310),
        ("aip-agent-001", "事件分类", "degraded", 600, 420),
        ("aip-agent-004", "报告草稿审查", "ok", 250, 180),
        ("aip-agent-002", "部署审批", "ok", 180, 120),
        ("aip-agent-007", "Schema 校验", "ok", 220, 150),
        ("aip-agent-006", "模型评估结果", "ok", 550, 390),
    ]

    for agent_id, query, status, duration, tokens in queries:
        segments = eng.build_default_trace(agent_id, query)
        # 根据状态调整 segments
        if status == "degraded":
            segments[2] = TraceSegment(name="reasoning", status="warning", duration_ms=duration,
                                       detail={"model": "gpt-4o", "tokens": tokens, "note": "slow"})
            segments[3] = TraceSegment(name="circuit", status="warning", duration_ms=8,
                                       detail={"breaker_state": "half_open"})
        elif status == "failed":
            segments[3] = TraceSegment(name="circuit", status="error", duration_ms=3,
                                       detail={"breaker_state": "open", "reason": "timeout"})
            segments[4] = TraceSegment(name="output", status="error", duration_ms=5,
                                       detail={"error": "circuit_open"})
        else:
            for seg in segments:
                if seg.name == "reasoning":
                    seg.duration_ms = duration
                    seg.detail["tokens"] = tokens

        eng.create(
            agent_id=agent_id, query=query, segments=segments,
            total_duration_ms=duration, tokens_used=tokens, status=status,
        )

    log.info("seed_phase3_lineage_done count=%s", len(eng.list()))
    return len(eng.list())
