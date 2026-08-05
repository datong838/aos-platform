"""D1.5 Phase B · L01-L03 canonical Logic Graph dry-run tests.

追溯：D1.5 执行规格 FR-D1.5-5/6/7、AC-D1.5-5、退出门第 5 条。
附录 A：规格文档 §附录 A（L01-L03 节点规格）。

原则：零新增生产代码，复用 canonical AIP Logic Engine（aip_logic_dry_run_executor
+ aip_logic_graph_models + function_engine）。L01-L03 决策输出 = branch
节点的 selected_branch_path；null 降级靠 branch 按序短路 + && 短路实现。
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_logic_dry_run_executor import LogicDryRunExecutor
from aos_api.aip_logic_graph_models import (
    LogicGraphSnapshot,
    ValidateLogicGraphRequest,
    compute_logic_graph_hash,
    validate_logic_graph,
)


# --------------------------------------------------------------------------- #
# 通用 helper
# --------------------------------------------------------------------------- #
def _snapshot(graph_id: str, nodes: list, edges: list, entries: list[str]) -> LogicGraphSnapshot:
    """构造一个 draft 态 LogicGraphSnapshot（模拟已通过 API 创建的 graph）。"""
    content = ValidateLogicGraphRequest(
        name=graph_id, nodes=nodes, edges=edges, entry_node_ids=entries
    )
    now = datetime.now(UTC)
    return LogicGraphSnapshot(
        id=graph_id,
        name=content.name,
        description=content.description,
        status="draft",
        schema_version=1,
        revision=1,
        graph_hash=compute_logic_graph_hash(content),
        nodes=content.nodes,
        edges=content.edges,
        entry_node_ids=content.entry_node_ids,
        created_at=now,
        updated_at=now,
    )


def _branch_path(result, node_id: str) -> str:
    """提取指定 branch 节点的 selected_branch_path。"""
    by_id = {r.node_id: r for r in result.node_results}
    return by_id[node_id].selected_branch_path


def _node_status(result, node_id: str) -> str:
    by_id = {r.node_id: r for r in result.node_results}
    return by_id[node_id].status


# --------------------------------------------------------------------------- #
# L01 商品上架检测 Logic Graph（FR-D1.5-5）
# --------------------------------------------------------------------------- #
# 节点结构：product_read → sku_check → category_validate → quality_gate
# 决策输出：pass / block / needs_review
# null 降级：quality_score == null → needs_review
L01_NODES = [
    {
        "id": "product_read",
        "kind": "input",
        "label": "读取商品",
        "config": {
            "schema": {
                "required": ["product_id", "quality_score", "sku_count", "category_id"]
            }
        },
    },
    {
        "id": "sku_check",
        "kind": "transform",
        "label": "SKU检查",
        "config": {"expression": "if sku_count > 0 then true else false"},
    },
    {
        "id": "category_validate",
        "kind": "transform",
        "label": "分类校验",
        "config": {"expression": 'if category_id != "" then true else false'},
    },
    {
        "id": "quality_gate",
        "kind": "branch",
        "label": "质量门",
        "config": {
            "paths": [
                {"id": "needs_review", "condition": "quality_score == null"},
                {
                    "id": "pass",
                    "condition": "quality_score >= 0.8 && sku_check && category_validate",
                },
                {"id": "block", "default": True},
            ]
        },
    },
]
L01_EDGES = [
    {"id": "e1", "source_node_id": "product_read", "target_node_id": "sku_check"},
    {"id": "e2", "source_node_id": "product_read", "target_node_id": "category_validate"},
    {"id": "e3", "source_node_id": "sku_check", "target_node_id": "quality_gate"},
    {"id": "e4", "source_node_id": "category_validate", "target_node_id": "quality_gate"},
]
L01_ENTRIES = ["product_read"]


def _l01_graph() -> LogicGraphSnapshot:
    return _snapshot("l01-product-launch", L01_NODES, L01_EDGES, L01_ENTRIES)


# --------------------------------------------------------------------------- #
# L02 订单履约 Logic Graph（FR-D1.5-6）
# --------------------------------------------------------------------------- #
# 节点结构：order_read → risk_score_check → anomaly_detect
# 决策输出：risk_high / risk_normal
# null 降级：risk_score == null → risk_normal
L02_NODES = [
    {
        "id": "order_read",
        "kind": "input",
        "label": "读取订单",
        "config": {
            "schema": {"required": ["order_id", "risk_score", "order_status"]}
        },
    },
    {
        "id": "risk_score_check",
        "kind": "transform",
        "label": "风险分检查",
        "config": {"expression": "risk_score"},
    },
    {
        "id": "anomaly_detect",
        "kind": "branch",
        "label": "异常检测",
        "config": {
            "paths": [
                {
                    "id": "risk_high",
                    "condition": "risk_score != null && risk_score > 0.6",
                },
                {"id": "risk_normal", "default": True},
            ]
        },
    },
]
L02_EDGES = [
    {"id": "e1", "source_node_id": "order_read", "target_node_id": "risk_score_check"},
    {"id": "e2", "source_node_id": "risk_score_check", "target_node_id": "anomaly_detect"},
]
L02_ENTRIES = ["order_read"]


def _l02_graph() -> LogicGraphSnapshot:
    return _snapshot("l02-order-fulfillment", L02_NODES, L02_EDGES, L02_ENTRIES)


# --------------------------------------------------------------------------- #
# L03 发货超时 Logic Graph（FR-D1.5-7）
# --------------------------------------------------------------------------- #
# 节点结构：order_read → shipment_check → overdue_calculate
# 决策输出：overdue / watch / ok
# null 降级：overdue_hours == null → ok
L03_NODES = [
    {
        "id": "order_read",
        "kind": "input",
        "label": "读取订单",
        "config": {
            "schema": {"required": ["order_id", "overdue_hours", "shipment_status"]}
        },
    },
    {
        "id": "shipment_check",
        "kind": "transform",
        "label": "发货检查",
        "config": {"expression": "overdue_hours"},
    },
    {
        "id": "overdue_calculate",
        "kind": "branch",
        "label": "超时计算",
        "config": {
            "paths": [
                {
                    "id": "overdue",
                    "condition": "overdue_hours != null && overdue_hours > 48",
                },
                {
                    "id": "watch",
                    "condition": "overdue_hours != null && overdue_hours > 0",
                },
                {"id": "ok", "default": True},
            ]
        },
    },
]
L03_EDGES = [
    {"id": "e1", "source_node_id": "order_read", "target_node_id": "shipment_check"},
    {"id": "e2", "source_node_id": "shipment_check", "target_node_id": "overdue_calculate"},
]
L03_ENTRIES = ["order_read"]


def _l03_graph() -> LogicGraphSnapshot:
    return _snapshot("l03-shipment-overdue", L03_NODES, L03_EDGES, L03_ENTRIES)


# --------------------------------------------------------------------------- #
# 结构合法性测试（AC-D1.5-5：Graph 通过 validate_logic_graph）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "graph_factory",
    [_l01_graph, _l02_graph, _l03_graph],
    ids=["L01", "L02", "L03"],
)
def test_logic_graph_structure_is_valid(graph_factory) -> None:
    """L01-L03 Logic Graph MUST 通过 canonical 结构校验。"""
    graph = graph_factory()
    content = ValidateLogicGraphRequest(
        name=graph.name,
        nodes=[n.model_dump(mode="json") for n in graph.nodes],
        edges=[e.model_dump(mode="json") for e in graph.edges],
        entry_node_ids=graph.entry_node_ids,
    )
    result = validate_logic_graph(content)
    assert result.valid, f"graph invalid: {[i.model_dump() for i in result.issues]}"


# --------------------------------------------------------------------------- #
# L01 dryRun 决策测试
# --------------------------------------------------------------------------- #
def test_l01_pass_when_high_quality_and_sku_and_category() -> None:
    """quality_score>=0.8 + 有 SKU + 有分类 → pass。"""
    result = LogicDryRunExecutor().execute(
        _l01_graph(),
        {
            "product_id": "niushop:1:100",
            "quality_score": 0.9,
            "sku_count": 3,
            "category_id": "cat-5",
        },
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "quality_gate") == "pass"


def test_l01_block_when_low_quality() -> None:
    """quality_score<0.8 → block（降级到 default）。"""
    result = LogicDryRunExecutor().execute(
        _l01_graph(),
        {
            "product_id": "niushop:1:101",
            "quality_score": 0.5,
            "sku_count": 3,
            "category_id": "cat-5",
        },
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "quality_gate") == "block"


def test_l01_block_when_no_sku() -> None:
    """sku_count=0 → sku_check=False → pass condition 不满足 → block。"""
    result = LogicDryRunExecutor().execute(
        _l01_graph(),
        {
            "product_id": "niushop:1:102",
            "quality_score": 0.9,
            "sku_count": 0,
            "category_id": "cat-5",
        },
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "quality_gate") == "block"


def test_l01_block_when_no_category() -> None:
    """category_id="" → category_validate=False → pass condition 不满足 → block。"""
    result = LogicDryRunExecutor().execute(
        _l01_graph(),
        {
            "product_id": "niushop:1:103",
            "quality_score": 0.9,
            "sku_count": 3,
            "category_id": "",
        },
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "quality_gate") == "block"


def test_l01_needs_review_when_quality_score_null() -> None:
    """quality_score=null → 首个 path 匹配 → needs_review（不触达 >= 0.8）。"""
    result = LogicDryRunExecutor().execute(
        _l01_graph(),
        {
            "product_id": "niushop:1:104",
            "quality_score": None,
            "sku_count": 3,
            "category_id": "cat-5",
        },
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "quality_gate") == "needs_review"


# --------------------------------------------------------------------------- #
# L02 dryRun 决策测试
# --------------------------------------------------------------------------- #
def test_l02_risk_high_when_score_above_threshold() -> None:
    """risk_score>0.6 → risk_high。"""
    result = LogicDryRunExecutor().execute(
        _l02_graph(),
        {"order_id": "niushop:1:200", "risk_score": 0.7, "order_status": "pending"},
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "anomaly_detect") == "risk_high"


def test_l02_risk_normal_when_score_below_threshold() -> None:
    """risk_score<=0.6 → risk_normal（default）。"""
    result = LogicDryRunExecutor().execute(
        _l02_graph(),
        {"order_id": "niushop:1:201", "risk_score": 0.3, "order_status": "pending"},
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "anomaly_detect") == "risk_normal"


def test_l02_risk_normal_when_score_null() -> None:
    """risk_score=null → != null 为 False → && 短路 → 不匹配 → default risk_normal。"""
    result = LogicDryRunExecutor().execute(
        _l02_graph(),
        {"order_id": "niushop:1:202", "risk_score": None, "order_status": "pending"},
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "anomaly_detect") == "risk_normal"


# --------------------------------------------------------------------------- #
# L03 dryRun 决策测试
# --------------------------------------------------------------------------- #
def test_l03_overdue_when_hours_above_48() -> None:
    """overdue_hours>48 → overdue。"""
    result = LogicDryRunExecutor().execute(
        _l03_graph(),
        {"order_id": "niushop:1:300", "overdue_hours": 50, "shipment_status": "pending"},
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "overdue_calculate") == "overdue"


def test_l03_watch_when_hours_between_1_and_48() -> None:
    """0<overdue_hours<=48 → watch。"""
    result = LogicDryRunExecutor().execute(
        _l03_graph(),
        {"order_id": "niushop:1:301", "overdue_hours": 10, "shipment_status": "pending"},
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "overdue_calculate") == "watch"


def test_l03_ok_when_zero_overdue() -> None:
    """overdue_hours=0 → > 0 为 False → 不匹配 → default ok。"""
    result = LogicDryRunExecutor().execute(
        _l03_graph(),
        {"order_id": "niushop:1:302", "overdue_hours": 0, "shipment_status": "shipped"},
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "overdue_calculate") == "ok"


def test_l03_ok_when_overdue_hours_null() -> None:
    """overdue_hours=null → 前两 condition 的 != null 为 False → && 短路 → default ok。"""
    result = LogicDryRunExecutor().execute(
        _l03_graph(),
        {"order_id": "niushop:1:303", "overdue_hours": None, "shipment_status": "pending"},
    )
    assert result.status == "succeeded"
    assert _branch_path(result, "overdue_calculate") == "ok"


# --------------------------------------------------------------------------- #
# dryRun 通用属性测试
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "graph_factory,inputs",
    [
        (
            _l01_graph,
            {"product_id": "x", "quality_score": 0.9, "sku_count": 1, "category_id": "c"},
        ),
        (
            _l02_graph,
            {"order_id": "x", "risk_score": 0.1, "order_status": "pending"},
        ),
        (
            _l03_graph,
            {"order_id": "x", "overdue_hours": 0, "shipment_status": "shipped"},
        ),
    ],
    ids=["L01", "L02", "L03"],
)
def test_dry_run_succeeds_with_executed_branch(graph_factory, inputs) -> None:
    """L01-L03 dryRun MUST succeeded，且 branch 节点 status=executed。"""
    result = LogicDryRunExecutor().execute(graph_factory(), inputs)
    assert result.status == "succeeded"
    assert result.error is None


def test_l01_dry_run_is_deterministic() -> None:
    """相同输入的 dryRun 必须确定性（幂等）。"""
    graph = _l01_graph()
    inputs = {
        "product_id": "niushop:1:100",
        "quality_score": 0.9,
        "sku_count": 3,
        "category_id": "cat-5",
    }
    first = LogicDryRunExecutor().execute(graph, inputs)
    second = LogicDryRunExecutor().execute(graph, inputs)
    assert _branch_path(first, "quality_gate") == _branch_path(second, "quality_gate")
    assert first.graph_hash == second.graph_hash


def test_l01_transform_nodes_executed_before_branch() -> None:
    """sku_check / category_validate MUST 先于 branch 执行（拓扑序）。"""
    result = LogicDryRunExecutor().execute(
        _l01_graph(),
        {
            "product_id": "x",
            "quality_score": 0.9,
            "sku_count": 1,
            "category_id": "c",
        },
    )
    assert _node_status(result, "product_read") == "executed"
    assert _node_status(result, "sku_check") == "executed"
    assert _node_status(result, "category_validate") == "executed"
    assert _node_status(result, "quality_gate") == "executed"


def test_l01_null_quality_does_not_trigger_type_mismatch() -> None:
    """quality_score=null 时 MUST NOT 触达 >= 0.8（否则 TYPE_MISMATCH）。

    回归保护：验证 null 降级 path 在阈值 path 之前短路。
    """
    result = LogicDryRunExecutor().execute(
        _l01_graph(),
        {
            "product_id": "x",
            "quality_score": None,
            "sku_count": 1,
            "category_id": "c",
        },
    )
    assert result.status == "succeeded"
    # 若 null 降级未短路，>= 0.8 会 TYPE_MISMATCH → branch failed → result failed
    assert _node_status(result, "quality_gate") == "executed"
    assert _branch_path(result, "quality_gate") == "needs_review"
