"""Phase 3 seed · AIP Capabilities — 20 个能力项 + 注册表."""
from __future__ import annotations

from aos_api.aip_capabilities_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase3_capabilities")


def seed_phase3_capabilities() -> int:
    """Seed 20 capabilities + registry entries. Returns count."""
    eng = get_engine()
    eng.reset()

    caps_data = [
        ("数据查询", "data", "查询数据流、数据集和对象属性"),
        ("数据预览", "data", "预览数据集前 N 行"),
        ("Schema 推断", "data", "自动推断数据 Schema"),
        ("管道构建", "build", "创建和编辑 ETL 管道"),
        ("管道预览", "build", "试运行管道并预览输出"),
        ("构建诊断", "build", "分析构建失败原因"),
        ("Ontology 浏览", "governance", "浏览对象类型和关系"),
        ("权限管理", "governance", "管理角色和权限"),
        ("审计日志", "governance", "查询平台审计记录"),
        ("ML 特征推荐", "ai", "推荐机器学习特征"),
        ("模型评估", "ai", "评估模型质量"),
        ("RAG 问答", "ai", "基于知识库的检索增强问答"),
        ("部署管理", "ops", "管理构建版本和部署"),
        ("事件响应", "ops", "自动化事件分类和处置"),
        ("调度管理", "ops", "管理定时任务和触发器"),
        ("敏感数据检测", "security", "检测 PII 和敏感字段"),
        ("注入防护", "security", "防止提示注入攻击"),
        ("内容过滤", "security", "过滤不当内容"),
        ("Token 限制", "security", "控制 Token 消耗"),
        ("血缘追溯", "data", "追溯数据来源和流向"),
    ]

    cap_ids = []
    for name, cat, desc in caps_data:
        cap = eng.create_capability(name=name, category=cat, description=desc)
        cap_ids.append(cap.id)

    # 添加几个注册条目
    registry_data = [
        ("aip-agent-001", "Data Health Copilot", [0, 1, 6, 15], "org", "registered"),
        ("aip-agent-002", "Pipeline Builder", [3, 4, 5, 12], "org", "registered"),
        ("aip-agent-003", "Security Auditor", [7, 8, 15, 16, 17, 18], "org", "registered"),
        ("aip-agent-004", "ML Feature Advisor", [9, 10, 11], "project", "pending"),
        ("aip-agent-005", "Knowledge Base QA", [0, 11, 19], "org", "registered"),
    ]

    for agent_id, agent_name, cap_indices, scope, status in registry_data:
        caps = [cap_ids[i] for i in cap_indices if i < len(cap_ids)]
        eng.register(agent_id=agent_id, agent_name=agent_name, capabilities=caps, scope=scope, status=status)

    total = len(eng.list_capabilities()) + len(eng.list_registry())
    log.info("seed_phase3_capabilities_done caps=%s registry=%s total=%s",
             len(eng.list_capabilities()), len(eng.list_registry()), total)
    return total
