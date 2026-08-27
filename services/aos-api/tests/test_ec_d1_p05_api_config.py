"""D1-W4: P05 Order 真实 API 配置创建 + 负向验证（Phase D）。

P05 Order 配置规格（frozen/02）：
- id: ec-p05-order
- sourceId: niushop-order
- displayName: 栖月汇订单
- objectTypeHint: Order
- config.target_ot: Order
- nodes: source / normalize / validate / quality_gate
- edges: source → normalize → validate → quality_gate

测试覆盖（10 项）：
1. POST /v1/pipelines 创建配置（含 nodes/edges/config）
2. GET /v1/pipelines 查询验证 nodes 持久化
3. Source 节点 config 含 cursor_fields
4. pipeline.config.target_ot == "Order"
5. ec_live_executor 能读取配置执行
6. quality_gate.config.derived_metrics 含 "risk_score"
7. validate.config.required_fields == ["order_no"]
8. normalize.config.pii_fields 含 "member_id"（仅保留关联键）
9. normalize.config.decimal_fields == ["order_money", "goods_money"]
10. 负向：跨租户创建同 pipeline_id 被拒绝（409 TENANT_SCOPE_CONFLICT）

约束：
- 用 TestClient + auth_headers（dev-org/dev-project）走真实 HTTP 路由
- pipeline_id 用 uuid 后缀避免跨测试污染 _pipelines 全局状态
- ec_live_executor 调用 mock 下游（fetch_source_rows/sink_*），验证 executor 顺利执行
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
# P05 Order 配置（frozen/02）
# ═══════════════════════════════════════════════


def _p05_payload(pid: str, sid: str) -> dict[str, Any]:
    """构造 P05 pipeline 创建 payload（含 nodes/edges/config）。"""
    return {
        "id": pid,
        "sourceId": sid,
        "name": "P05 Order Pipeline",
        "displayName": "栖月汇订单",
        "objectTypeHint": "Order",
        "config": {
            "target_ot": "Order",
            "source_table": "ns_order",
            "source_filter": "site_id=1 AND is_delete=0",
            "unique_key_template": "niushop:1:{order_id}",
            "cursor_fields": ["create_time", "order_id"],
            "incremental_strategy": "hourly_rescan_7d",
        },
        "nodes": [
            {
                "id": "source",
                "name": "Source",
                "type": "source",
                "config": {
                    "source_id": "niushop-order",
                    "source_table": "ns_order",
                    "source_filter": "site_id=1 AND is_delete=0",
                    "primary_key": "order_id",
                    "cursor_fields": ["create_time", "order_id"],
                },
            },
            {
                "id": "normalize",
                "name": "Normalize",
                "type": "transform",
                "config": {
                    "target_ot": "Order",
                    "unique_key_template": "niushop:1:{order_id}",
                    "zero_time_to_null": True,
                    "decimal_fields": ["order_money", "goods_money"],
                    "pii_fields": ["member_id"],
                },
            },
            {
                "id": "validate",
                "name": "Validate",
                "type": "gate",
                "config": {
                    "required_fields": ["order_no"],
                    "soft_delete_filter": "is_delete=1",
                },
            },
            {
                "id": "quality_gate",
                "name": "QualityGate",
                "type": "gate",
                "config": {
                    "target_ot": "Order",
                    "derived_metrics": ["risk_score"],
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
def p05_pipeline(client, auth_headers):
    """创建 P05 pipeline，返回 GET /v1/pipelines 取回的 pipeline dict。"""
    pid = f"ec-p05-order-{uuid.uuid4().hex[:8]}"
    sid = f"niushop-order-{pid}"
    # 先创建 source（pipeline.sourceId 必须存在）
    r_src = client.post(
        "/v1/sources", headers=auth_headers, json={"id": sid, "type": "file"}
    )
    assert r_src.status_code == 200, r_src.text
    # 创建 pipeline
    r = client.post(
        "/v1/pipelines", headers=auth_headers, json=_p05_payload(pid, sid)
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


def test_p05_create_pipeline_via_api(p05_pipeline):
    """#1 POST /v1/pipelines 创建配置（含 nodes/edges/config）。"""
    assert p05_pipeline["id"].startswith("ec-p05-order-")
    assert p05_pipeline["displayName"] == "栖月汇订单"
    assert p05_pipeline["objectTypeHint"] == "Order"
    assert p05_pipeline["sourceId"].startswith("niushop-order-")
    # nodes/edges/config 持久化（回显）
    assert len(p05_pipeline["nodes"]) == 4
    assert len(p05_pipeline["edges"]) == 3
    assert p05_pipeline["config"]["target_ot"] == "Order"
    # datasetRid 自动生成
    assert p05_pipeline["datasetRid"].startswith("ri.dataset.")


