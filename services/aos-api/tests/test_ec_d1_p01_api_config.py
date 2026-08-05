"""D1 Phase D · W1: P01 Shop 真实 API 配置创建测试。

验证 wave_ext.PipelineIn 扩展字段 nodes/edges/config 经 POST /v1/pipelines
创建后能完整持久化到 _pipelines 内存字典（并经 _persist_safe 序列化到
meta_pipeline.props JSONB），并能被 GET /v1/pipelines 列表端点读回。

P01 Shop 配置规格（frozen/02）：
- id: ec-p01-shop, sourceId: niushop-shop, objectTypeHint: Shop
- config.target_ot: Shop
- 4 节点：source / normalize / validate / quality_gate
- 3 边：source→normalize→validate→quality_gate

测试覆盖 6 项：
1. POST /v1/pipelines 创建 → 200 + item.nodes 非空
2. GET /v1/pipelines 列表过滤 → nodes/edges/config 持久化
3. Source 节点 config 完整性（source_id/source_table/source_filter/primary_key）
4. pipeline.config.target_ot == "Shop"
5. ec_live_executor 读取配置执行不抛异常（mock fetch_source_rows 返回空）
6. edges 拓扑完整（3 条边串联 4 节点）

mock 策略：
- HTTP: conftest 的 client + auth_headers（Bearer dev + dev-org/dev-project）
- ec_live_executor: mock fetch_source_rows 返回 []（避免 MySQL）
                   mock build_link_rows 透传（P01 无 Link）
                   mock data_os_store.persist_dataset/history 为 no-op
- pipeline id 用 uuid 后缀避免 _pipelines 全局字典跨测试污染
"""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aos_api import data_os_store
from aos_api.ec_live_executor import ec_live_executor
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")


# ═══════════════════════════════════════════════
# fixtures
# ═══════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_engine():
    eng = get_engine()
    eng.reset_all_for_tests()
    yield
    eng.reset_all_for_tests()


@pytest.fixture(autouse=True)
def _mock_data_os_store():
    """避免 persist_dataset / persist_dataset_history 打 DB。

    注：persist_pipeline 仍走真实路径（meta_pipeline UPSERT），
    验证 nodes/edges/config 序列化到 props JSONB。
    """
    monkey = pytest.MonkeyPatch()
    monkey.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkey.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)
    yield
    monkey.undo()


# ═══════════════════════════════════════════════
# 配置工厂（来自 frozen/02 P01 规格）
# ═══════════════════════════════════════════════


def _p01_payload(*, pid: str = "ec-p01-shop") -> dict:
    """P01 Shop Pipeline 完整配置（frozen/02）。"""
    return {
        "id": pid,
        "sourceId": "niushop-shop",
        "name": "P01 Shop Pipeline",
        "displayName": "栖月汇店铺信息",
        "objectTypeHint": "Shop",
        "config": {
            "target_ot": "Shop",
            "source_table": "ns_site",
            "source_filter": "site_id=1",
            "unique_key_template": "niushop:1:{site_id}",
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": "niushop-shop",
                    "source_table": "ns_site",
                    "source_filter": "site_id=1",
                    "primary_key": "site_id",
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {
                    "target_ot": "Shop",
                    "unique_key_template": "niushop:1:{site_id}",
                    "zero_time_to_null": True,
                },
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {"required_fields": ["site_name"]},
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {"target_ot": "Shop"},
            },
        ],
        "edges": [
            {"source": "source", "target": "normalize"},
            {"source": "normalize", "target": "validate"},
            {"source": "validate", "target": "quality_gate"},
        ],
    }


def _create_pipeline_via_api(client, auth_headers, payload: dict) -> dict:
    """POST /v1/pipelines 创建并返回 item。"""
    resp = client.post("/v1/pipelines", json=payload, headers=auth_headers)
    assert resp.status_code == 200, f"create failed: {resp.status_code} {resp.text}"
    return resp.json()


