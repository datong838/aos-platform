"""W1-13 · Data Lineage DAG 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.lineage_graph import LineageError, LineageGraph, LineageNode
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _build_graph() -> LineageGraph:
    g = LineageGraph()
    g.add_node(LineageNode(id="source", type="data_source", name="MySQL"))
    g.add_node(LineageNode(id="raw", type="dataset", name="raw_orders"))
    g.add_node(LineageNode(id="clean", type="dataset", name="clean_orders"))
    g.add_node(LineageNode(id="transform", type="transform", name="clean_pipeline"))
    g.add_node(LineageNode(id="obj", type="ontology_object", name="Order"))
    g.add_edge("source", "raw")
    g.add_edge("raw", "transform")
    g.add_edge("transform", "clean")
    g.add_edge("clean", "obj")
    return g


def test_add_node():
    g = LineageGraph()
    g.add_node(LineageNode(id="n1", type="dataset", name="orders"))
    assert g.node_count == 1


def test_add_node_invalid_type():
    g = LineageGraph()
    with pytest.raises(LineageError) as exc:
        g.add_node(LineageNode(id="n1", type="bogus"))
    assert exc.value.code == "INVALID_NODE_TYPE"


def test_add_edge():
    g = LineageGraph()
    g.add_node(LineageNode(id="a", type="dataset"))
    g.add_node(LineageNode(id="b", type="dataset"))
    g.add_edge("a", "b")
    assert g.edge_count == 1


def test_add_edge_missing_node():
    g = LineageGraph()
    g.add_node(LineageNode(id="a", type="dataset"))
    with pytest.raises(LineageError) as exc:
        g.add_edge("a", "nonexistent")
    assert exc.value.code == "NOT_FOUND"


def test_add_edge_self_loop():
    g = LineageGraph()
    g.add_node(LineageNode(id="a", type="dataset"))
    with pytest.raises(LineageError) as exc:
        g.add_edge("a", "a")
    assert exc.value.code == "SELF_LOOP"


def test_upstream():
    g = _build_graph()
    upstream = g.get_upstream("clean")
    assert "transform" in upstream
    assert "raw" in upstream
    assert "source" in upstream


def test_downstream():
    g = _build_graph()
    downstream = g.get_downstream("raw")
    assert "transform" in downstream
    assert "clean" in downstream
    assert "obj" in downstream


def test_upstream_depth_limit():
    g = _build_graph()
    upstream = g.get_upstream("clean", depth=1)
    assert upstream == ["transform"]


def test_topological_sort():
    g = _build_graph()
    order = g.topological_sort()
    assert order.index("source") < order.index("raw")
    assert order.index("raw") < order.index("transform")
    assert order.index("transform") < order.index("clean")
    assert order.index("clean") < order.index("obj")


def test_cycle_detection():
    g = LineageGraph()
    g.add_node(LineageNode(id="a", type="dataset"))
    g.add_node(LineageNode(id="b", type="dataset"))
    g.add_edge("a", "b")
    g.add_edge("b", "a")
    assert g.has_cycle() is True
    with pytest.raises(LineageError) as exc:
        g.topological_sort()
    assert exc.value.code == "CYCLE_DETECTED"


def test_no_cycle():
    g = _build_graph()
    assert g.has_cycle() is False


def test_color_by_type():
    g = _build_graph()
    colors = g.color_nodes("type")
    assert colors["source"] == "data_source"
    assert colors["raw"] == "dataset"
    assert colors["obj"] == "ontology_object"


def test_to_dict():
    g = _build_graph()
    d = g.to_dict()
    assert len(d["nodes"]) == 5
    assert len(d["edges"]) == 4


# --- API --- #
@pytest.fixture()
def client(monkeypatch):
    from aos_api.lineage_graph import LineageGraph as LG
    fresh = LG()
    monkeypatch.setattr("aos_api.routers.lineage.get_graph", lambda: fresh)
    return TestClient(create_app())


def test_api_add_node(client):
    resp = client.post("/v1/lineage/nodes", json={"id": "n1", "type": "dataset", "name": "orders"}, headers=_H)
    assert resp.status_code == 200


def test_api_add_edge(client):
    client.post("/v1/lineage/nodes", json={"id": "a", "type": "dataset"}, headers=_H)
    client.post("/v1/lineage/nodes", json={"id": "b", "type": "dataset"}, headers=_H)
    resp = client.post("/v1/lineage/edges", json={"source": "a", "target": "b"}, headers=_H)
    assert resp.status_code == 200


def test_api_upstream(client):
    for nid in ["a", "b", "c"]:
        client.post("/v1/lineage/nodes", json={"id": nid, "type": "dataset"}, headers=_H)
    client.post("/v1/lineage/edges", json={"source": "a", "target": "b"}, headers=_H)
    client.post("/v1/lineage/edges", json={"source": "b", "target": "c"}, headers=_H)
    resp = client.get("/v1/lineage/c/upstream", headers=_H)
    assert resp.status_code == 200
    assert "a" in resp.json()["nodes"]


def test_api_graph(client):
    client.post("/v1/lineage/nodes", json={"id": "x", "type": "dataset"}, headers=_H)
    resp = client.get("/v1/lineage/graph", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["nodes"]) >= 1


def test_api_color(client):
    client.post("/v1/lineage/nodes", json={"id": "x", "type": "dataset", "name": "orders"}, headers=_H)
    resp = client.post("/v1/lineage/color?by=type", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["colors"]["x"] == "dataset"
