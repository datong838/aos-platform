"""Phase 3 seed · AIP Agents — 15 个 Agent（含 prompt/tools/guardrails）."""
from __future__ import annotations

from aos_api.aip_agents_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase3_agents")


def seed_phase3_agents() -> int:
    """Seed 15 agents. Returns count."""
    eng = get_engine()
    eng.reset()

    agents_data = [
        {
            "name": "Data Health Copilot",
            "description": "监控数据流健康状态，诊断异常",
            "source": "platform",
            "tags": ["data", "monitoring", "diagnostics"],
            "system_prompt": "你是数据健康助手，负责监控数据流状态、诊断异常并提供修复建议。",
            "calls": 1280, "success_rate": 0.97, "avg_latency_ms": 340,
            "tools": [
                {"id": "tool-query-stream", "name": "QueryStream", "category": "data"},
                {"id": "tool-check-health", "name": "CheckHealth", "category": "data"},
            ],
            "guardrails": [
                {"id": "gr-001", "name": "PII过滤", "type": "pii", "action": "redact", "enabled": True},
                {"id": "gr-002", "name": "注入防护", "type": "injection", "action": "block", "enabled": True},
            ],
        },
        {
            "name": "Pipeline Builder",
            "description": "辅助构建 ETL 管道",
            "source": "platform",
            "tags": ["build", "etl", "pipeline"],
            "system_prompt": "你是管道构建专家，帮助用户设计和调试 ETL 流程。",
            "calls": 856, "success_rate": 0.94, "avg_latency_ms": 520,
            "tools": [
                {"id": "tool-validate-dsl", "name": "ValidateDSL", "category": "build"},
                {"id": "tool-preview", "name": "PreviewRun", "category": "build"},
            ],
            "guardrails": [
                {"id": "gr-003", "name": "Token限制", "type": "token_limit", "action": "warn", "enabled": True},
            ],
        },
        {
            "name": "Ontology Explorer",
            "description": "探索和查询 Ontology 对象",
            "source": "platform",
            "tags": ["ontology", "explore"],
            "system_prompt": "你是 Ontology 导航员，帮助用户查询对象类型、属性和关系。",
            "calls": 2100, "success_rate": 0.99, "avg_latency_ms": 180,
        },
        {
            "name": "Report Generator",
            "description": "生成 SLA/健康/审计报告",
            "source": "platform",
            "tags": ["report", "analytics"],
            "system_prompt": "你是报告生成助手，负责汇总指标并产出结构化报告。",
            "calls": 670, "success_rate": 0.96, "avg_latency_ms": 890,
        },
        {
            "name": "Security Auditor",
            "description": "安全审计与合规检查",
            "source": "platform",
            "tags": ["security", "governance", "audit"],
            "system_prompt": "你是安全审计员，负责检查权限配置、敏感数据和合规策略。",
            "calls": 430, "success_rate": 0.98, "avg_latency_ms": 410,
        },
        {
            "name": "ML Feature Advisor",
            "description": "推荐机器学习特征",
            "source": "marketplace",
            "tags": ["ai", "ml", "feature"],
            "system_prompt": "你是 ML 特征工程顾问，帮助用户选择和构造特征。",
            "calls": 320, "success_rate": 0.91, "avg_latency_ms": 1200,
        },
        {
            "name": "SQL Optimizer",
            "description": "优化 SQL 查询性能",
            "source": "marketplace",
            "tags": ["sql", "optimization"],
            "system_prompt": "你是 SQL 性能优化专家，分析查询计划并推荐索引策略。",
            "calls": 540, "success_rate": 0.95, "avg_latency_ms": 350,
        },
        {
            "name": "Schema Validator",
            "description": "校验数据 Schema 漂移",
            "source": "platform",
            "tags": ["schema", "validation"],
            "system_prompt": "你是 Schema 校验器，检测字段类型变化并提供迁移建议。",
            "calls": 280, "success_rate": 0.97, "avg_latency_ms": 220,
        },
        {
            "name": "Incident Responder",
            "description": "自动化事件响应",
            "source": "custom",
            "tags": ["ops", "incident", "automation"],
            "system_prompt": "你是事件响应 Agent，负责自动分类和初步处置生产事件。",
            "calls": 190, "success_rate": 0.93, "avg_latency_ms": 600,
        },
        {
            "name": "Lineage Tracer",
            "description": "追溯数据血缘",
            "source": "platform",
            "tags": ["lineage", "trace"],
            "system_prompt": "你是血缘追溯助手，帮助用户理解数据的来源和流向。",
            "calls": 410, "success_rate": 0.99, "avg_latency_ms": 150,
        },
        {
            "name": "Cost Analyst",
            "description": "分析计算资源成本",
            "source": "marketplace",
            "tags": ["cost", "analytics", "finops"],
            "system_prompt": "你是成本分析 Agent，帮助用户优化计算资源使用和预算。",
            "calls": 150, "success_rate": 0.92, "avg_latency_ms": 700,
        },
        {
            "name": "Test Generator",
            "description": "生成数据质量测试",
            "source": "platform",
            "tags": ["test", "quality"],
            "system_prompt": "你是测试生成器，为数据管道自动生成期望测试。",
            "calls": 220, "success_rate": 0.96, "avg_latency_ms": 300,
        },
        {
            "name": "Deploy Assistant",
            "description": "辅助部署和回滚",
            "source": "platform",
            "tags": ["deploy", "ops"],
            "system_prompt": "你是部署助手，帮助用户管理构建版本和发布流程。",
            "calls": 380, "success_rate": 0.98, "avg_latency_ms": 250,
        },
        {
            "name": "Knowledge Base QA",
            "description": "基于知识库的问答",
            "source": "marketplace",
            "tags": ["rag", "qa", "knowledge"],
            "system_prompt": "你是知识库问答 Agent，基于平台文档和最佳实践提供解答。",
            "calls": 1500, "success_rate": 0.94, "avg_latency_ms": 450,
        },
        {
            "name": "Workflow Designer",
            "description": "设计自动化工作流",
            "source": "custom",
            "tags": ["workflow", "automation", "design"],
            "system_prompt": "你是工作流设计器，帮助用户编排自动化触发器和动作。",
            "calls": 95, "success_rate": 0.90, "avg_latency_ms": 800,
        },
    ]

    for d in agents_data:
        eng.create(**d)

    log.info("seed_phase3_agents_done count=%s", len(eng.list()))
    return len(eng.list())