def _list_and_find(client, auth_headers, pid: str) -> dict:
    """GET /v1/pipelines 列表端点过滤出指定 id 的 pipeline。

    wave_ext 没有 GET /v1/pipelines/{id} 裸路径（object_storage_indexing 的同名
    路由有 /object-storage-indexing prefix，返回 StreamPipeline，与 EC pipeline
    存储隔离）。改用 list 端点过滤验证持久化。
    """
    resp = client.get("/v1/pipelines", headers=auth_headers)
    assert resp.status_code == 200, f"list failed: {resp.status_code} {resp.text}"
    items = resp.json().get("items") or []
    for item in items:
        if item.get("id") == pid:
            return item
    pytest.fail(f"pipeline {pid} not found in list response")


# ═══════════════════════════════════════════════
# 1. POST /v1/pipelines 创建 → 200 + item.nodes 非空
# ═══════════════════════════════════════════════


def test_p01_api_create_pipeline_returns_200_with_nodes(client, auth_headers):
    """POST /v1/pipelines 创建 P01 Pipeline（含 nodes/edges/config）→ 200 + nodes 非空。"""
    pid = f"ec-p01-shop-{uuid.uuid4().hex[:8]}"
    item = _create_pipeline_via_api(client, auth_headers, _p01_payload(pid=pid))

    assert item["id"] == pid
    assert item["sourceId"] == "niushop-shop"
    assert item["objectTypeHint"] == "Shop"
    assert item["displayName"] == "栖月汇店铺信息"
    # nodes 完整持久化（4 节点）
    assert isinstance(item.get("nodes"), list)
    assert len(item["nodes"]) == 4
    # edges 完整持久化（3 边）
    assert isinstance(item.get("edges"), list)
    assert len(item["edges"]) == 3
    # config 持久化
    assert isinstance(item.get("config"), dict)
    assert item["config"].get("target_ot") == "Shop"


# ═══════════════════════════════════════════════
# 2. GET /v1/pipelines 列表过滤 → nodes/edges/config 持久化
# ═══════════════════════════════════════════════


def test_p01_api_list_pipeline_persists_nodes_edges_config(client, auth_headers):
    """GET /v1/pipelines 列表过滤验证 nodes/edges/config 持久化。"""
    pid = f"ec-p01-shop-{uuid.uuid4().hex[:8]}"
    _create_pipeline_via_api(client, auth_headers, _p01_payload(pid=pid))

    item = _list_and_find(client, auth_headers, pid)

    # nodes 持久化：4 节点 id 集合一致
    node_ids = {n["id"] for n in item["nodes"]}
    assert node_ids == {"source", "normalize", "validate", "quality_gate"}
    # edges 持久化：3 条边的 (source, target) 对
    edge_pairs = {(e["source"], e["target"]) for e in item["edges"]}
    assert edge_pairs == {
        ("source", "normalize"),
        ("normalize", "validate"),
        ("validate", "quality_gate"),
    }
    # config 持久化
    assert item["config"]["target_ot"] == "Shop"
    assert item["config"]["source_table"] == "ns_site"
    assert item["config"]["source_filter"] == "site_id=1"
    assert item["config"]["unique_key_template"] == "niushop:1:{site_id}"


# ═══════════════════════════════════════════════
# 3. Source 节点 config 完整性
# ═══════════════════════════════════════════════


def test_p01_source_node_config_complete(client, auth_headers):
    """Source 节点 config 包含 source_id/source_table/source_filter/primary_key。"""
    pid = f"ec-p01-shop-{uuid.uuid4().hex[:8]}"
    item = _create_pipeline_via_api(client, auth_headers, _p01_payload(pid=pid))

    source_node = next(n for n in item["nodes"] if n["id"] == "source")
    src_cfg = source_node["config"]
    assert src_cfg["source_id"] == "niushop-shop"
    assert src_cfg["source_table"] == "ns_site"
    assert src_cfg["source_filter"] == "site_id=1"
    assert src_cfg["primary_key"] == "site_id"


# ═══════════════════════════════════════════════
# 4. pipeline.config.target_ot == "Shop"
# ═══════════════════════════════════════════════


