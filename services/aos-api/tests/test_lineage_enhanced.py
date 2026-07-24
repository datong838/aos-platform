"""W2-#4 · Lineage 增强测试（列级血缘 + 22 色 + 布局）。"""
from __future__ import annotations

import pytest

from aos_api.lineage_graph import LineageGraph, LineageNode, get_graph
from aos_api.lineage_views import (
    NODE_KIND_4,
    PALETTE_22,
    ColumnLineage,
    LineageLayout,
    LineageViewError,
    LineageViewService,
    color_by_type,
    compute_layout,
    list_node_kinds,
    list_palette,
)


@pytest.fixture
def graph_with_data() -> LineageGraph:
    get_graph()._nodes.clear()
    get_graph()._adj.clear()
    get_graph()._radj.clear()
    g = get_graph()
    g.add_node(LineageNode(id="ds1", type="dataset", name="订单源"))
    g.add_node(LineageNode(id="tf1", type="transform", name="清洗"))
    g.add_node(LineageNode(id="obj1", type="ontology_object", name="订单对象"))
    g.add_edge("ds1", "tf1")
    g.add_edge("tf1", "obj1")
    return g


# ---------- 22 色调色板 ----------


def test_palette_has_at_least_seven_types():
    assert len(PALETTE_22) >= 7
    assert "dataset" in PALETTE_22
    assert "llm" in PALETTE_22


def test_list_palette_returns_dicts():
    items = list_palette()
    assert all("type" in item and "color" in item for item in items)


def test_color_by_type_returns_hex():
    color = color_by_type("dataset")
    assert color.startswith("#")
    assert color_by_type("bogus") == "#6b7280"


# ---------- 4 种节点映射 ----------


def test_node_kind_4_maps_to_four_categories():
    kinds = {v for v in NODE_KIND_4.values()}
    assert kinds == {"source", "transform", "sink"}


def test_list_node_kinds_complete():
    items = list_node_kinds()
    assert len(items) >= 6
    raw_types = {item["raw_type"] for item in items}
    assert "dataset" in raw_types


# ---------- 布局 ----------


def test_compute_layout_assigns_coordinates(graph_with_data: LineageGraph):
    layout = compute_layout(graph_with_data)
    assert isinstance(layout, LineageLayout)
    assert len(layout.nodes) == 3
    assert all(n.x >= 0 and n.y >= 0 for n in layout.nodes)
    assert layout.layer_count >= 2


def test_layout_layers_topological(graph_with_data: LineageGraph):
    layout = compute_layout(graph_with_data)
    ds = next(n for n in layout.nodes if n.id == "ds1")
    tf = next(n for n in layout.nodes if n.id == "tf1")
    obj = next(n for n in layout.nodes if n.id == "obj1")
    assert ds.layer < tf.layer < obj.layer


def test_layout_includes_colors(graph_with_data: LineageGraph):
    layout = compute_layout(graph_with_data)
    for node in layout.nodes:
        assert node.color.startswith("#")


def test_layout_width_height_positive(graph_with_data: LineageGraph):
    layout = compute_layout(graph_with_data)
    assert layout.width > 0
    assert layout.height > 0


# ---------- 列级血缘 ----------


def test_column_lineage_set_and_get(graph_with_data: LineageGraph):
    svc = LineageViewService(graph_with_data)
    cols = [ColumnLineage(source_columns=["amount"], target_column="total", transform_expr="amount * 2")]
    svc.set_column_lineage("ds1", "tf1", cols)
    result = svc.get_column_lineage("ds1", "tf1")
    assert len(result) == 1
    assert result[0].target_column == "total"


def test_column_lineage_empty_default(graph_with_data: LineageGraph):
    svc = LineageViewService(graph_with_data)
    assert svc.get_column_lineage("x", "y") == []


# ---------- 视图服务 ----------


def test_service_color_by_type(graph_with_data: LineageGraph):
    svc = LineageViewService(graph_with_data)
    colors = svc.color("type")
    assert "ds1" in colors
    assert colors["ds1"] == PALETTE_22["dataset"]


def test_service_color_by_depth(graph_with_data: LineageGraph):
    svc = LineageViewService(graph_with_data)
    colors = svc.color("depth")
    assert "ds1" in colors


def test_service_color_bad_by_raises(graph_with_data: LineageGraph):
    svc = LineageViewService(graph_with_data)
    with pytest.raises(LineageViewError) as exc:
        svc.color("bogus")
    assert exc.value.code == "BAD_BY"


def test_service_summary(graph_with_data: LineageGraph):
    svc = LineageViewService(graph_with_data)
    summary = svc.summary()
    assert summary["node_count"] == 3
    assert summary["edge_count"] == 2
    assert summary["kind_4_counts"]["source"] == 1


def test_service_layout_with_columns(graph_with_data: LineageGraph):
    svc = LineageViewService(graph_with_data)
    svc.set_column_lineage("ds1", "tf1", [
        ColumnLineage(source_columns=["a"], target_column="b"),
    ])
    layout = svc.layout()
    edge = next(e for e in layout.edges if e.source == "ds1" and e.target == "tf1")
    assert len(edge.columns) == 1
