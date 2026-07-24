"""W2-#12 · OE 探索图表可视化测试。"""
from __future__ import annotations

import pytest

from aos_api.object_explorer import (
    CHART_CATALOG,
    ExplorerDesign,
    ExplorerError,
    ExplorerFilter,
    ExplorerMetric,
    ObjectExplorerStore,
    list_chart_catalog,
)


@pytest.fixture
def store() -> ObjectExplorerStore:
    return ObjectExplorerStore()


def _sample_rows() -> list[dict]:
    return [
        {"city": "北京", "amount": 100, "status": "done"},
        {"city": "北京", "amount": 200, "status": "pending"},
        {"city": "上海", "amount": 150, "status": "done"},
        {"city": "上海", "amount": 50, "status": "cancelled"},
    ]


def test_chart_catalog_has_seven_kinds():
    catalog = list_chart_catalog()
    assert len(catalog) == 7


def test_create_design(store: ObjectExplorerStore):
    design = ExplorerDesign(name="城市分析", otd_id="otd-1", chart_kind="bar")
    created = store.create(design)
    assert created.id in {d.id for d in store.list_all()}


def test_create_missing_name_raises(store: ObjectExplorerStore):
    with pytest.raises(ExplorerError) as exc:
        store.create(ExplorerDesign(name="", otd_id="otd-1", chart_kind="bar"))
    assert exc.value.code == "MISSING_NAME"


def test_create_unknown_chart_raises(store: ObjectExplorerStore):
    design = ExplorerDesign.model_construct(name="d", otd_id="otd-1", chart_kind="bogus")
    with pytest.raises(ExplorerError) as exc:
        store.create(design)
    assert exc.value.code == "UNKNOWN_CHART"


def test_render_with_group_by_and_metric(store: ObjectExplorerStore):
    design = store.create(ExplorerDesign(
        name="城市金额",
        otd_id="otd-1",
        chart_kind="bar",
        group_by="city",
        metrics=[ExplorerMetric(field="amount", agg="sum")],
    ))
    result = store.render(design.id, _sample_rows())
    series_by_city = {s["city"]: s for s in result["series"]}
    assert series_by_city["北京"]["amount_sum"] == 300
    assert series_by_city["上海"]["amount_sum"] == 200
    assert result["chart_kind"] == "bar"


def test_render_count_metric(store: ObjectExplorerStore):
    design = store.create(ExplorerDesign(
        name="计数",
        otd_id="otd-1",
        chart_kind="pie",
        group_by="status",
        metrics=[ExplorerMetric(field="amount", agg="count")],
    ))
    result = store.render(design.id, _sample_rows())
    status_counts = {s["status"]: s["amount_count"] for s in result["series"]}
    assert status_counts["done"] == 2
    assert status_counts["pending"] == 1


def test_render_with_filters(store: ObjectExplorerStore):
    design = store.create(ExplorerDesign(
        name="过滤",
        otd_id="otd-1",
        chart_kind="table",
        filters=[ExplorerFilter(field="city", expr="city == \"北京\"")],
    ))
    result = store.render(design.id, _sample_rows())
    assert result["total"] == 2
    assert all(r["city"] == "北京" for r in result["series"])


def test_render_no_group_by_returns_all_rows(store: ObjectExplorerStore):
    design = store.create(ExplorerDesign(name="全量", otd_id="otd-1", chart_kind="table"))
    result = store.render(design.id, _sample_rows())
    assert result["total"] == 4


def test_undo_redo_flow(store: ObjectExplorerStore):
    design = store.create(ExplorerDesign(name="d", otd_id="otd-1", chart_kind="bar"))
    store.update(design.id, name="v2")
    assert store.get(design.id).name == "v2"
    undone = store.undo(design.id)
    assert undone.name == "d"
    redone = store.redo(design.id)
    assert redone.name == "v2"


def test_undo_empty_raises(store: ObjectExplorerStore):
    design = store.create(ExplorerDesign(name="d", otd_id="otd-1", chart_kind="bar"))
    with pytest.raises(ExplorerError) as exc:
        store.undo(design.id)
    assert exc.value.code == "UNDO_EMPTY"


def test_delete_design(store: ObjectExplorerStore):
    design = store.create(ExplorerDesign(name="d", otd_id="otd-1", chart_kind="bar"))
    assert store.delete(design.id) is True
    assert store.get(design.id) is None


def test_list_by_otd(store: ObjectExplorerStore):
    store.create(ExplorerDesign(name="a", otd_id="otd-1", chart_kind="bar"))
    store.create(ExplorerDesign(name="b", otd_id="otd-2", chart_kind="line"))
    assert len(store.list_by_otd("otd-1")) == 1


def test_render_unknown_design_raises(store: ObjectExplorerStore):
    with pytest.raises(ExplorerError) as exc:
        store.render("ghost", [])
    assert exc.value.code == "NOT_FOUND"
