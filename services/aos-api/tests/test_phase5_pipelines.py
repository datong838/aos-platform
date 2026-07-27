"""Phase 5 · Pipeline Core API — 单元测试 (≥27).

Tests for phase5_pipeline_engine, phase5_pipelines, phase5_schedules, phase5_datasets.
"""
from __future__ import annotations

import pytest

from aos_api.phase5_pipeline_engine import get_engine


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


# ═══════════════════════════════════════════
# Pipelines tests (9)
# ═══════════════════════════════════════════


def test_create_and_get_pipeline() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(name="ETL-1", pipeline_type="ETL", status="active")
    fetched = eng.get_pipeline(pl.id)
    assert fetched is not None
    assert fetched.name == "ETL-1"
    assert fetched.pipeline_type == "ETL"


def test_list_pipelines_with_filter() -> None:
    eng = get_engine()
    eng.create_pipeline(name="A", status="active")
    eng.create_pipeline(name="B", status="draft")
    eng.create_pipeline(name="C", status="active")
    items, total = eng.list_pipelines(status="active")
    assert total == 2
    assert all(p.status == "active" for p in items)


def test_list_pipelines_search() -> None:
    eng = get_engine()
    eng.create_pipeline(name="customer_etl")
    eng.create_pipeline(name="orders_elt")
    items, total = eng.list_pipelines(search="customer")
    assert total == 1
    assert items[0].name == "customer_etl"


def test_update_pipeline() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(name="PL")
    updated = eng.update_pipeline(pl.id, status="active", description="updated")
    assert updated.status == "active"
    assert updated.description == "updated"


def test_get_pipeline_not_found() -> None:
    eng = get_engine()
    assert eng.get_pipeline("nope") is None


def test_pipeline_graph() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(name="PL")
    n1 = eng.add_node(pl.id, "src", node_type="source")
    n2 = eng.add_node(pl.id, "sink", node_type="sink")
    eng.add_edge(pl.id, n1.id, n2.id)
    graph = eng.get_graph(pl.id)
    assert graph["node_count"] == 2
    assert graph["edge_count"] == 1


def test_pipeline_files() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(name="My Pipeline")
    eng.add_node(pl.id, "src", node_type="source")
    tree = eng.get_files(pl.id)
    assert len(tree) == 1
    assert tree[0]["type"] == "folder"
    assert tree[0]["children"][0]["name"] == "nodes"


def test_node_preview_and_config() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(name="PL")
    node = eng.add_node(pl.id, "llm_node", node_type="llm", config={"model": "gpt"})
    preview = eng.preview_node(pl.id, node.id, limit=5)
    assert preview["node_type"] == "llm"
    assert len(preview["rows"]) == 5
    cfg = eng.get_node_config(pl.id, node.id)
    assert cfg["config"]["model"] == "gpt"


def test_proposals_lifecycle() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(name="PL")
    pp = eng.create_proposal(pl.id, "Optimize", status="pending")
    assert pp.status == "pending"
    discarded = eng.discard_proposal(pl.id, pp.id)
    assert discarded.status == "discarded"
    pp2 = eng.create_proposal(pl.id, "Add field", status="pending")
    merged = eng.merge_proposal(pl.id, pp2.id)
    assert merged.status == "merged"


# ═══════════════════════════════════════════
# Pipeline nodes / trial-run / history tests (extra for pipelines group)
# ═══════════════════════════════════════════


def test_trial_run() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(name="PL")
    node = eng.add_node(pl.id, "transform", node_type="transform")
    result = eng.trial_run(pl.id, node.id, sample_input={"x": 1})
    assert result["status"] == "ok"
    assert len(result["output_rows"]) == 3


def test_pipeline_history() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(name="PL")  # creates "created" history
    eng.update_pipeline(pl.id, description="v2")  # creates "updated" history
    history = eng.list_history(pl.id)
    assert len(history) >= 2
    assert history[0].action in ("created", "updated")


def test_update_node_config() -> None:
    eng = get_engine()
    pl = eng.create_pipeline(name="PL")
    node = eng.add_node(pl.id, "n1", node_type="source")
    updated = eng.update_node_config(pl.id, node.id, {"batch": 500})
    assert updated.config["batch"] == 500


# ═══════════════════════════════════════════
# Schedules tests (9)
# ═══════════════════════════════════════════


def test_create_and_get_schedule() -> None:
    eng = get_engine()
    sc = eng.create_schedule(name="Nightly", trigger_type="cron", cron_expr="0 2 * * *")
    fetched = eng.get_schedule(sc.id)
    assert fetched is not None
    assert fetched.name == "Nightly"
    assert fetched.trigger_type == "cron"


def test_list_schedules_filter() -> None:
    eng = get_engine()
    eng.create_schedule(name="A", trigger_type="cron", status="active")
    eng.create_schedule(name="B", trigger_type="manual", status="paused")
    items, total = eng.list_schedules(trigger_type="cron")
    assert total == 1
    assert items[0].trigger_type == "cron"


