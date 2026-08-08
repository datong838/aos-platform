"""D1 Phase D W3: P02 Product 真实 API 配置创建 + Link 落地验证测试。

覆盖 8 项（frozen/02 规格）：
1. POST /v1/pipelines 创建配置（含 nodes/edges/config）
2. GET /v1/pipelines 查询验证 nodes 持久化
3. Source 节点 config 含 cursor_fields/cursor_fallback
4. pipeline.config.target_ot 正确（Product）
5. ec_live_executor 能读取 API 配置执行
6. quality_gate.config.derived_metrics 含 "quality_score"
7. quality_gate.config.link_rules.inCategory 配置验证
8. ec_live_executor + build_link_rows 端到端 Link 行追加（mock ec_derived_metrics 透传）

注：
- wave_ext.py 没有 GET /v1/pipelines/{id} 单点端点（object_storage_indexing.py
  拦截该路径走 StreamIndexEngine，不同存储）。使用 GET /v1/pipelines 列表过滤 id 验证。
- ec_live_executor 测试 mock fetch_source_rows / sink_to_dataset / sink_to_ot /
  get_engine，不依赖真实 PG / 对象存储。
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aos_api.ec_live_executor import ec_live_executor
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")

PIPELINE_ID = "ec-p02-product-api"
SOURCE_ID = "niushop-product-api-p02"


# ═══════════════════════════════════════════════
# frozen/02 配置规格（P02 Product）
# ═══════════════════════════════════════════════


def _pipeline_payload() -> dict:
    """frozen/02 P02 Product Pipeline 配置（含 nodes/edges/config）。"""
    return {
        "id": PIPELINE_ID,
        "sourceId": SOURCE_ID,
        "name": "P02 Product Pipeline API",
        "displayName": "栖月汇商品",
        "objectTypeHint": "Product",
        "target": "dataset",
        "config": {
            "target_ot": "Product",
            "source_table": "ns_goods",
            "source_filter": "site_id=1 AND is_delete=0",
            "unique_key_template": "niushop:1:{goods_id}",
            "cursor_fields": ["modify_time", "goods_id"],
            "cursor_fallback": "create_time",
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": SOURCE_ID,
                    "source_table": "ns_goods",
                    "source_filter": "site_id=1 AND is_delete=0",
                    "primary_key": "goods_id",
                    "cursor_fields": ["modify_time", "goods_id"],
                    "cursor_fallback": "create_time",
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {
                    "target_ot": "Product",
                    "unique_key_template": "niushop:1:{goods_id}",
                    "zero_time_to_null": True,
                    "decimal_fields": ["price"],
                    "enum_fields": {"goods_state": [0, 1]},
                },
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {
                    "required_fields": ["goods_name"],
                    "soft_delete_filter": "is_delete=1",
                },
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {
                    "target_ot": "Product",
                    "derived_metrics": ["quality_score"],
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


def _ensure_source(client, auth_headers):
    """创建 Pipeline 前置依赖：Source（ConnectorIn）。"""
    payload = {"id": SOURCE_ID, "type": "file"}
    resp = client.post("/v1/sources", json=payload, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ═══════════════════════════════════════════════
# row 工厂（OT 行格式，与 test_ec_d1_p02_product.py 对齐）
# ═══════════════════════════════════════════════


def _make_product_row(
    *,
    goods_id: str = "g-1",
    category_id: str = "c-1",
    when: datetime = NOW,
) -> dict:
    return {
        "ot": "Product",
        "source_pk": goods_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "shopId": "1",
            "title": f"商品{goods_id}",
            "status": "active",
            "categoryId": category_id,
            "price": "99.00",
            "currency": "CNY",
            "goodsState": 1,
            "createdAt": "2026-07-31T18:00:00+08:00",
            "updatedAt": "2026-07-31T18:00:00+08:00",
        },
    }


def _links_by_type(rows: list[dict], link_type: str) -> list[dict]:
    return [r for r in rows if r.get("link_type") == link_type]


def _object_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if "link_type" not in r]


def _api_pipeline_to_ns(api_item: dict) -> SimpleNamespace:
    """把 API 返回的 pipeline dict 转成 ec_live_executor 需要的 SimpleNamespace。"""
    return SimpleNamespace(
        id=api_item["id"],
        config=api_item.get("config") or {},
    )


# ═══════════════════════════════════════════════
# 1-4. API 配置创建与持久化验证
# ═══════════════════════════════════════════════


class TestP02ApiConfigCreation:
    """1-4: POST /v1/pipelines 创建 + GET 查询持久化 + nodes 完整性 + config.target_ot。"""

    def test_01_create_pipeline_with_nodes_edges_config(self, client, auth_headers):
        """1. POST /v1/pipelines 创建配置（含 nodes/edges/config），返回 200 + 持久化 item。"""
        _ensure_source(client, auth_headers)
        payload = _pipeline_payload()

        resp = client.post("/v1/pipelines", json=payload, headers=auth_headers)
        assert resp.status_code == 200, resp.text

        body = resp.json()
        assert body["id"] == PIPELINE_ID
        assert body["sourceId"] == SOURCE_ID
        assert body["objectTypeHint"] == "Product"
        assert body["displayName"] == "栖月汇商品"
        # nodes/edges/config 持久化（PipelineIn.model_dump 全字段透传）
        assert len(body["nodes"]) == 4
        assert len(body["edges"]) == 3
        assert body["config"]["target_ot"] == "Product"

    def test_02_get_pipelines_nodes_persisted(self, client, auth_headers):
        """2. GET /v1/pipelines 列表查询，验证 nodes 字段持久化（4 节点）。"""
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        assert resp.status_code == 200, resp.text

        items = resp.json()["items"]
        matched = [p for p in items if p["id"] == PIPELINE_ID]
        assert len(matched) == 1, f"pipeline {PIPELINE_ID} not found in list"

        pipeline = matched[0]
        nodes = pipeline["nodes"]
        assert len(nodes) == 4
        node_ids = {n["id"] for n in nodes}
        assert node_ids == {"source", "normalize", "validate", "quality_gate"}

    def test_03_source_node_cursor_fields_complete(self, client, auth_headers):
        """3. Source 节点 config 完整性：含 cursor_fields/cursor_fallback/primary_key。"""
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )
        source_node = next(n for n in pipeline["nodes"] if n["id"] == "source")
        cfg = source_node["config"]

        assert cfg["primary_key"] == "goods_id"
        assert cfg["cursor_fields"] == ["modify_time", "goods_id"]
        assert cfg["cursor_fallback"] == "create_time"
        assert cfg["source_table"] == "ns_goods"
        assert cfg["source_filter"] == "site_id=1 AND is_delete=0"

    def test_04_config_target_ot_product(self, client, auth_headers):
        """4. pipeline.config.target_ot == 'Product'。"""
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )
        assert pipeline["config"]["target_ot"] == "Product"
        # 与 objectTypeHint 一致
        assert pipeline["objectTypeHint"] == "Product"


# ═══════════════════════════════════════════════
# 5. ec_live_executor 能读取 API 配置执行
# ═══════════════════════════════════════════════


class TestP02ExecutorReadsApiConfig:
    """5. ec_live_executor 能读取 API 创建的 pipeline 配置执行。"""

    def test_05_ec_live_executor_reads_api_config(self, client, auth_headers):
        """5. 构造 mock pipeline（从 API 配置转 SimpleNamespace）+ nodes，
        调用 ec_live_executor，验证 rows_read/rows_written 正确。
        """
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        # 从 API 拿回持久化的 pipeline 配置
        resp = client.get("/v1/pipelines", headers=auth_headers)
        api_pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )

        # 转 SimpleNamespace（ec_live_executor 通过 getattr 访问 id/config）
        pipeline_ns = _api_pipeline_to_ns(api_pipeline)
        nodes_ns = [SimpleNamespace(**n) for n in api_pipeline["nodes"]]

        source_rows = [
            _make_product_row(goods_id="g-1", category_id="c-1"),
            _make_product_row(goods_id="g-2", category_id="1,2,3"),
        ]

        def _sink_ds(eng, sc, pl, out_rows):
            return SimpleNamespace(id="ds-p02-api")

        sink_ot_calls: list[tuple] = []

        def _sink_ot(eng, sc, pl, out_rows):
            sink_ot_calls.append((sc, pl, [dict(r) for r in out_rows]))
            obj_cnt = len(_object_rows(out_rows))
            lk_cnt = len([r for r in out_rows if r.get("link_type")])
            return {"objects_written": obj_cnt, "links_written": lk_cnt}

        with patch("aos_api.ec_live_executor.fetch_source_rows", return_value=source_rows), \
             patch("aos_api.ec_live_executor.sink_to_dataset", side_effect=_sink_ds), \
             patch("aos_api.ec_live_executor.sink_to_ot", side_effect=_sink_ot), \
             patch("aos_api.ec_live_executor.get_engine", return_value=MagicMock()):
            result = ec_live_executor(
                pipeline=pipeline_ns,
                nodes=nodes_ns,
                node_id="source",
                sample_input=None,
                execution_kind="live",
                cancel_event=SimpleNamespace(is_set=False),
                deadline=1e9,
                scope=TEST_SCOPE,
            )

        # 2 source rows → 2 objects + 4 inCategory + 2 sellsProduct = 8
        assert result["rows_read"] == 2
        assert result["rows_written"] == 8
        assert len(sink_ot_calls) == 1
        _, _, output_rows = sink_ot_calls[0]
        # 验证 inCategory Link 构造（与 config.link_rules.inCategory 对齐）
        links = _links_by_type(output_rows, "Product.inCategory")
        assert len(links) == 4  # g-1 → 1, g-2 → 3
        assert result["output_ref"].startswith("dataset://catalog/")


# ═══════════════════════════════════════════════
# 6-7. 派生指标 + Link 规则配置验证
# ═══════════════════════════════════════════════


class TestP02QualityGateConfig:
    """6-7: quality_gate 节点 derived_metrics + link_rules 配置验证。"""

    def test_06_quality_gate_derived_metrics_quality_score(self, client, auth_headers):
        """6. quality_gate.config.derived_metrics 含 'quality_score'。"""
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )
        qg = next(n for n in pipeline["nodes"] if n["id"] == "quality_gate")

        assert qg["config"]["target_ot"] == "Product"
        assert "quality_score" in qg["config"]["derived_metrics"]
        # 与 ec_derived_metrics._PIPELINE_ID_TO_OT 推断表一致
        assert qg["config"]["derived_metrics"] == ["quality_score"]

    def test_07_quality_gate_link_rules_inCategory(self, client, auth_headers):
        """7. quality_gate.config.link_rules.inCategory 配置验证。"""
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )
        qg = next(n for n in pipeline["nodes"] if n["id"] == "quality_gate")

        link_rules = qg["config"]["link_rules"]
        assert "inCategory" in link_rules
        assert link_rules["inCategory"] == "split by comma"
        # 与 ec_link_builder._build_in_category_links 多值拆分逻辑对齐
        assert "comma" in link_rules["inCategory"]


# ═══════════════════════════════════════════════
# 8. ec_live_executor + build_link_rows 端到端 Link 行追加
# ═══════════════════════════════════════════════


class TestP02ExecutorLinkLandingE2E:
    """8. ec_live_executor + build_link_rows 端到端：mock ec_derived_metrics 透传，
    验证 inCategory Link 行正确追加到 output_rows。
    """

    def test_08_ec_live_executor_link_rows_appended(self, client, auth_headers):
        """8. mock ec_derived_metrics 为透传，验证 build_link_rows 在 executor
        链路中正确追加 inCategory Link 行（单值 + 多值拆分）。
        """
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        api_pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )
        pipeline_ns = _api_pipeline_to_ns(api_pipeline)

        source_rows = [
            _make_product_row(goods_id="g-1", category_id="c-1"),  # 1 link
            _make_product_row(goods_id="g-2", category_id="1,2,3"),  # 3 links
        ]

        sink_ot_calls: list[tuple] = []

        def _sink_ot(eng, sc, pl, out_rows):
            sink_ot_calls.append((sc, pl, [dict(r) for r in out_rows]))
            return {
                "objects_written": len(_object_rows(out_rows)),
                "links_written": len([r for r in out_rows if r.get("link_type")]),
            }

        # mock ec_derived_metrics 为透传（聚焦验证 build_link_rows 输出）
        with patch("aos_api.ec_live_executor.fetch_source_rows", return_value=source_rows), \
             patch("aos_api.ec_live_executor.sink_to_dataset",
                   side_effect=lambda *a, **kw: SimpleNamespace(id="ds-p02-link")), \
             patch("aos_api.ec_live_executor.sink_to_ot", side_effect=_sink_ot), \
             patch("aos_api.ec_live_executor.get_engine", return_value=MagicMock()), \
             patch("aos_api.ec_live_executor.apply_derived_metrics",
                   side_effect=lambda rows, pipeline: rows):
            result = ec_live_executor(
                pipeline=pipeline_ns,
                nodes=[SimpleNamespace(id="source", node_type="source", config={})],
                node_id="source",
                sample_input=None,
                execution_kind="live",
                cancel_event=SimpleNamespace(is_set=False),
                deadline=1e9,
                scope=TEST_SCOPE,
            )

        # 2 objects + 4 inCategory links = 6
        assert result["rows_read"] == 2
        assert result["rows_written"] == 6

        assert len(sink_ot_calls) == 1
        _, _, output_rows = sink_ot_calls[0]

        # Object 行验证
        objs = _object_rows(output_rows)
        assert len(objs) == 2
        assert {o["source_pk"] for o in objs} == {"g-1", "g-2"}

        # inCategory Link 行验证（与 quality_gate.config.link_rules.inCategory 对齐）
        links = _links_by_type(output_rows, "Product.inCategory")
        assert len(links) == 4

        # g-1 → 1 条 Link（c-1）
        g1_links = [l for l in links if l["source_pk"] == "g-1"]
        assert len(g1_links) == 1
        assert g1_links[0]["target_source_pk"] == "c-1"
        assert g1_links[0]["source_type"] == "Product"
        assert g1_links[0]["target_type"] == "Category"

        # g-2 → 3 条 Link（拆分 1,2,3）
        g2_links = [l for l in links if l["source_pk"] == "g-2"]
        assert len(g2_links) == 3
        assert {l["target_source_pk"] for l in g2_links} == {"1", "2", "3"}

        # Link 行不含 ot 字段（与 ec_link_builder 约定一致）
        assert all("ot" not in l for l in links)
        assert all(l["is_deleted"] is False for l in links)
