"""Phase 3 seed · AIP Logic — 10 个逻辑流 + automations."""
from __future__ import annotations

from aos_api.aip_logic_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase3_logic")


def seed_phase3_logic() -> int:
    """Seed 10 logic flows + automations. Returns count."""
    eng = get_engine()
    eng.reset()

    flows_data = [
        ("数据健康检查流", [
            {"kind": "task", "name": "Fetch Streams", "config": {"source": "monitor"}},
            {"kind": "branch", "name": "Health Gate", "config": {"condition": "success", "paths": ["healthy", "unhealthy"]}},
            {"kind": "llm", "name": "Diagnose", "config": {"prompt": "Analyze stream health"}},
            {"kind": "handoff", "name": "Merge Reports"},
        ]),
        ("ETL 异常诊断", [
            {"kind": "task", "name": "Get Build Log"},
            {"kind": "branch", "name": "Error Type", "config": {"condition": "schema_drift", "paths": ["schema", "timeout", "data"]}},
            {"kind": "llm", "name": "Root Cause", "config": {"prompt": "Identify root cause"}},
            {"kind": "tool", "name": "Fix Suggestion", "config": {"tool": "schema-fixer"}},
        ]),
        ("SLA 报告生成", [
            {"kind": "task", "name": "Aggregate Metrics"},
            {"kind": "llm", "name": "Generate Report", "config": {"prompt": "Generate SLA report"}},
            {"kind": "handoff", "name": "Compile"},
        ]),
        ("权限审计流", [
            {"kind": "task", "name": "List Users"},
            {"kind": "branch", "name": "Role Check", "config": {"condition": "has_admin", "paths": ["admin", "standard"]}},
            {"kind": "tool", "name": "Audit Log", "config": {"tool": "audit-query"}},
        ]),
        ("管道部署审批", [
            {"kind": "task", "name": "Validate Build"},
            {"kind": "branch", "name": "Approval Gate", "config": {"condition": "approved", "paths": ["proceed", "reject"]}},
            {"kind": "task", "name": "Deploy"},
        ]),
        ("Schema 漂移检测", [
            {"kind": "task", "name": "Compare Schema"},
            {"kind": "branch", "name": "Drift?", "config": {"condition": "drift_detected", "paths": ["migrate", "no_action"]}},
            {"kind": "llm", "name": "Migration Plan"},
        ]),
        ("成本优化建议", [
            {"kind": "task", "name": "Collect Usage"},
            {"kind": "llm", "name": "Analyze Costs"},
            {"kind": "handoff", "name": "Summarize"},
        ]),
        ("事件自动响应", [
            {"kind": "task", "name": "Classify Incident"},
            {"kind": "branch", "name": "Severity", "config": {"condition": "severity_high", "paths": ["escalate", "auto_fix"]}},
            {"kind": "tool", "name": "Execute Fix"},
        ]),
        ("知识库索引更新", [
            {"kind": "task", "name": "Fetch Docs"},
            {"kind": "llm", "name": "Generate Embeddings"},
            {"kind": "handoff", "name": "Update Index"},
        ]),
        ("数据质量评估", [
            {"kind": "task", "name": "Run Expectations"},
            {"kind": "branch", "name": "Quality Gate", "config": {"condition": "pass", "paths": ["pass", "fail"]}},
            {"kind": "llm", "name": "Report"},
        ]),
    ]

    for name, blocks in flows_data:
        eng.create_flow(name=name, blocks=blocks, status="active")

    # 创建 automations
    autos_data = [
        ("Daily Health Check", "schedule", {"cron": "0 9 * * *"}, eng.list_flows()[0].id if eng.list_flows() else ""),
        ("Build Failure Alert", "event", {"event": "build.failed"}, eng.list_flows()[1].id if len(eng.list_flows()) > 1 else ""),
        ("Weekly SLA Report", "schedule", {"cron": "0 10 * * 1"}, eng.list_flows()[2].id if len(eng.list_flows()) > 2 else ""),
        ("Permission Audit", "schedule", {"cron": "0 2 * * *"}, ""),
        ("Deploy Approval Webhook", "webhook", {"url": "/hooks/deploy"}, ""),
    ]

    for name, ttype, config, flow_id in autos_data:
        eng.create_automation(name=name, trigger_type=ttype, trigger_config=config, flow_id=flow_id)

    total = len(eng.list_flows()) + len(eng.list_automations())
    log.info("seed_phase3_logic_done flows=%s autos=%s total=%s",
             len(eng.list_flows()), len(eng.list_automations()), total)
    return total