def test_list_schedules_search() -> None:
    eng = get_engine()
    eng.create_schedule(name="Daily ETL")
    eng.create_schedule(name="Weekly Report")
    items, total = eng.list_schedules(search="daily")
    assert total == 1
    assert items[0].name == "Daily ETL"


def test_update_schedule() -> None:
    eng = get_engine()
    sc = eng.create_schedule(name="SC")
    updated = eng.update_schedule(sc.id, cron_expr="0 4 * * *", status="paused")
    assert updated.cron_expr == "0 4 * * *"
    assert updated.status == "paused"


def test_run_schedule() -> None:
    eng = get_engine()
    sc = eng.create_schedule(name="SC")
    run = eng.run_schedule(sc.id)
    assert run.status == "success"
    assert run.rows_processed > 0
    runs = eng.list_schedule_runs(sc.id)
    assert len(runs) == 1


def test_pause_schedule() -> None:
    eng = get_engine()
    sc = eng.create_schedule(name="SC", status="active")
    paused = eng.pause_schedule(sc.id)
    assert paused.status == "paused"


def test_get_schedule_not_found() -> None:
    eng = get_engine()
    assert eng.get_schedule("nope") is None


def test_schedule_pagination() -> None:
    eng = get_engine()
    for i in range(25):
        eng.create_schedule(name=f"SC-{i}")
    items, total = eng.list_schedules(page=1, page_size=10)
    assert total == 25
    assert len(items) == 10
    items2, _ = eng.list_schedules(page=3, page_size=10)
    assert len(items2) == 5


def test_schedule_run_creates_record() -> None:
    eng = get_engine()
    sc = eng.create_schedule(name="SC")
    eng.run_schedule(sc.id)
    eng.run_schedule(sc.id)
    runs = eng.list_schedule_runs(sc.id)
    assert len(runs) == 2


# ═══════════════════════════════════════════
# Datasets tests (9)
# ═══════════════════════════════════════════


def test_create_and_get_dataset() -> None:
    eng = get_engine()
    ds = eng.create_dataset(name="customers", row_count=100)
    fetched = eng.get_dataset(ds.id)
    assert fetched is not None
    assert fetched.name == "customers"
    assert fetched.row_count == 100


def test_list_datasets_search() -> None:
    eng = get_engine()
    eng.create_dataset(name="customer_orders")
    eng.create_dataset(name="product_catalog")
    items, total = eng.list_datasets(search="customer")
    assert total == 1
    assert items[0].name == "customer_orders"


def test_dataset_preview() -> None:
    eng = get_engine()
    schema = [{"name": "id", "datatype": "int"}, {"name": "label", "datatype": "string"}]
    ds = eng.create_dataset(name="ds", schema=schema, row_count=500)
    result = eng.preview_dataset(ds.id, limit=10)
    assert len(result["columns"]) == 2
    assert result["total"] == 500
    assert len(result["rows"]) == 10
    assert result["rows"][0]["id"] == 0


def test_dataset_builds() -> None:
    eng = get_engine()
    ds = eng.create_dataset(name="ds")
    b1 = eng.add_build(ds.id, status="success")
    b2 = eng.add_build(ds.id, status="failed")
    builds = eng.list_builds(ds.id)
    assert len(builds) == 2


def test_dataset_health() -> None:
    eng = get_engine()
    ds = eng.create_dataset(name="ds")
    hc = eng.check_health(ds.id)
    assert hc.status == "healthy"
    latest = eng.get_latest_health(ds.id)
    assert latest is not None
    assert latest.id == hc.id


def test_sync_config_default() -> None:
    eng = get_engine()
    ds = eng.create_dataset(name="ds")
    sc = eng.get_sync_config(ds.id)
    assert sc.mode == "full"
    assert sc.interval_minutes == 60
    assert sc.enabled is True


def test_sync_config_update() -> None:
    eng = get_engine()
    ds = eng.create_dataset(name="ds")
    sc = eng.set_sync_config(ds.id, mode="incremental", interval_minutes=15)
    assert sc.mode == "incremental"
    assert sc.interval_minutes == 15


def test_get_dataset_not_found() -> None:
    eng = get_engine()
    assert eng.get_dataset("nope") is None


def test_dataset_preview_datatypes() -> None:
    eng = get_engine()
    schema = [
        {"name": "count", "datatype": "int"},
        {"name": "price", "datatype": "double"},
        {"name": "active", "datatype": "boolean"},
        {"name": "label", "datatype": "string"},
    ]
    ds = eng.create_dataset(name="ds", schema=schema)
    result = eng.preview_dataset(ds.id, limit=5)
    row0 = result["rows"][0]
    assert isinstance(row0["count"], int)
    assert isinstance(row0["price"], float)
    assert isinstance(row0["active"], bool)
    assert isinstance(row0["label"], str)