def test_p01_pipeline_config_target_ot_is_shop(client, auth_headers):
    """pipeline.config.target_ot == "Shop"。"""
    pid = f"ec-p01-shop-{uuid.uuid4().hex[:8]}"
    item = _create_pipeline_via_api(client, auth_headers, _p01_payload(pid=pid))

    assert item["config"]["target_ot"] == "Shop"
    # 同时验证 normalize 节点 config.target_ot 一致
    normalize_node = next(n for n in item["nodes"] if n["id"] == "normalize")
    assert normalize_node["config"]["target_ot"] == "Shop"
    # quality_gate 节点 config.target_ot 一致
    qg_node = next(n for n in item["nodes"] if n["id"] == "quality_gate")
    assert qg_node["config"]["target_ot"] == "Shop"


# ═══════════════════════════════════════════════
# 5. ec_live_executor 读取配置执行不抛异常
# ═══════════════════════════════════════════════


def test_p01_ec_live_executor_reads_config_no_error(client, auth_headers):
    """ec_live_executor 读取 mock pipeline（含 config.target_ot）+ nodes 执行不抛异常。

    构造与 API 创建等价的 SimpleNamespace pipeline + nodes list，
    mock fetch_source_rows 返回空（避免 MySQL），验证 executor 不报错。
    """
    pid = f"ec-p01-shop-{uuid.uuid4().hex[:8]}"
    api_item = _create_pipeline_via_api(client, auth_headers, _p01_payload(pid=pid))

    # 构造与 API item 等价的 mock pipeline 对象（ec_live_executor 读取 pipeline.config.target_ot）
    pipeline = SimpleNamespace(
        id=api_item["id"],
        config=api_item["config"],
        sourceId=api_item["sourceId"],
    )
    # nodes 透传给 ec_live_executor（本测试 mock fetch_source_rows，nodes 不实际使用）
    nodes = api_item["nodes"]

    # mock fetch_source_rows 返回空（P01 Shop 无 mock row；只验证不抛异常）
    with patch(
        "aos_api.ec_live_executor.fetch_source_rows", return_value=[]
    ) as mock_fetch, patch(
        "aos_api.ec_live_executor.build_link_rows",
        side_effect=lambda rows, pipeline: rows,
    ):
        result = ec_live_executor(
            pipeline=pipeline,
            nodes=nodes,
            node_id="source",
            sample_input=None,
            execution_kind="initial",
            cancel_event=None,
            deadline=time.time() + 30,
            scope=TEST_SCOPE,
        )

    # fetch_source_rows 被调用（executor 真实走了 source 分支）
    assert mock_fetch.called
    # 输出引用以 dataset://catalog/ 开头
    assert result["output_ref"].startswith("dataset://catalog/")
    # 空 input → 0 行
    assert result["rows_read"] == 0
    assert result["rows_written"] == 0


# ═══════════════════════════════════════════════
# 6. edges 拓扑完整（3 条边串联 4 节点）
# ═══════════════════════════════════════════════


def test_p01_edges_topology_complete(client, auth_headers):
    """edges 拓扑完整：source→normalize→validate→quality_gate 单链 3 边。

    验证：
    - 4 节点 3 边
    - 边的 source/target 都引用存在的 node id
    - 形成 source 到 quality_gate 的单链（无环、无分叉）
    """
    pid = f"ec-p01-shop-{uuid.uuid4().hex[:8]}"
    item = _create_pipeline_via_api(client, auth_headers, _p01_payload(pid=pid))

    nodes = item["nodes"]
    edges = item["edges"]

    node_ids = {n["id"] for n in nodes}
    assert len(nodes) == 4
    assert len(edges) == 3

    # 所有边的 source/target 都引用存在的 node id
    for edge in edges:
        assert edge["source"] in node_ids, f"edge source {edge['source']} not in nodes"
        assert edge["target"] in node_ids, f"edge target {edge['target']} not in nodes"

    # 单链验证：source 出度=1 入度=0；quality_gate 入度=1 出度=0；中间节点入度=出度=1
    in_degree = {nid: 0 for nid in node_ids}
    out_degree = {nid: 0 for nid in node_ids}
    for edge in edges:
        out_degree[edge["source"]] += 1
        in_degree[edge["target"]] += 1

    assert in_degree["source"] == 0 and out_degree["source"] == 1
    assert in_degree["normalize"] == 1 and out_degree["normalize"] == 1
    assert in_degree["validate"] == 1 and out_degree["validate"] == 1
    assert in_degree["quality_gate"] == 1 and out_degree["quality_gate"] == 0
