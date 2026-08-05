"""D1 Phase D W2: P04 Category 真实 API 配置创建 + DatasetSink 集成验证.

P04 Category 配置规格（frozen/02）:
- 源表/主键: ns_goods_category / category_id
- 源过滤: site_id=1
- 目标 OT: Category
- 唯一键: niushop:1:{category_id}
- 关键校验: pid=0 为根；检测分类环和孤儿父级
- Link: inCategory: Product → Category（多分类字符串需先定义拆分契约）

测试覆盖 8 项:
1. POST /v1/pipelines 创建配置（含 nodes/edges/config）
2. GET /v1/pipelines 查询验证 nodes 持久化
3. nodes 配置完整性：Source 节点 source_table
4. config.target_ot 正确
5. ec_live_executor 能读取配置执行（不报错）
6. DatasetSink 集成验证：sink_to_dataset 被调用，output_ref 格式正确
7. 分类环检测：validate 节点 cycle_detection 配置
8. inCategory 拆分契约：quality_gate link_rules.inCategory 配置
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from aos_api import data_os_store
from aos_api.ec_live_executor import ec_live_executor
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope


TEST_SCOPE = TenantScope("dev-org", "dev-project")

# P04 Category 配置（frozen/02）
P04_PIPELINE_PAYLOAD: dict[str, Any] = {
    "id": "ec-p04-category",
    "sourceId": "niushop-category",
    "name": "P04 Category Pipeline",
    "displayName": "栖月汇商品分类",
    "objectTypeHint": "Category",
    "target": "dataset",
    "config": {
        "target_ot": "Category",
        "source_table": "ns_goods_category",
        "source_filter": "site_id=1",
        "unique_key_template": "niushop:1:{category_id}",
    },
    "nodes": [
        {
            "id": "source",
            "name": "Source",
            "type": "source",
            "config": {
                "source_id": "niushop-category",
                "source_table": "ns_goods_category",
                "source_filter": "site_id=1",
                "primary_key": "category_id",
            },
        },
        {
            "id": "normalize",
            "name": "Normalize",
            "type": "transform",
            "config": {
                "target_ot": "Category",
                "unique_key_template": "niushop:1:{category_id}",
            },
        },
        {
            "id": "validate",
            "name": "Validate",
            "type": "gate",
            "config": {
                "required_fields": ["category_name"],
                "cycle_detection": True,
                "orphan_parent_detection": True,
            },
        },
        {
            "id": "quality_gate",
            "name": "QualityGate",
            "type": "gate",
            "config": {
                "target_ot": "Category",
                "link_rules": {"inCategory": "split by comma"},
            },
        },
    ],
    "edges": [
        {"source": "source", "target": "normalize"},
        {"source": "normalize", "target": "validate"},
        {"source": "validate", "target": "quality_gate"},
    ],
}


def _stub_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    """避免持久化副作用污染 PG（与 test_ec_d1_p04_category.py 模式一致）."""
    monkeypatch.setattr(data_os_store, "persist_dataset", lambda *a, **kw: None)
    monkeypatch.setattr(data_os_store, "persist_dataset_history", lambda *a, **kw: None)


def _create_source(client, auth_headers) -> None:
    """先创建 source（PipelineIn.sourceId 引用，wave_ext.create_pipeline 不强制校验存在，
    但创建以模拟真实接线）."""
    r = client.post(
        "/v1/sources",
        headers=auth_headers,
        json={"id": "niushop-category", "type": "file"},
    )
    assert r.status_code == 200, r.text


def _create_p04_pipeline(client, auth_headers) -> dict[str, Any]:
    """创建 P04 pipeline，返回 response body."""
    _create_source(client, auth_headers)
    r = client.post(
        "/v1/pipelines",
        headers=auth_headers,
        json=P04_PIPELINE_PAYLOAD,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _build_mock_pipeline_and_nodes() -> tuple[SimpleNamespace, list[SimpleNamespace]]:
    """构造 mock pipeline + nodes（保留 P04 配置），供 ec_live_executor 调用."""
    pipeline = SimpleNamespace(
        id="ec-p04-category",
        config=P04_PIPELINE_PAYLOAD["config"],
    )
    nodes = [SimpleNamespace(**n) for n in P04_PIPELINE_PAYLOAD["nodes"]]
    return pipeline, nodes


# ═══════════════════════════════════════════════
# 1. POST /v1/pipelines 创建配置
# ═══════════════════════════════════════════════


def test_post_pipeline_creates_p04_config(client, auth_headers):
    """POST /v1/pipelines 创建 P04 Pipeline（含 nodes/edges/config）."""
    body = _create_p04_pipeline(client, auth_headers)
    assert body["id"] == "ec-p04-category"
    assert body["sourceId"] == "niushop-category"
    assert body["objectTypeHint"] == "Category"
    assert body["displayName"] == "栖月汇商品分类"
    # nodes/edges/config 三个新字段都持久化
    assert len(body["nodes"]) == 4
    assert len(body["edges"]) == 3
    assert body["config"]["target_ot"] == "Category"
    # 自动创建 dataset（wave_ext.create_pipeline 副作用）
    assert body["datasetRid"].startswith("ri.dataset.")


# ═══════════════════════════════════════════════
# 2. GET /v1/pipelines 查询验证 nodes 持久化
# ═══════════════════════════════════════════════


def test_get_pipelines_returns_p04_with_nodes(client, auth_headers):
    """GET /v1/pipelines 返回 P04，nodes 完整持久化."""
    _create_p04_pipeline(client, auth_headers)
    r = client.get("/v1/pipelines", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    p04 = next((p for p in items if p["id"] == "ec-p04-category"), None)
    assert p04 is not None, "P04 pipeline not found in list"
    assert len(p04["nodes"]) == 4
    node_ids = [n["id"] for n in p04["nodes"]]
    assert node_ids == ["source", "normalize", "validate", "quality_gate"]
    # edges 也持久化
    assert len(p04["edges"]) == 3


# ═══════════════════════════════════════════════
# 3. nodes 配置完整性：Source 节点 source_table
# ═══════════════════════════════════════════════


def test_source_node_config_contains_source_table(client, auth_headers):
    """Source 节点 config 含 source_table='ns_goods_category'."""
    body = _create_p04_pipeline(client, auth_headers)
    source_node = next(n for n in body["nodes"] if n["id"] == "source")
    assert source_node["config"]["source_table"] == "ns_goods_category"
    assert source_node["config"]["source_filter"] == "site_id=1"
    assert source_node["config"]["primary_key"] == "category_id"
    assert source_node["config"]["source_id"] == "niushop-category"


# ═══════════════════════════════════════════════
# 4. config.target_ot 正确
# ═══════════════════════════════════════════════


def test_pipeline_config_target_ot_is_category(client, auth_headers):
    """pipeline.config.target_ot == 'Category'."""
    body = _create_p04_pipeline(client, auth_headers)
    assert body["config"]["target_ot"] == "Category"
    assert body["config"]["source_table"] == "ns_goods_category"
    assert body["config"]["source_filter"] == "site_id=1"
    assert body["config"]["unique_key_template"] == "niushop:1:{category_id}"


# ═══════════════════════════════════════════════
# 5. ec_live_executor 能读取配置执行
# ═══════════════════════════════════════════════


def test_ec_live_executor_runs_with_p04_config(monkeypatch):
    """ec_live_executor 接收 P04 mock pipeline + nodes，不报错.

    mock fetch_source_rows（W1 实现，避免真实 MySQL 连接）
    mock sink_to_ot（W3 实现，避免 BatchCommand 校验依赖 store）
    保留真实 sink_to_dataset（W2 实现，验证 DatasetSink 集成）
    """
    _stub_persist(monkeypatch)
    eng = get_engine()
    eng.reset_all_for_tests()

    pipeline, nodes = _build_mock_pipeline_and_nodes()

    sample_rows = [
        {"category_id": "1", "category_name": "根分类", "pid": 0, "site_id": 1},
        {"category_id": "2", "category_name": "子分类A", "pid": 1, "site_id": 1},
    ]
    monkeypatch.setattr(
        "aos_api.ec_live_executor.fetch_source_rows",
        lambda **kw: sample_rows,
    )
    monkeypatch.setattr(
        "aos_api.ec_live_executor.sink_to_ot",
        lambda *a, **kw: {"objects_written": 2, "links_written": 0},
    )

    result = ec_live_executor(
        pipeline=pipeline,
        nodes=nodes,
        node_id="source",
        sample_input=sample_rows,
        execution_kind="trial",
        cancel_event=None,
        deadline=9999.0,
        scope=TEST_SCOPE,
    )

    assert result["rows_read"] == 2
    assert result["rows_written"] == 2
    assert result["output_ref"].startswith("dataset://catalog/")
    eng.reset_all_for_tests()


# ═══════════════════════════════════════════════
# 6. DatasetSink 集成验证：sink_to_dataset 被调用 + output_ref 格式
# ═══════════════════════════════════════════════


def test_dataset_sink_called_and_output_ref_format(monkeypatch):
    """ec_live_executor 调用 sink_to_dataset，output_ref 格式 dataset://catalog/<rid>."""
    _stub_persist(monkeypatch)
    eng = get_engine()
    eng.reset_all_for_tests()

    pipeline, nodes = _build_mock_pipeline_and_nodes()

    sample_rows = [
        {"category_id": "1", "category_name": "根分类", "pid": 0, "site_id": 1},
    ]
    monkeypatch.setattr(
        "aos_api.ec_live_executor.fetch_source_rows",
        lambda **kw: sample_rows,
    )
    monkeypatch.setattr(
        "aos_api.ec_live_executor.sink_to_ot",
        lambda *a, **kw: {"objects_written": 1, "links_written": 0},
    )

    # spy sink_to_dataset 验证被调用
    from aos_api import ec_live_executor as exec_mod

    calls: list[tuple[Any, Any, Any, Any]] = []
    real_sink = exec_mod.sink_to_dataset

    def _spy(eng_, scope, pipeline_, rows):
        calls.append((eng_, scope, pipeline_, rows))
        return real_sink(eng_, scope, pipeline_, rows)

    monkeypatch.setattr(exec_mod, "sink_to_dataset", _spy)

    result = ec_live_executor(
        pipeline=pipeline,
        nodes=nodes,
        node_id="source",
        sample_input=sample_rows,
        execution_kind="trial",
        cancel_event=None,
        deadline=9999.0,
        scope=TEST_SCOPE,
    )

    # sink_to_dataset 被调用一次，rows 为 sample_rows
    assert len(calls) == 1
    assert calls[0][3] == sample_rows
    # output_ref 格式：dataset://catalog/<rid>
    assert result["output_ref"].startswith("dataset://catalog/ri.dataset.")
    eng.reset_all_for_tests()


# ═══════════════════════════════════════════════
# 7. 分类环检测：validate 节点 cycle_detection
# ═══════════════════════════════════════════════


def test_validate_node_cycle_detection_config(client, auth_headers):
    """validate 节点 config 含 cycle_detection=True（P04 关键校验）."""
    body = _create_p04_pipeline(client, auth_headers)
    validate_node = next(n for n in body["nodes"] if n["id"] == "validate")
    assert validate_node["config"]["cycle_detection"] is True
    assert validate_node["config"]["orphan_parent_detection"] is True
    assert "category_name" in validate_node["config"]["required_fields"]


# ═══════════════════════════════════════════════
# 8. inCategory 拆分契约：quality_gate link_rules.inCategory
# ═══════════════════════════════════════════════


def test_quality_gate_incategory_split_contract(client, auth_headers):
    """quality_gate 节点 config.link_rules.inCategory == 'split by comma'."""
    body = _create_p04_pipeline(client, auth_headers)
    qg = next(n for n in body["nodes"] if n["id"] == "quality_gate")
    assert qg["config"]["link_rules"]["inCategory"] == "split by comma"
    assert qg["config"]["target_ot"] == "Category"
