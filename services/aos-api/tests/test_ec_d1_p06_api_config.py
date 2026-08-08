"""D1-W4: P06 OrderLine 真实 API 配置创建 + 负向验证（Phase D）。

P06 OrderLine 配置规格（frozen/02）：
- id: ec-p06-orderline
- sourceId: niushop-orderline
- displayName: 栖月汇订单明细
- objectTypeHint: OrderLine
- config.target_ot: OrderLine
- nodes: source / normalize / validate / quality_gate
- edges: source → normalize → validate → quality_gate

测试覆盖（10 项）：
1. POST /v1/pipelines 创建配置（含 nodes/edges/config）
2. GET /v1/pipelines 查询验证 nodes 持久化
3. Source 节点 config 含 cursor_fields（refund_action_time + order_goods_id）
4. pipeline.config.target_ot == "OrderLine"
5. ec_live_executor 能读取配置执行
6. quality_gate.config.link_rules.contains 正确
7. quality_gate.config.link_rules.forProduct 正确
8. quality_gate.config.link_rules.forSku 含 skip_if=0
9. 游标修正：cursor_fields 用 refund_action_time 而非 create_time
10. 负向：跨租户创建同 pipeline_id 被拒绝（409 TENANT_SCOPE_CONFLICT）

约束：
- 用 TestClient + auth_headers（dev-org/dev-project）走真实 HTTP 路由
- pipeline_id 用 uuid 后缀避免跨测试污染 _pipelines 全局状态
- ec_live_executor 调用 mock 下游，验证 executor 顺利执行
- 跨租户测试用 other-org header 模拟
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from aos_api import ec_live_executor as ec_mod
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope


# ═══════════════════════════════════════════════
# P06 OrderLine 配置（frozen/02）
# ═══════════════════════════════════════════════


def _p06_payload(pid: str, sid: str) -> dict[str, Any]:
    """构造 P06 pipeline 创建 payload（含 nodes/edges/config）。"""
    return {
        "id": pid,
        "sourceId": sid,
        "name": "P06 OrderLine Pipeline",
        "displayName": "栖月汇订单明细",
        "objectTypeHint": "OrderLine",
        "config": {
            "target_ot": "OrderLine",
            "source_table": "ns_order_goods",
            "source_filter": "site_id=1",
            "unique_key_template": "niushop:1:{order_goods_id}",
            "cursor_fields": ["refund_action_time", "order_goods_id"],
            "cursor_note": "create_time=0 for 227 rows, fallback to refund_action_time",
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": "niushop-orderline",
                    "source_table": "ns_order_goods",
                    "source_filter": "site_id=1",
                    "primary_key": "order_goods_id",
                    "cursor_fields": ["refund_action_time", "order_goods_id"],
                    "cursor_note": "create_time=0 for 227 rows, fallback to refund_action_time",
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {
                    "target_ot": "OrderLine",
                    "unique_key_template": "niushop:1:{order_goods_id}",
                    "zero_time_to_null": True,
                    "decimal_fields": ["num", "price", "goods_money"],
                    "enum_fields": {"refund_status": [-3, 0, 3]},
                },
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {
                    "required_fields": ["order_id", "goods_id"],
                },
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {
                    "target_ot": "OrderLine",
                    "link_rules": {
                        "contains": "source=order_id, target=order_goods_id",
                        "forProduct": "source=order_goods_id, target=goods_id",
                        "forSku": "source=order_goods_id, target=sku_id, skip_if=0",
                    },
                },
            },
        ],
        "edges": [
            {"source": "source", "target": "normalize"},
            {"source": "normalize", "target": "validate"},
            {"source": "validate", "target": "quality_gate"},
        ],
    }


# ═══════════════════════════════════════════════
# fixtures
# ═══════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield
    eng.reset_all_for_tests()


@pytest.fixture()
def p06_pipeline(client, auth_headers):
    """创建 P06 pipeline，返回 pipeline dict。"""
    pid = f"ec-p06-orderline-{uuid.uuid4().hex[:8]}"
    sid = f"niushop-orderline-{pid}"
    r_src = client.post(
        "/v1/sources", headers=auth_headers, json={"id": sid, "type": "file"}
    )
    assert r_src.status_code == 200, r_src.text
    r = client.post(
        "/v1/pipelines", headers=auth_headers, json=_p06_payload(pid, sid)
    )
    assert r.status_code == 200, r.text
    return r.json()


def _find_node(pipeline: dict[str, Any], node_id: str) -> dict[str, Any]:
    """从 pipeline.nodes 中找到指定 id 的节点。"""
    for n in pipeline.get("nodes") or []:
        if n.get("id") == node_id:
            return n
    raise AssertionError(f"node {node_id} not found in pipeline.nodes")


# ═══════════════════════════════════════════════
# 测试（10 项）
# ═══════════════════════════════════════════════


def test_p06_create_pipeline_via_api(p06_pipeline):
    """#1 POST /v1/pipelines 创建配置（含 nodes/edges/config）。"""
    assert p06_pipeline["id"].startswith("ec-p06-orderline-")
    assert p06_pipeline["displayName"] == "栖月汇订单明细"
    assert p06_pipeline["objectTypeHint"] == "OrderLine"
    assert p06_pipeline["sourceId"].startswith("niushop-orderline-")
    # nodes/edges/config 持久化（回显）
    assert len(p06_pipeline["nodes"]) == 4
    assert len(p06_pipeline["edges"]) == 3
    assert p06_pipeline["config"]["target_ot"] == "OrderLine"
    # datasetRid 自动生成
    assert p06_pipeline["datasetRid"].startswith("ri.dataset.")


