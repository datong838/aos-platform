"""D1 Phase D W3: P03 ProductSku 真实 API 配置创建 + Link 落地验证测试。

覆盖 8 项（frozen/02 规格）：
1. POST /v1/pipelines 创建配置（含 nodes/edges/config）
2. GET /v1/pipelines 查询验证 nodes 持久化
3. Source 节点 config 含 cursor_fields/cursor_fallback
4. pipeline.config.target_ot 正确（ProductSku）
5. ec_live_executor 能读取 API 配置执行
6. quality_gate.config.derived_metrics 含 "stock_health"
7. quality_gate.config.link_rules.hasSku 配置验证
8. ec_live_executor + build_link_rows 端到端 Link 行追加（mock ec_derived_metrics 透传）

注：
- wave_ext.py 没有 GET /v1/pipelines/{id} 单点端点（object_storage_indexing.py
  拦截该路径走 StreamIndexEngine，不同存储）。使用 GET /v1/pipelines 列表过滤 id 验证。
- ec_live_executor 测试 mock fetch_source_rows / sink_to_dataset / sink_to_ot /
  get_engine，不依赖真实 PG / 对象存储。
- hasSku 经 ec_link_builder._REVERSED_LINKS 反转方向：
  frozen/02 Product→ProductSku 反转为 CORE ProductSku→Product（ProductSku.ofProduct）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aos_api.ec_live_executor import ec_live_executor
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)
TEST_SCOPE = TenantScope("dev-org", "dev-project")

PIPELINE_ID = "ec-p03-sku-api"
SOURCE_ID = "niushop-sku-api-p03"


# ═══════════════════════════════════════════════
# frozen/02 配置规格（P03 ProductSku）
# ═══════════════════════════════════════════════


def _pipeline_payload() -> dict:
    """frozen/02 P03 ProductSku Pipeline 配置（含 nodes/edges/config）。"""
    return {
        "id": PIPELINE_ID,
        "sourceId": SOURCE_ID,
        "name": "P03 ProductSku Pipeline API",
        "displayName": "栖月汇商品SKU",
        "objectTypeHint": "ProductSku",
        "target": "dataset",
        "config": {
            "target_ot": "ProductSku",
            "source_table": "ns_goods_sku",
            "source_filter": "site_id=1 AND is_delete=0",
            "unique_key_template": "niushop:1:{sku_id}",
            "cursor_fields": ["modify_time", "sku_id"],
            "cursor_fallback": "create_time",
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": SOURCE_ID,
                    "source_table": "ns_goods_sku",
                    "source_filter": "site_id=1 AND is_delete=0",
                    "primary_key": "sku_id",
                    "cursor_fields": ["modify_time", "sku_id"],
                    "cursor_fallback": "create_time",
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {
                    "target_ot": "ProductSku",
                    "unique_key_template": "niushop:1:{sku_id}",
                    "zero_time_to_null": True,
                },
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {
                    "required_fields": ["sku_name"],
                    "orphan_detection": "product_id not in Product",
                    "soft_delete_filter": "is_delete=1",
                },
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {
                    "target_ot": "ProductSku",
                    "derived_metrics": ["stock_health"],
                    "link_rules": {
                        "hasSku": "source=product_id, target=sku_id",
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


def _ensure_source(client, auth_headers):
    """创建 Pipeline 前置依赖：Source（ConnectorIn）。"""
    payload = {"id": SOURCE_ID, "type": "file"}
    resp = client.post("/v1/sources", json=payload, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ═══════════════════════════════════════════════
# row 工厂（OT 行格式，与 test_ec_d1_p03_sku.py 对齐）
# ═══════════════════════════════════════════════


def _make_sku_row(
    *,
    sku_id: str = "s-1",
    product_id: str = "g-1",
    when: datetime = NOW,
) -> dict:
    return {
        "ot": "ProductSku",
        "source_pk": sku_id,
        "source_updated_at": when,
        "source_timezone": "+00:00",
        "is_deleted": False,
        "properties": {
            "productId": product_id,
            "status": "active",
            "barcode": f"BC-{sku_id}",
            "price": "99.00",
            "currency": "CNY",
            "stock": 100,
            "goodsStockAlarm": 10,
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


class TestP03ApiConfigCreation:
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
        assert body["objectTypeHint"] == "ProductSku"
        assert body["displayName"] == "栖月汇商品SKU"
        # nodes/edges/config 持久化（PipelineIn.model_dump 全字段透传）
        assert len(body["nodes"]) == 4
        assert len(body["edges"]) == 3
        assert body["config"]["target_ot"] == "ProductSku"

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

        assert cfg["primary_key"] == "sku_id"
        assert cfg["cursor_fields"] == ["modify_time", "sku_id"]
        assert cfg["cursor_fallback"] == "create_time"
        assert cfg["source_table"] == "ns_goods_sku"
        assert cfg["source_filter"] == "site_id=1 AND is_delete=0"

    def test_04_config_target_ot_product_sku(self, client, auth_headers):
        """4. pipeline.config.target_ot == 'ProductSku'。"""
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )
        assert pipeline["config"]["target_ot"] == "ProductSku"
        # 与 objectTypeHint 一致
        assert pipeline["objectTypeHint"] == "ProductSku"


# ═══════════════════════════════════════════════
# 5. ec_live_executor 能读取 API 配置执行
# ═══════════════════════════════════════════════


class TestP03ExecutorReadsApiConfig:
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
            _make_sku_row(sku_id="s-1", product_id="g-1"),
            _make_sku_row(sku_id="s-2", product_id="g-1"),
            _make_sku_row(sku_id="s-3", product_id="g-2"),
        ]

        def _sink_ds(eng, sc, pl, out_rows):
            return SimpleNamespace(id="ds-p03-api")

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

        # 3 source rows → 3 objects + 3 hasSku links = 6
        assert result["rows_read"] == 3
        assert result["rows_written"] == 6
        assert len(sink_ot_calls) == 1
        _, _, output_rows = sink_ot_calls[0]
        # 验证 hasSku Link 构造（反转后为 ProductSku.ofProduct，与 config.link_rules.hasSku 对齐）
        links = _links_by_type(output_rows, "ProductSku.ofProduct")
        assert len(links) == 3
        assert result["output_ref"].startswith("dataset://catalog/")


# ═══════════════════════════════════════════════
# 6-7. 派生指标 + Link 规则配置验证
# ═══════════════════════════════════════════════


class TestP03QualityGateConfig:
    """6-7: quality_gate 节点 derived_metrics + link_rules 配置验证。"""

    def test_06_quality_gate_derived_metrics_stock_health(self, client, auth_headers):
        """6. quality_gate.config.derived_metrics 含 'stock_health'。"""
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )
        qg = next(n for n in pipeline["nodes"] if n["id"] == "quality_gate")

        assert qg["config"]["target_ot"] == "ProductSku"
        assert "stock_health" in qg["config"]["derived_metrics"]
        # 与 ec_derived_metrics._PIPELINE_ID_TO_OT 推断表一致
        assert qg["config"]["derived_metrics"] == ["stock_health"]

    def test_07_quality_gate_link_rules_hasSku(self, client, auth_headers):
        """7. quality_gate.config.link_rules.hasSku 配置验证。"""
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )
        qg = next(n for n in pipeline["nodes"] if n["id"] == "quality_gate")

        link_rules = qg["config"]["link_rules"]
        assert "hasSku" in link_rules
        assert "product_id" in link_rules["hasSku"]
        assert "sku_id" in link_rules["hasSku"]
        # 与 ec_link_builder._build_has_sku_links 字段映射对齐：
        # source_pk = row.source_pk（sku_id），target = row.properties.productId
        assert link_rules["hasSku"] == "source=product_id, target=sku_id"


# ═══════════════════════════════════════════════
# 8. ec_live_executor + build_link_rows 端到端 Link 行追加
# ═══════════════════════════════════════════════


class TestP03ExecutorLinkLandingE2E:
    """8. ec_live_executor + build_link_rows 端到端：mock ec_derived_metrics 透传，
    验证 hasSku Link 行正确追加到 output_rows（经 _REVERSED_LINKS 反转方向）。
    """

    def test_08_ec_live_executor_link_rows_appended(self, client, auth_headers):
        """8. mock ec_derived_metrics 为透传，验证 build_link_rows 在 executor
        链路中正确追加 hasSku Link 行（反转后为 ProductSku.ofProduct）。
        """
        _ensure_source(client, auth_headers)
        client.post("/v1/pipelines", json=_pipeline_payload(), headers=auth_headers)

        resp = client.get("/v1/pipelines", headers=auth_headers)
        api_pipeline = next(
            p for p in resp.json()["items"] if p["id"] == PIPELINE_ID
        )
        pipeline_ns = _api_pipeline_to_ns(api_pipeline)

        source_rows = [
            _make_sku_row(sku_id="s-1", product_id="g-1"),  # 1 link
            _make_sku_row(sku_id="s-2", product_id="g-1"),  # 1 link
            _make_sku_row(sku_id="s-3", product_id="g-2"),  # 1 link
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
                   side_effect=lambda *a, **kw: SimpleNamespace(id="ds-p03-link")), \
             patch("aos_api.ec_live_executor.sink_to_ot", side_effect=_sink_ot), \
             patch("aos_api.ec_live_executor.get_engine", return_value=MagicMock()), \
             patch("aos_api.ec_live_executor.apply_derived_metrics",
                   side_effect=lambda rows, pipeline, *, link_aggregator: rows):
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

        # 3 objects + 3 hasSku links = 6
        assert result["rows_read"] == 3
        assert result["rows_written"] == 6

        assert len(sink_ot_calls) == 1
        _, _, output_rows = sink_ot_calls[0]

        # Object 行验证
        objs = _object_rows(output_rows)
        assert len(objs) == 3
        assert {o["source_pk"] for o in objs} == {"s-1", "s-2", "s-3"}

        # hasSku Link 行验证（反转后为 ProductSku.ofProduct，
        # source=ProductSku(sku_id), target=Product(product_id)）
        links = _links_by_type(output_rows, "ProductSku.ofProduct")
        assert len(links) == 3

        # 验证 source/target 方向反转（与 ec_link_builder._REVERSED_LINKS 对齐）
        pairs = {(l["source_pk"], l["target_source_pk"]) for l in links}
        assert pairs == {("s-1", "g-1"), ("s-2", "g-1"), ("s-3", "g-2")}
        assert all(l["source_type"] == "ProductSku" for l in links)
        assert all(l["target_type"] == "Product" for l in links)

        # g-1 有 2 个 SKU（target_source_pk = g-1 的有 2 条）
        g1_links = [l for l in links if l["target_source_pk"] == "g-1"]
        assert len(g1_links) == 2
        assert {l["source_pk"] for l in g1_links} == {"s-1", "s-2"}

        # Link 行不含 ot 字段（与 ec_link_builder 约定一致）
        assert all("ot" not in l for l in links)
        assert all(l["is_deleted"] is False for l in links)
