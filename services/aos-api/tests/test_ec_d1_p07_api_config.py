"""D1 Phase D · W1: P07 Shipment 真实 API 配置创建测试。

验证 wave_ext.PipelineIn 扩展字段 nodes/edges/config 经 POST /v1/pipelines
创建后能完整持久化到 _pipelines 内存字典（并经 _persist_safe 序列化到
meta_pipeline.props JSONB），并能被 GET /v1/pipelines 列表端点读回。

P07 Shipment 配置规格（frozen/02）：
- id: ec-p07-shipment, sourceId: niushop-shipment, objectTypeHint: Shipment
- config.target_ot: Shipment
- 4 节点：source / normalize / validate / quality_gate
- 3 边：source→normalize→validate→quality_gate
- normalize 节点 mask_fields: ["delivery_no"]（物流号遮罩）
- quality_gate 节点 derived_metrics: ["overdue_hours"]
- 派生指标：overdue_hours（SLA=48h，未发货+已支付时计算）

测试覆盖 6 项：
1. POST /v1/pipelines 创建 → 200 + item.nodes 非空
2. GET /v1/pipelines 列表过滤 → nodes/edges/config 持久化
3. Source 节点 config 完整性（source_id/source_table/source_filter/primary_key）
4. pipeline.config.target_ot == "Shipment"
5. ec_live_executor 读取配置执行不抛异常（mock fetch_source_rows 返回空）
6. overdue_hours 写入 properties（mock fetch_source_rows 返回带 pay_time 的 row + patch _now_utc）

mock 策略：
- HTTP: conftest 的 client + auth_headers（Bearer dev + dev-org/dev-project）
- ec_live_executor: mock fetch_source_rows 返回测试 row（避免 MySQL）
                   mock build_link_rows 透传（ships Link 由 W3 构造，本测试只验证 overdue_hours）
                   mock data_os_store.persist_dataset/history 为 no-op
- overdue_hours: patch aos_api.ec_derived_metrics._now_utc 固定时间让断言确定
- pipeline id 用 uuid 后缀避免 _pipelines 全局字典跨测试污染
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aos_api import data_os_store
from aos_api.ec_live_executor import ec_live_executor
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")
# 固定 now：pay_time 在 now 前 72h，SLA=48h → overdue_hours = (72-48)/1 = 24.0
FIXED_NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


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
# 配置工厂（来自 frozen/02 P07 规格）
# ═══════════════════════════════════════════════


def _p07_payload(*, pid: str = "ec-p07-shipment") -> dict:
    """P07 Shipment Pipeline 完整配置（frozen/02）。"""
    return {
        "id": pid,
        "sourceId": "niushop-shipment",
        "name": "P07 Shipment Pipeline",
        "displayName": "栖月汇物流包裹",
        "objectTypeHint": "Shipment",
        "config": {
            "target_ot": "Shipment",
            "source_table": "ns_express_delivery_package",
            "source_filter": "site_id=1",
            "unique_key_template": "niushop:1:{id}",
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": "niushop-shipment",
                    "source_table": "ns_express_delivery_package",
                    "source_filter": "site_id=1",
                    "primary_key": "id",
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {
                    "target_ot": "Shipment",
                    "unique_key_template": "niushop:1:{id}",
                    "zero_time_to_null": True,
                    "mask_fields": ["delivery_no"],
                },
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {"required_fields": ["order_id"]},
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {
                    "target_ot": "Shipment",
                    "derived_metrics": ["overdue_hours"],
                },
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


def _shipment_row(*, pay_time: float | None = None) -> dict:
    """构造 Shipment 源行（denormalized from Order），用于 overdue_hours 计算。

    delivery_time=0（未发货），pay_time 默认在 FIXED_NOW 前 72h（已支付）。
    SLA=48h → overdue_hours = (72-48)/1 = 24.0
    """
    if pay_time is None:
        pay_time = (FIXED_NOW - timedelta(hours=72)).timestamp()
    return {
        "ot": "Shipment",
        "source_pk": "1",
        "source_updated_at": FIXED_NOW,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "orderId": "ord-1",
            "status": "pending",
            "carrier": "SF",
            "trackingNo": "SF1234567890",
        },
        # 源字段（denormalized from Order，用于 overdue_hours 计算）
        "delivery_time": 0,
        "pay_time": pay_time,
    }


# ═══════════════════════════════════════════════
# 1. POST /v1/pipelines 创建 → 200 + item.nodes 非空
# ═══════════════════════════════════════════════


def test_p07_api_create_pipeline_returns_200_with_nodes(client, auth_headers):
    """POST /v1/pipelines 创建 P07 Pipeline（含 nodes/edges/config）→ 200 + nodes 非空。"""
    pid = f"ec-p07-shipment-{uuid.uuid4().hex[:8]}"
    item = _create_pipeline_via_api(client, auth_headers, _p07_payload(pid=pid))

    assert item["id"] == pid
    assert item["sourceId"] == "niushop-shipment"
    assert item["objectTypeHint"] == "Shipment"
    assert item["displayName"] == "栖月汇物流包裹"
    # nodes 完整持久化（4 节点）
    assert isinstance(item.get("nodes"), list)
    assert len(item["nodes"]) == 4
    # edges 完整持久化（3 边）
    assert isinstance(item.get("edges"), list)
    assert len(item["edges"]) == 3
    # config 持久化
    assert isinstance(item.get("config"), dict)
    assert item["config"].get("target_ot") == "Shipment"


# ═══════════════════════════════════════════════
# 2. GET /v1/pipelines 列表过滤 → nodes/edges/config 持久化
# ═══════════════════════════════════════════════


def test_p07_api_list_pipeline_persists_nodes_edges_config(client, auth_headers):
    """GET /v1/pipelines 列表过滤验证 nodes/edges/config 持久化。"""
    pid = f"ec-p07-shipment-{uuid.uuid4().hex[:8]}"
    _create_pipeline_via_api(client, auth_headers, _p07_payload(pid=pid))

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
    assert item["config"]["target_ot"] == "Shipment"
    assert item["config"]["source_table"] == "ns_express_delivery_package"
    assert item["config"]["source_filter"] == "site_id=1"
    assert item["config"]["unique_key_template"] == "niushop:1:{id}"
    # P07 专有：normalize 节点 mask_fields 持久化
    normalize_node = next(n for n in item["nodes"] if n["id"] == "normalize")
    assert normalize_node["config"]["mask_fields"] == ["delivery_no"]
    # P07 专有：quality_gate 节点 derived_metrics 持久化
    qg_node = next(n for n in item["nodes"] if n["id"] == "quality_gate")
    assert qg_node["config"]["derived_metrics"] == ["overdue_hours"]


# ═══════════════════════════════════════════════
# 3. Source 节点 config 完整性
# ═══════════════════════════════════════════════


def test_p07_source_node_config_complete(client, auth_headers):
    """Source 节点 config 包含 source_id/source_table/source_filter/primary_key。"""
    pid = f"ec-p07-shipment-{uuid.uuid4().hex[:8]}"
    item = _create_pipeline_via_api(client, auth_headers, _p07_payload(pid=pid))

    source_node = next(n for n in item["nodes"] if n["id"] == "source")
    src_cfg = source_node["config"]
    assert src_cfg["source_id"] == "niushop-shipment"
    assert src_cfg["source_table"] == "ns_express_delivery_package"
    assert src_cfg["source_filter"] == "site_id=1"
    assert src_cfg["primary_key"] == "id"


# ═══════════════════════════════════════════════
# 4. pipeline.config.target_ot == "Shipment"
# ═══════════════════════════════════════════════


def test_p07_pipeline_config_target_ot_is_shipment(client, auth_headers):
    """pipeline.config.target_ot == "Shipment"。"""
    pid = f"ec-p07-shipment-{uuid.uuid4().hex[:8]}"
    item = _create_pipeline_via_api(client, auth_headers, _p07_payload(pid=pid))

    assert item["config"]["target_ot"] == "Shipment"
    # 同时验证 normalize 节点 config.target_ot 一致
    normalize_node = next(n for n in item["nodes"] if n["id"] == "normalize")
    assert normalize_node["config"]["target_ot"] == "Shipment"
    # quality_gate 节点 config.target_ot 一致
    qg_node = next(n for n in item["nodes"] if n["id"] == "quality_gate")
    assert qg_node["config"]["target_ot"] == "Shipment"


# ═══════════════════════════════════════════════
# 5. ec_live_executor 读取配置执行不抛异常
# ═══════════════════════════════════════════════


def test_p07_ec_live_executor_reads_config_no_error(client, auth_headers):
    """ec_live_executor 读取 mock pipeline（含 config.target_ot）+ nodes 执行不抛异常。

    构造与 API 创建等价的 SimpleNamespace pipeline + nodes list，
    mock fetch_source_rows 返回空（避免 MySQL），验证 executor 不报错。
    """
    pid = f"ec-p07-shipment-{uuid.uuid4().hex[:8]}"
    api_item = _create_pipeline_via_api(client, auth_headers, _p07_payload(pid=pid))

    # 构造与 API item 等价的 mock pipeline 对象（ec_live_executor 读取 pipeline.config.target_ot）
    pipeline = SimpleNamespace(
        id=api_item["id"],
        config=api_item["config"],
        sourceId=api_item["sourceId"],
    )
    nodes = api_item["nodes"]

    # mock fetch_source_rows 返回空（只验证不抛异常）
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
# 6. overdue_hours 写入 properties（P07 专有）
# ═══════════════════════════════════════════════


def test_p07_overdue_hours_written_to_properties(client, auth_headers):
    """派生指标 overdue_hours 写入 row.properties。

    场景：mock fetch_source_rows 返回 Shipment 源行（delivery_time=0 未发货，
    pay_time 在 FIXED_NOW 前 72h 已支付）。ec_derived_metrics.apply_derived_metrics
    按 pipeline.config.target_ot="Shipment" 计算 overdue_hours。

    SLA=48h，pay_time 距 now 72h → overdue_hours = (72-48)/1 = 24.0

    验证：output_rows[0].properties["overdue_hours"] == 24.0
    """
    pid = f"ec-p07-shipment-{uuid.uuid4().hex[:8]}"
    api_item = _create_pipeline_via_api(client, auth_headers, _p07_payload(pid=pid))

    pipeline = SimpleNamespace(
        id=api_item["id"],
        config=api_item["config"],
        sourceId=api_item["sourceId"],
    )
    nodes = api_item["nodes"]

    # patch _now_utc 固定时间，让 overdue_hours 断言确定
    with patch("aos_api.ec_derived_metrics._now_utc", return_value=FIXED_NOW), patch(
        "aos_api.ec_live_executor.fetch_source_rows",
        return_value=[_shipment_row()],
    ), patch(
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

    # executor 读取 1 行，输出 1 行
    assert result["rows_read"] == 1
    assert result["rows_written"] == 1
    # overdue_hours 派生指标写入 properties
    out_row = result["output_rows"][0]
    props = out_row.get("properties") or {}
    assert "overdue_hours" in props, f"overdue_hours missing in properties: {props}"
    assert props["overdue_hours"] == 24.0