def test_p06_get_pipeline_persists_nodes(client, auth_headers, p06_pipeline):
    """#2 GET /v1/pipelines 查询验证 nodes 持久化。"""
    r = client.get("/v1/pipelines", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    matched = [p for p in items if p["id"] == p06_pipeline["id"]]
    assert len(matched) == 1
    got = matched[0]
    # nodes 完整持久化（4 个节点）
    assert len(got.get("nodes") or []) == 4
    node_ids = {n["id"] for n in got["nodes"]}
    assert node_ids == {"source", "normalize", "validate", "quality_gate"}
    # edges 持久化
    assert len(got.get("edges") or []) == 3


def test_p06_source_node_has_cursor_fields(p06_pipeline):
    """#3 Source 节点 config 包含 cursor_fields（nodes 配置完整性）。"""
    src = _find_node(p06_pipeline, "source")
    cfg = src["config"]
    assert cfg["source_id"] == "niushop-orderline"
    assert cfg["source_table"] == "ns_order_goods"
    assert cfg["primary_key"] == "order_goods_id"
    # cursor_fields 完整（refund_action_time + order_goods_id）
    assert cfg["cursor_fields"] == ["refund_action_time", "order_goods_id"]


def test_p06_config_target_ot_is_orderline(p06_pipeline):
    """#4 pipeline.config.target_ot 正确（OrderLine）。"""
    cfg = p06_pipeline["config"]
    assert cfg["target_ot"] == "OrderLine"
    assert cfg["source_table"] == "ns_order_goods"
    assert cfg["unique_key_template"] == "niushop:1:{order_goods_id}"
    # cursor_note 说明游标修正原因
    assert "refund_action_time" in cfg["cursor_note"]


def test_p06_ec_live_executor_reads_config(p06_pipeline, monkeypatch):
    """#5 ec_live_executor 能读取配置执行（mock 下游，验证 executor 顺利返回）。"""
    fake_row = {
        "ot": "OrderLine",
        "source_pk": "200",
        "source_updated_at": "2026-07-31T10:00:00+00:00",
        "source_timezone": "+00:00",
        "properties": {"orderId": "100", "goodsId": "g-1", "skuId": "s-1"},
    }

    # mock 下游：避免连 MySQL/PG，隔离 executor 配置读取
    monkeypatch.setattr(
        ec_mod, "fetch_source_rows", lambda **kw: [fake_row]
    )
    monkeypatch.setattr(ec_mod, "apply_derived_metrics", lambda rows, pipeline, **kw: rows)
    monkeypatch.setattr(ec_mod, "build_link_rows", lambda rows, _: rows)
    monkeypatch.setattr(
        ec_mod,
        "sink_to_dataset",
        lambda *a, **kw: SimpleNamespace(id="ri.dataset.test"),
    )
    monkeypatch.setattr(ec_mod, "sink_to_ot", lambda *a, **kw: None)

    # 构造 pipeline 对象（带 config，让 build_link_rows 等读到 target_ot）
    pipeline = SimpleNamespace(
        id=p06_pipeline["id"], config=p06_pipeline["config"]
    )
    nodes = [
        SimpleNamespace(id=n["id"], config=n["config"])
        for n in p06_pipeline["nodes"]
    ]

    result = ec_mod.ec_live_executor(
        pipeline=pipeline,
        nodes=nodes,
        node_id="source",
        sample_input=None,
        execution_kind="schedule",
        cancel_event=None,
        deadline=0,
        scope=TenantScope("dev-org", "dev-project"),
    )

    # executor 顺利执行，读到 1 行
    assert result["rows_read"] == 1
    assert result["rows_written"] == 1
    assert result["output_ref"].startswith("dataset://catalog/")


def test_p06_link_rules_contains(p06_pipeline):
    """#6 quality_gate.config.link_rules.contains 正确。

    contains: Order → OrderLine（source=order_id, target=order_goods_id）
    """
    qg = _find_node(p06_pipeline, "quality_gate")
    link_rules = qg["config"]["link_rules"]
    assert "contains" in link_rules
    contains = link_rules["contains"]
    assert "source=order_id" in contains
    assert "target=order_goods_id" in contains


def test_p06_link_rules_forproduct(p06_pipeline):
    """#7 quality_gate.config.link_rules.forProduct 正确。

    forProduct: OrderLine → Product（source=order_goods_id, target=goods_id）
    """
    qg = _find_node(p06_pipeline, "quality_gate")
    link_rules = qg["config"]["link_rules"]
    assert "forProduct" in link_rules
    for_product = link_rules["forProduct"]
    assert "source=order_goods_id" in for_product
    assert "target=goods_id" in for_product


def test_p06_link_rules_forsku_skip_if_zero(p06_pipeline):
    """#8 quality_gate.config.link_rules.forSku 含 skip_if=0。

    forSku: OrderLine → ProductSku（source=order_goods_id, target=sku_id, skip_if=0）
    sku_id=0 时跳过 Link 构造（避免 dangling link）。
    """
    qg = _find_node(p06_pipeline, "quality_gate")
    link_rules = qg["config"]["link_rules"]
    assert "forSku" in link_rules
    for_sku = link_rules["forSku"]
    assert "source=order_goods_id" in for_sku
    assert "target=sku_id" in for_sku
    assert "skip_if=0" in for_sku


def test_p06_cursor_uses_refund_action_time(p06_pipeline):
    """#9 游标修正：cursor_fields 用 refund_action_time 而非 create_time。

    差异报告 D-002：ns_order_goods.create_time 227 行全为 0，不可用作游标。
    修正：cursor_fields 改为 [refund_action_time, order_goods_id]。
    """
    # pipeline.config.cursor_fields
    cfg = p06_pipeline["config"]
    cursor_fields = cfg["cursor_fields"]
    assert "refund_action_time" in cursor_fields
    assert "create_time" not in cursor_fields

    # source node config 也保持一致
    src = _find_node(p06_pipeline, "source")
    src_cursor = src["config"]["cursor_fields"]
    assert "refund_action_time" in src_cursor
    assert "create_time" not in src_cursor
    # cursor_note 说明修正原因
    assert "create_time=0" in src["config"]["cursor_note"]


def test_p06_cross_tenant_create_rejected(client, auth_headers):
    """#10 负向：跨租户创建同 pipeline_id 被拒绝（409 TENANT_SCOPE_CONFLICT）。

    场景：
    1. dev-org 创建 pipeline-P（sourceId=src-dev）
    2. other-org 创建同 id pipeline-P（sourceId=src-other，避免 source 跨租户先抛）
    3. _assert_mutation_scope 检测到 _pipelines[P] 属于 dev-org → 抛 TENANT_SCOPE_CONFLICT
    """
    pid = f"ec-p06-cross-{uuid.uuid4().hex[:8]}"
    sid_dev = f"niushop-orderline-dev-{pid}"
    sid_other = f"niushop-orderline-other-{pid}"

    # dev-org 创建 source + pipeline
    r = client.post(
        "/v1/sources", headers=auth_headers, json={"id": sid_dev, "type": "file"}
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/v1/pipelines", headers=auth_headers, json=_p06_payload(pid, sid_dev)
    )
    assert r.status_code == 200, r.text

    # other-org 创建自己的 source（避免 source 跨租户先抛）
    other_headers = {
        **auth_headers,
        "X-Org-Id": "other-org",
        "X-Project-Id": "other-project",
    }
    r = client.post(
        "/v1/sources",
        headers=other_headers,
        json={"id": sid_other, "type": "file"},
    )
    assert r.status_code == 200, r.text

    # other-org 创建同 id pipeline → 409 TENANT_SCOPE_CONFLICT
    r2 = client.post(
        "/v1/pipelines", headers=other_headers, json=_p06_payload(pid, sid_other)
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "TENANT_SCOPE_CONFLICT"
