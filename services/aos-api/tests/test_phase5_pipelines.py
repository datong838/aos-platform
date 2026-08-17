"""Phase 5 · Pipeline Core API — 单元测试 (≥27).

Tests for phase5_pipeline_engine, phase5_pipelines, phase5_schedules, phase5_datasets.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from aos_api.db import connect
from aos_api.phase5_pipeline_engine import get_engine
from aos_api.tenant_scope import TenantScope


TEST_SCOPE = TenantScope("dev-org", "dev-project")


@pytest.fixture(autouse=True)
def reset_engine():
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES ('dev-org','测试组织') "
            "ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) "
            "VALUES ('dev-org','dev-project','测试工作区') ON CONFLICT DO NOTHING"
        )
        conn.commit()
    get_engine().reset(scope=TEST_SCOPE, purge_persisted=True)
    yield
    get_engine().reset(scope=TEST_SCOPE, purge_persisted=True)


# ═══════════════════════════════════════════
# Pipelines tests (9)
# ═══════════════════════════════════════════


def test_create_and_get_pipeline() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="ETL-1", pipeline_type="ETL", status="active")
    fetched = eng.get_pipeline(TEST_SCOPE, pl.id)
    assert fetched is not None
    assert fetched.name == "ETL-1"
    assert fetched.pipeline_type == "ETL"


def test_list_pipelines_with_filter() -> None:
    eng = get_engine()
    eng.create_pipeline(TEST_SCOPE, name="A", status="active")
    eng.create_pipeline(TEST_SCOPE, name="B", status="draft")
    eng.create_pipeline(TEST_SCOPE, name="C", status="active")
    items, total = eng.list_pipelines(TEST_SCOPE, status="active")
    assert total == 2
    assert all(p.status == "active" for p in items)


def test_list_pipelines_search() -> None:
    eng = get_engine()
    eng.create_pipeline(TEST_SCOPE, name="customer_etl")
    eng.create_pipeline(TEST_SCOPE, name="orders_elt")
    items, total = eng.list_pipelines(TEST_SCOPE, search="customer")
    assert total == 1
    assert items[0].name == "customer_etl"


def test_update_pipeline() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")
    updated = eng.update_pipeline(TEST_SCOPE, pl.id, status="active", description="updated")
    assert updated.status == "active"
    assert updated.description == "updated"


def test_get_pipeline_not_found() -> None:
    eng = get_engine()
    assert eng.get_pipeline(TEST_SCOPE, "nope") is None


def test_pipeline_graph() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")
    n1 = eng.add_node(TEST_SCOPE, pl.id, "src", node_type="source")
    n2 = eng.add_node(TEST_SCOPE, pl.id, "sink", node_type="sink")
    eng.add_edge(TEST_SCOPE, pl.id, n1.id, n2.id)
    graph = eng.get_graph(TEST_SCOPE, pl.id)
    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1


def test_replace_pipeline_graph_round_trip() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")
    result = eng.replace_graph(
        TEST_SCOPE,
        pl.id,
        [
            {"id": "n-source", "name": "source", "node_type": "source", "position_x": 12, "position_y": 34},
            {"id": "n-sink", "name": "sink", "node_type": "sink", "position_x": 420, "position_y": 34},
        ],
        [{"id": "e-1", "source_node_id": "n-source", "target_node_id": "n-sink"}],
        pipeline_type="Streaming",
        write_mode="UPSERT",
    )
    assert result["node_count"] == 2
    assert result["edge_count"] == 1
    assert {n["id"] for n in result["nodes"]} == {"n-source", "n-sink"}
    assert eng.get_pipeline(TEST_SCOPE, pl.id).pipeline_type == "Streaming"  # type: ignore[union-attr]
    assert eng.get_pipeline(TEST_SCOPE, pl.id).write_mode == "UPSERT"  # type: ignore[union-attr]


def test_replace_pipeline_graph_rejects_cycle_without_mutation() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")
    original = eng.add_node(TEST_SCOPE, pl.id, "original", node_type="source")
    with pytest.raises(ValueError, match="acyclic"):
        eng.replace_graph(
            TEST_SCOPE,
            pl.id,
            [
                {"id": "a", "name": "A", "node_type": "source"},
                {"id": "b", "name": "B", "node_type": "sink"},
            ],
            [
                {"source_node_id": "a", "target_node_id": "b"},
                {"source_node_id": "b", "target_node_id": "a"},
            ],
        )
    assert [node.id for node in eng.list_nodes(TEST_SCOPE, pl.id)] == [original.id]


def test_replace_pipeline_graph_rejects_cross_pipeline_id_collision() -> None:
    eng = get_engine()
    first = eng.create_pipeline(TEST_SCOPE, name="First")
    second = eng.create_pipeline(TEST_SCOPE, name="Second")
    owned = eng.add_node(TEST_SCOPE, first.id, "owned", node_type="source")
    with pytest.raises(ValueError, match="another pipeline"):
        eng.replace_graph(
            TEST_SCOPE,
            second.id,
            [{"id": owned.id, "name": "collision", "node_type": "source"}],
            [],
        )
    assert eng.get_node(TEST_SCOPE, owned.id).pipeline_id == first.id  # type: ignore[union-attr]


def test_replace_graph_creates_owner_for_external_canvas_id() -> None:
    eng = get_engine()
    pipeline_id = "test-external-canvas-pipeline"
    result = eng.replace_graph(
        TEST_SCOPE,
        pipeline_id,
        [{"id": "external-source", "name": "source", "node_type": "source"}],
        [],
        name="Alignment pipeline",
    )
    assert result["pipeline_id"] == pipeline_id
    assert eng.get_pipeline(TEST_SCOPE, pipeline_id) is not None


def test_replace_graph_survives_engine_memory_restart() -> None:
    eng = get_engine()
    saved = eng.replace_graph(
        TEST_SCOPE,
        "restart-pipeline",
        [
            {"id": "restart-source", "name": "source", "node_type": "source"},
            {"id": "restart-output", "name": "output", "node_type": "sink"},
        ],
        [{"id": "restart-edge", "source_node_id": "restart-source", "target_node_id": "restart-output"}],
        pipeline_type="Batch",
        write_mode="SNAPSHOT",
    )
    assert saved["persisted"] is True
    revision = saved["revision"]

    eng.reset(scope=TEST_SCOPE, purge_persisted=False)
    reloaded = eng.get_graph(TEST_SCOPE, "restart-pipeline")
    assert reloaded["persisted"] is True
    assert reloaded["revision"] == revision
    assert {node["id"] for node in reloaded["nodes"]} == {"restart-source", "restart-output"}
    assert reloaded["edges"][0]["id"] == "restart-edge"


def test_replace_and_get_graph_return_only_complete_concurrent_snapshots() -> None:
    eng = get_engine()
    pipeline_id = "atomic-pipeline"

    def payload(version: int) -> tuple[list[dict], list[dict]]:
        nodes = [
            {"id": f"atomic-source-{version}", "name": "source", "node_type": "source"},
            {"id": f"atomic-output-{version}", "name": "output", "node_type": "sink"},
        ]
        edges = [{
            "id": f"atomic-edge-{version}",
            "source_node_id": f"atomic-source-{version}",
            "target_node_id": f"atomic-output-{version}",
        }]
        return nodes, edges

    first_nodes, first_edges = payload(0)
    eng.replace_graph(TEST_SCOPE, pipeline_id, first_nodes, first_edges)

    def write_versions() -> None:
        for version in range(1, 8):
            nodes, edges = payload(version)
            eng.replace_graph(TEST_SCOPE, pipeline_id, nodes, edges)

    def read_snapshots() -> list[dict]:
        return [eng.get_graph(TEST_SCOPE, pipeline_id) for _ in range(20)]

    with ThreadPoolExecutor(max_workers=3) as pool:
        writer = pool.submit(write_versions)
        readers = [pool.submit(read_snapshots) for _ in range(2)]
        writer.result()
        snapshots = [snapshot for reader in readers for snapshot in reader.result()]

    for snapshot in snapshots:
        assert snapshot["node_count"] == 2
        assert snapshot["edge_count"] == 1
        node_ids = {node["id"] for node in snapshot["nodes"]}
        edge = snapshot["edges"][0]
        assert edge["source_node_id"] in node_ids
        assert edge["target_node_id"] in node_ids


def test_replace_graph_api_persists_and_rejects_dangling_edge(client, auth_headers) -> None:
    payload = {
        "nodes": [
            {"id": "api-source", "name": "source", "node_type": "source", "position_x": 30, "position_y": 40},
            {"id": "api-output", "name": "output", "node_type": "sink", "position_x": 430, "position_y": 40},
        ],
        "edges": [{"id": "api-edge", "source_node_id": "api-source", "target_node_id": "api-output"}],
        "pipeline_type": "Batch",
        "write_mode": "SNAPSHOT",
        "name": "API canvas",
    }
    pipeline_id = "test-api-canvas-pipeline"
    saved = client.put(f"/v1/pipelines/{pipeline_id}/graph", json=payload, headers=auth_headers)
    assert saved.status_code == 200
    assert saved.json()["persisted"] is True
    assert saved.json()["demo"] is False

    invalid = {**payload, "edges": [{"source_node_id": "api-source", "target_node_id": "missing"}]}
    rejected = client.put(f"/v1/pipelines/{pipeline_id}/graph", json=invalid, headers=auth_headers)
    assert rejected.status_code == 422
    current = client.get(f"/v1/pipelines/{pipeline_id}/graph", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["edge_count"] == 1


def test_pipeline_files() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="My Pipeline")
    eng.add_node(TEST_SCOPE, pl.id, "src", node_type="source")
    tree = eng.get_files(TEST_SCOPE, pl.id)
    assert len(tree) == 1
    assert tree[0]["type"] == "folder"
    assert tree[0]["children"][0]["name"] == "nodes"


def test_node_preview_and_config() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")
    node = eng.add_node(TEST_SCOPE, pl.id, "llm_node", node_type="llm", config={"model": "gpt"})
    preview = eng.preview_node(TEST_SCOPE, pl.id, node.id, limit=5)
    assert preview["node_type"] == "llm"
    assert len(preview["rows"]) == 5
    assert preview["mode"] == "demo"
    assert preview["synthetic"] is True
    cfg = eng.get_node_config(TEST_SCOPE, pl.id, node.id)
    assert cfg["config"]["model"] == "gpt"


def test_proposals_lifecycle() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")
    pp = eng.create_proposal(TEST_SCOPE, pl.id, "Optimize", status="pending")
    assert pp.status == "pending"
    discarded = eng.discard_proposal(TEST_SCOPE, pl.id, pp.id)
    assert discarded.status == "discarded"
    pp2 = eng.create_proposal(TEST_SCOPE, pl.id, "Add field", status="pending")
    approved = eng.approve_proposal(TEST_SCOPE, pl.id, pp2.id)
    assert approved.status == "approved"
    merged = eng.merge_proposal(TEST_SCOPE, pl.id, pp2.id)
    assert merged.status == "merged"


# ═══════════════════════════════════════════
# Pipeline nodes / trial-run / history tests (extra for pipelines group)
# ═══════════════════════════════════════════


def test_trial_run() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")
    node = eng.add_node(TEST_SCOPE, pl.id, "transform", node_type="transform")
    result = eng.trial_run(TEST_SCOPE, pl.id, node.id, sample_input={"x": 1})
    assert result["status"] == "unsupported"
    assert result["error_code"] == "PIPELINE_EXECUTOR_MISSING"
    assert result["output_rows"] == []


def test_pipeline_history() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")  # creates "created" history
    eng.update_pipeline(TEST_SCOPE, pl.id, description="v2")  # creates "updated" history
    history = eng.list_history(TEST_SCOPE, pl.id)
    assert len(history) >= 2
    assert history[0].action in ("created", "updated")


def test_update_node_config() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")
    node = eng.add_node(TEST_SCOPE, pl.id, "n1", node_type="source")
    updated = eng.update_node_config(TEST_SCOPE, pl.id, node.id, {"batch": 500})
    assert updated.config["batch"] == 500


# ═══════════════════════════════════════════
# Schedules tests (9)
# ═══════════════════════════════════════════


def test_create_and_get_schedule() -> None:
    eng = get_engine()
    sc = eng.create_schedule(TEST_SCOPE, name="Nightly", trigger_type="cron", cron_expr="0 2 * * *")
    fetched = eng.get_schedule(TEST_SCOPE, sc.id)
    assert fetched is not None
    assert fetched.name == "Nightly"
    assert fetched.trigger_type == "cron"


def test_list_schedules_filter() -> None:
    eng = get_engine()
    eng.create_schedule(TEST_SCOPE, name="A", trigger_type="cron", status="active")
    eng.create_schedule(TEST_SCOPE, name="B", trigger_type="manual", status="paused")
    items, total = eng.list_schedules(TEST_SCOPE, trigger_type="cron")
    assert total == 1
    assert items[0].trigger_type == "cron"


def test_list_schedules_search() -> None:
    eng = get_engine()
    eng.create_schedule(TEST_SCOPE, name="Daily ETL")
    eng.create_schedule(TEST_SCOPE, name="Weekly Report")
    items, total = eng.list_schedules(TEST_SCOPE, search="daily")
    assert total == 1
    assert items[0].name == "Daily ETL"


def test_update_schedule() -> None:
    eng = get_engine()
    sc = eng.create_schedule(TEST_SCOPE, name="SC")
    updated = eng.update_schedule(TEST_SCOPE, sc.id, cron_expr="0 4 * * *", status="paused")
    assert updated.cron_expr == "0 4 * * *"
    assert updated.status == "paused"


def test_run_schedule() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(TEST_SCOPE, name="PL")
    sc = eng.create_schedule(TEST_SCOPE, name="SC", pipeline_id=pl.id)
    run = eng.run_schedule(TEST_SCOPE, sc.id)
    assert run.status == "unsupported"
    assert run.rows_processed == 0
    runs = eng.list_schedule_runs(TEST_SCOPE, sc.id)
    assert len(runs) == 1


def test_pause_schedule() -> None:
    eng = get_engine()
    sc = eng.create_schedule(TEST_SCOPE, name="SC", status="active")
    paused = eng.pause_schedule(TEST_SCOPE, sc.id)
    assert paused.status == "paused"


def test_get_schedule_not_found() -> None:
    eng = get_engine()
    assert eng.get_schedule(TEST_SCOPE, "nope") is None


def test_schedule_pagination() -> None:
    eng = get_engine()
    for i in range(25):
        eng.create_schedule(TEST_SCOPE, name=f"SC-{i}")
    items, total = eng.list_schedules(TEST_SCOPE, page=1, page_size=10)
    assert total == 25
    assert len(items) == 10
    items2, _ = eng.list_schedules(TEST_SCOPE, page=3, page_size=10)
    assert len(items2) == 5


def test_schedule_run_creates_record() -> None:
    eng = get_engine()
    sc = eng.create_schedule(TEST_SCOPE, name="SC")
    eng.run_schedule(TEST_SCOPE, sc.id)
    eng.run_schedule(TEST_SCOPE, sc.id)
    runs = eng.list_schedule_runs(TEST_SCOPE, sc.id)
    assert len(runs) == 2


# ═══════════════════════════════════════════
# Datasets tests (9)
# ═══════════════════════════════════════════


def test_create_and_get_dataset() -> None:
    eng = get_engine()
    ds = eng.create_dataset(TEST_SCOPE, name="customers", row_count=100)
    fetched = eng.get_dataset(TEST_SCOPE, ds.id)
    assert fetched is not None
    assert fetched.name == "customers"
    assert fetched.row_count == 100


def test_list_datasets_search() -> None:
    eng = get_engine()
    eng.create_dataset(TEST_SCOPE, name="customer_orders")
    eng.create_dataset(TEST_SCOPE, name="product_catalog")
    items, total = eng.list_datasets(TEST_SCOPE, search="customer")
    assert total == 1
    assert items[0].name == "customer_orders"


def test_dataset_preview() -> None:
    eng = get_engine()
    schema = [{"name": "id", "datatype": "int"}, {"name": "label", "datatype": "string"}]
    ds = eng.create_dataset(TEST_SCOPE, name="ds", schema=schema, row_count=500)
    result = eng.preview_dataset(TEST_SCOPE, ds.id, limit=10)
    assert len(result["columns"]) == 2
    assert result["total"] == 500
    assert len(result["rows"]) == 10
    assert result["rows"][0]["id"] == 0
    assert result["mode"] == "demo"
    assert result["synthetic"] is True


def test_dataset_builds() -> None:
    eng = get_engine()
    ds = eng.create_dataset(TEST_SCOPE, name="ds")
    eng.add_build(TEST_SCOPE, ds.id, status="success")
    eng.add_build(TEST_SCOPE, ds.id, status="failed")
    builds = eng.list_builds(TEST_SCOPE, ds.id)
    assert len(builds) == 2


def test_dataset_health() -> None:
    eng = get_engine()
    ds = eng.create_dataset(TEST_SCOPE, name="ds")
    hc = eng.check_health(TEST_SCOPE, ds.id)
    assert hc.status == "healthy"
    latest = eng.get_latest_health(TEST_SCOPE, ds.id)
    assert latest is not None
    assert latest.id == hc.id
    assert hc.mode == "demo"
    assert hc.synthetic is True


def test_sync_config_default() -> None:
    eng = get_engine()
    ds = eng.create_dataset(TEST_SCOPE, name="ds")
    sc = eng.get_sync_config(TEST_SCOPE, ds.id)
    assert sc.mode == "full"
    assert sc.interval_minutes == 60
    assert sc.enabled is True


def test_sync_config_update() -> None:
    eng = get_engine()
    ds = eng.create_dataset(TEST_SCOPE, name="ds")
    sc = eng.set_sync_config(
        TEST_SCOPE, ds.id, mode="incremental", interval_minutes=15
    )
    assert sc.mode == "incremental"
    assert sc.interval_minutes == 15


def test_get_dataset_not_found() -> None:
    eng = get_engine()
    assert eng.get_dataset(TEST_SCOPE, "nope") is None


def test_dataset_preview_datatypes() -> None:
    eng = get_engine()
    schema = [
        {"name": "count", "datatype": "int"},
        {"name": "price", "datatype": "double"},
        {"name": "active", "datatype": "boolean"},
        {"name": "label", "datatype": "string"},
    ]
    ds = eng.create_dataset(TEST_SCOPE, name="ds", schema=schema)
    result = eng.preview_dataset(TEST_SCOPE, ds.id, limit=5)
    row0 = result["rows"][0]
    assert isinstance(row0["count"], int)
    assert isinstance(row0["price"], float)
    assert isinstance(row0["active"], bool)
    assert isinstance(row0["label"], str)
