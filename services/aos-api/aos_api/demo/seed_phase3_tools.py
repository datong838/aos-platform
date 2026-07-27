"""Phase 3 seed · AIP Tools — 15 个工具 + 10 evals + 5 circuits."""
from __future__ import annotations

from aos_api.aip_tools_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase3_tools")


def seed_phase3_tools() -> int:
    """Seed 15 tools + 10 evals + 5 circuits. Returns total count."""
    eng = get_engine()
    eng.reset()

    tools_data = [
        # data (3)
        ("QueryStream", "data", "查询数据流状态"),
        ("SchemaInfer", "data", "推断数据 Schema"),
        ("DatasetPreview", "data", "预览数据集"),
        # build (3)
        ("ValidateDSL", "build", "校验管道 DSL"),
        ("PreviewRun", "build", "试运行管道"),
        ("BuildDiagnostics", "build", "构建诊断"),
        # governance (2)
        ("OntologyBrowser", "governance", "浏览 Ontology"),
        ("AuditQuery", "governance", "查询审计日志"),
        # ai (2)
        ("FeatureRecommender", "ai", "推荐 ML 特征"),
        ("RAGRetriever", "ai", "RAG 检索"),
        # ops (2)
        ("DeployManager", "ops", "管理部署"),
        ("IncidentClassifier", "ops", "分类事件"),
        # security (2)
        ("PIIDetector", "security", "检测敏感数据"),
        ("InjectionGuard", "security", "注入防护"),
        # integration (1)
        ("WebhookDispatcher", "integration", "Webhook 分发"),
    ]

    quality_scores = [
        (92.5, 95.0, 88.0, 94.5),
        (88.0, 90.0, 85.0, 89.0),
        (95.0, 96.0, 92.0, 97.0),
        (91.0, 93.0, 89.0, 91.0),
        (87.5, 88.0, 86.0, 88.5),
        (84.0, 85.0, 82.0, 85.0),
        (96.0, 97.0, 94.0, 97.0),
        (93.0, 94.0, 91.0, 94.0),
        (78.5, 80.0, 75.0, 80.5),
        (90.0, 92.0, 88.0, 90.0),
        (89.0, 90.0, 87.0, 90.0),
        (82.0, 84.0, 80.0, 82.0),
        (94.0, 95.0, 92.0, 95.0),
        (91.5, 93.0, 89.0, 92.5),
        (86.0, 87.0, 84.0, 87.0),
    ]

    tool_ids = []
    for i, (name, cat, desc) in enumerate(tools_data):
        tool = eng.create_tool(name=name, category=cat, description=desc, calls=(i + 1) * 100)
        if i < len(quality_scores):
            o, a, l, r = quality_scores[i]
            eng.set_quality(tool.id, overall=o, accuracy=a, latency=l, reliability=r)
        tool_ids.append(tool.id)

    # 10 evals
    evals_data = [
        ("QueryStream Eval", "tool", tool_ids[0] if tool_ids else "", "passed", 92.5, True),
        ("SchemaInfer Eval", "tool", tool_ids[1] if len(tool_ids) > 1 else "", "passed", 88.0, True),
        ("RAG Retrieval Eval", "rag", tool_ids[9] if len(tool_ids) > 9 else "", "passed", 90.0, True),
        ("Feature Recommender Eval", "tool", tool_ids[8] if len(tool_ids) > 8 else "", "failed", 78.5, False),
        ("Build Diagnostics Eval", "tool", tool_ids[5] if len(tool_ids) > 5 else "", "running", 0, False),
        ("PII Detector Eval", "tool", tool_ids[12] if len(tool_ids) > 12 else "", "passed", 94.0, True),
        ("Generation Quality", "gen", "", "passed", 89.0, True),
        ("L4 Gate Check", "l4", "", "passed", 95.0, True),
        ("Injection Guard Eval", "tool", tool_ids[13] if len(tool_ids) > 13 else "", "pending", 0, False),
        ("Deploy Manager Eval", "tool", tool_ids[10] if len(tool_ids) > 10 else "", "passed", 89.0, True),
    ]

    for name, etype, target, status, score, l4 in evals_data:
        eng.create_eval(
            name=name, eval_type=etype, target_id=target,
            status=status, score=score, l4_allowed=l4,
            metrics={"precision": score * 0.95, "recall": score * 0.9} if score > 0 else {},
        )

    # 5 circuits
    circuit_targets = tool_ids[:5]
    for i, tid in enumerate(circuit_targets):
        eng.trip_circuit(tid, f"Test circuit trip #{i+1}")

    total = len(eng.list_tools()) + len(eng.list_evals()) + len(eng.list_circuits())
    log.info("seed_phase3_tools_done tools=%s evals=%s circuits=%s total=%s",
             len(eng.list_tools()), len(eng.list_evals()), len(eng.list_circuits()), total)
    return total