def test_p05_get_pipeline_persists_nodes(client, auth_headers, p05_pipeline):
    """#2 GET /v1/pipelines 查询验证 nodes 持久化。"""
    r = client.get("/v1/pipelines", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    matched = [p for p in items if p["id"] == p05_pipeline["id"]]
    assert len(matched) == 1
    got = matched[0]
    # nodes 完整持久化（4 个节点）
    assert len(got.get("nodes") or []) == 4
    node_ids = {n["id"] for n in got["nodes"]}
    assert node_ids == {"source", "normalize", "validate", "quality_gate"}
    # edges 持久化
    assert len(got.get("edges") or []) == 3


def test_p05_source_node_has_cursor_fields(p05_pipeline):
    """#3 Source 节点 config 包含 cursor_fields（nodes 配置完整性）。"""
    src = _find_node(p05_pipeline, "source")
    cfg = src["config"]
    assert cfg["source_id"] == "niushop-order"
    assert cfg["source_table"] == "ns_order"
    assert cfg["primary_key"] == "order_id"
    # cursor_fields 完整（复合游标）
    assert cfg["cursor_fields"] == ["create_time", "order_id"]


def test_p05_config_target_ot_is_order(p05_pipeline):
    """#4 pipeline.config.target_ot 正确（Order）。"""
    cfg = p05_pipeline["config"]
    assert cfg["target_ot"] == "Order"
    assert cfg["source_table"] == "ns_order"
    assert cfg["unique_key_template"] == "niushop:1:{order_id}"
    assert cfg["incremental_strategy"] == "hourly_rescan_7d"


def test_p05_ec_live_executor_reads_config(p05_pipeline, monkeypatch):
    """#5 ec_live_executor 能读取配置执行（mock 下游，验证 executor 顺利返回）。"""
    fake_row = {
        "ot": "Order",
        "source_pk": "100",
        "source_updated_at": "2026-07-31T10:00:00+00:00",
        "source_timezone": "+00:00",
        "properties": {"orderNo": "NO001", "memberId": "m-1"},
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
        id=p05_pipeline["id"], config=p05_pipeline["config"]
    )
    nodes = [
        SimpleNamespace(id=n["id"], config=n["config"])
        for n in p05_pipeline["nodes"]
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


def test_p05_quality_gate_derived_metrics(p05_pipeline):
    """#6 quality_gate.config.derived_metrics 含 "risk_score"。"""
    qg = _find_node(p05_pipeline, "quality_gate")
    cfg = qg["config"]
    assert cfg["target_ot"] == "Order"
    assert "risk_score" in cfg["derived_metrics"]


def test_p05_validate_required_fields(p05_pipeline):
    """#7 validate.config.required_fields == ["order_no"]。"""
    v = _find_node(p05_pipeline, "validate")
    cfg = v["config"]
    assert cfg["required_fields"] == ["order_no"]
    assert cfg["soft_delete_filter"] == "is_delete=1"


def test_p05_normalize_pii_fields_member_id(p05_pipeline):
    """#8 normalize.config.pii_fields 含 "member_id"（仅保留关联键，不引 PII）。"""
    nm = _find_node(p05_pipeline, "normalize")
    cfg = nm["config"]
    assert cfg["target_ot"] == "Order"
    assert "member_id" in cfg["pii_fields"]
    # pii_fields 只含 member_id（关联键），不含手机/身份证/邮箱等真实 PII
    pii_keys = set(cfg["pii_fields"])
    assert pii_keys == {"member_id"}


def test_p05_normalize_decimal_fields(p05_pipeline):
    """#9 normalize.config.decimal_fields == ["order_money", "goods_money"]。"""
    nm = _find_node(p05_pipeline, "normalize")
    cfg = nm["config"]
    assert cfg["decimal_fields"] == ["order_money", "goods_money"]
    assert cfg["zero_time_to_null"] is True


def test_p05_cross_tenant_create_rejected(client, auth_headers):
    """#10 负向：跨租户创建同 pipeline_id 被拒绝（409 TENANT_SCOPE_CONFLICT）。

    场景：
    1. dev-org 创建 pipeline-P（sourceId=src-dev）
    2. other-org 创建同 id pipeline-P（sourceId=src-other，避免 source 跨租户先抛）
    3. _assert_mutation_scope 检测到 _pipelines[P] 属于 dev-org → 抛 TENANT_SCOPE_CONFLICT
    """
    pid = f"ec-p05-cross-{uuid.uuid4().hex[:8]}"
    sid_dev = f"niushop-order-dev-{pid}"
    sid_other = f"niushop-order-other-{pid}"

    # dev-org 创建 source + pipeline
    r = client.post(
        "/v1/sources", headers=auth_headers, json={"id": sid_dev, "type": "file"}
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/v1/pipelines", headers=auth_headers, json=_p05_payload(pid, sid_dev)
    )
    assert r.status_code == 200, r.text

    # 精确登记负租户，使请求抵达被测 pipeline scope 冲突，而不是被目录门提前拒绝。
    from aos_api.db import connect

    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES ('other-org','负向测试组织') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) "
            "VALUES ('other-org','other-project','负向测试工作区') "
            "ON CONFLICT (org_id,project_id) DO NOTHING"
        )
        conn.commit()

    # other-org 创建自己的 source（避免 source 跨租户先抛）
    other_headers = {
        **auth_headers,
        "X-Org-Id": "other-org",
        "X-Project-Id": "other-project",
    }
    try:
        r = client.post(
            "/v1/sources",
            headers=other_headers,
            json={"id": sid_other, "type": "file"},
        )
        assert r.status_code == 200, r.text

        # other-org 创建同 id pipeline → 409 TENANT_SCOPE_CONFLICT
        r2 = client.post(
            "/v1/pipelines", headers=other_headers, json=_p05_payload(pid, sid_other)
        )
        assert r2.status_code == 409, r2.text
        assert r2.json()["code"] == "TENANT_SCOPE_CONFLICT"
    finally:
        with connect() as conn:
            conn.execute(
                "DELETE FROM meta_source WHERE id=%s AND org_id='other-org' AND project_id='other-project'",
                (sid_other,),
            )
            conn.execute(
                "DELETE FROM twa_workspace WHERE org_id='other-org' AND project_id='other-project'"
            )
            conn.execute("DELETE FROM twa_org WHERE id='other-org'")
            conn.commit()
