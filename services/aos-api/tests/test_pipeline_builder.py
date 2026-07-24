"""W1-14 · Pipeline Builder DAG 编辑器单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.pipeline_builder import (
    MAX_UNDO,
    Pipeline,
    PipelineEditor,
    PipelineEditorError,
    PipelineStore,
)

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _new_editor() -> PipelineEditor:
    return PipelineEditor(Pipeline(id="p1", name="test"))


def _add_dataset(ed: PipelineEditor, nid: str, label: str = "ds") -> None:
    ed.apply({"action": "add_node", "node": {"id": nid, "kind": "dataset", "label": label}})


def _add_transform(ed: PipelineEditor, nid: str, op: str, config: dict | None = None) -> None:
    ed.apply({
        "action": "add_node",
        "node": {"id": nid, "kind": "transform", "label": nid, "op": op, "config": config or {}},
    })


# --- 引擎：节点 --- #

def test_create_empty_pipeline():
    ed = _new_editor()
    assert ed.pipeline.name == "test"
    assert ed.pipeline.nodes == []


def test_apply_add_node():
    ed = _new_editor()
    ed.apply({"action": "add_node", "node": {"id": "n1", "kind": "dataset", "label": "users"}})
    assert len(ed.pipeline.nodes) == 1
    assert ed.pipeline.nodes[0].id == "n1"
    assert ed.pipeline.version == 2


def test_apply_add_node_dup_id():
    ed = _new_editor()
    _add_dataset(ed, "n1")
    with pytest.raises(PipelineEditorError) as exc:
        ed.apply({"action": "add_node", "node": {"id": "n1", "kind": "dataset", "label": "dup"}})
    assert exc.value.code == "NODE_DUP_ID"


def test_apply_update_node_not_found():
    ed = _new_editor()
    with pytest.raises(PipelineEditorError) as exc:
        ed.apply({"action": "update_node", "node_id": "ghost", "patch": {"label": "x"}})
    assert exc.value.code == "NODE_NOT_FOUND"


def test_apply_update_node_success():
    ed = _new_editor()
    _add_dataset(ed, "n1", "v1")
    ed.apply({"action": "update_node", "node_id": "n1", "patch": {"label": "v2"}})
    assert ed.pipeline.nodes[0].label == "v2"


def test_apply_remove_node_with_edges():
    ed = _new_editor()
    _add_dataset(ed, "a")
    _add_dataset(ed, "b")
    ed.apply({"action": "add_edge", "edge": {"src": "a", "dst": "b"}})
    ed.apply({"action": "remove_node", "node_id": "a"})
    assert all(n.id != "a" for n in ed.pipeline.nodes)
    assert all(e.src != "a" and e.dst != "a" for e in ed.pipeline.edges)


# --- 引擎：边 --- #

def test_apply_add_edge():
    ed = _new_editor()
    _add_dataset(ed, "a")
    _add_dataset(ed, "b")
    ed.apply({"action": "add_edge", "edge": {"src": "a", "dst": "b"}})
    assert len(ed.pipeline.edges) == 1


def test_apply_add_edge_src_missing():
    ed = _new_editor()
    _add_dataset(ed, "b")
    with pytest.raises(PipelineEditorError) as exc:
        ed.apply({"action": "add_edge", "edge": {"src": "ghost", "dst": "b"}})
    assert exc.value.code == "EDGE_SRC_MISSING"


def test_apply_add_edge_self_loop():
    ed = _new_editor()
    _add_dataset(ed, "a")
    with pytest.raises(PipelineEditorError) as exc:
        ed.apply({"action": "add_edge", "edge": {"src": "a", "dst": "a"}})
    assert exc.value.code == "EDGE_SELF_LOOP"


def test_apply_add_edge_cycle():
    ed = _new_editor()
    _add_dataset(ed, "a")
    _add_dataset(ed, "b")
    ed.apply({"action": "add_edge", "edge": {"src": "a", "dst": "b"}})
    with pytest.raises(PipelineEditorError) as exc:
        ed.apply({"action": "add_edge", "edge": {"src": "b", "dst": "a"}})
    assert exc.value.code == "CYCLE_DETECTED"


def test_apply_add_edge_dup_silent():
    ed = _new_editor()
    _add_dataset(ed, "a")
    _add_dataset(ed, "b")
    ed.apply({"action": "add_edge", "edge": {"src": "a", "dst": "b"}})
    ed.apply({"action": "add_edge", "edge": {"src": "a", "dst": "b"}})
    assert len(ed.pipeline.edges) == 1


# --- 引擎：撤销/重做 --- #

def test_undo():
    ed = _new_editor()
    _add_dataset(ed, "n1")
    assert len(ed.pipeline.nodes) == 1
    ed.undo()
    assert len(ed.pipeline.nodes) == 0


def test_redo():
    ed = _new_editor()
    _add_dataset(ed, "n1")
    ed.undo()
    ed.redo()
    assert len(ed.pipeline.nodes) == 1


def test_new_apply_clears_redo():
    ed = _new_editor()
    _add_dataset(ed, "n1")
    ed.undo()
    _add_dataset(ed, "n2")
    with pytest.raises(PipelineEditorError) as exc:
        ed.redo()
    assert exc.value.code == "REDO_EMPTY"


def test_undo_empty():
    ed = _new_editor()
    with pytest.raises(PipelineEditorError) as exc:
        ed.undo()
    assert exc.value.code == "UNDO_EMPTY"


def test_undo_stack_cap():
    ed = _new_editor()
    for i in range(MAX_UNDO + 10):
        _add_dataset(ed, f"n{i}")
    assert len(ed._undo_stack) == MAX_UNDO


# --- 引擎：校验 --- #

def test_validate_clean():
    ed = _new_editor()
    _add_dataset(ed, "a")
    _add_transform(ed, "t1", "filter", {"expression": "true"})
    ed.apply({"action": "add_edge", "edge": {"src": "a", "dst": "t1"}})
    assert ed.validate() == []


def test_validate_missing_op():
    ed = _new_editor()
    ed.pipeline.nodes.append(_mk_node("t1", kind="transform", op=None))
    errs = ed.validate()
    assert any("TRANSFORM_NO_OP" in e for e in errs)


def test_validate_bad_op():
    ed = _new_editor()
    ed.pipeline.nodes.append(_mk_node("t1", kind="transform", op="bogus"))
    errs = ed.validate()
    assert any("TRANSFORM_BAD_OP" in e for e in errs)


def _mk_node(nid: str, kind: str = "dataset", op: str | None = None, label: str = "x"):
    from aos_api.pipeline_builder import PipelineNode
    return PipelineNode(id=nid, kind=kind, op=op, label=label)


# --- 引擎：节点校验错误 --- #

def test_transform_no_op():
    ed = _new_editor()
    with pytest.raises(PipelineEditorError) as exc:
        ed.apply({"action": "add_node", "node": {"id": "t1", "kind": "transform", "label": "x"}})
    assert exc.value.code == "TRANSFORM_NO_OP"


def test_transform_bad_op():
    ed = _new_editor()
    with pytest.raises(PipelineEditorError) as exc:
        ed.apply({"action": "add_node", "node": {"id": "t1", "kind": "transform", "op": "bogus"}})
    assert exc.value.code == "TRANSFORM_BAD_OP"


def test_dataset_no_rid_no_label():
    ed = _new_editor()
    with pytest.raises(PipelineEditorError) as exc:
        ed.apply({"action": "add_node", "node": {"id": "d1", "kind": "dataset"}})
    assert exc.value.code == "DATASET_NO_RID"


# --- 引擎：预览 --- #

def test_preview_single_chain():
    ed = _new_editor()
    _add_dataset(ed, "src")
    _add_transform(ed, "flt", "filter", {"expression": "amount > 100"})
    ed.apply({"action": "add_edge", "edge": {"src": "src", "dst": "flt"}})
    inputs = {"src": [{"amount": 50}, {"amount": 200}, {"amount": 300}]}
    out = ed.preview(inputs)
    assert len(out["src"]) == 3
    assert len(out["flt"]) == 2


def test_preview_multi_upstream_merge():
    ed = _new_editor()
    _add_dataset(ed, "s1")
    _add_dataset(ed, "s2")
    _add_transform(ed, "u", "union")
    ed.apply({"action": "add_edge", "edge": {"src": "s1", "dst": "u"}})
    ed.apply({"action": "add_edge", "edge": {"src": "s2", "dst": "u"}})
    inputs = {"s1": [{"id": 1}], "s2": [{"id": 2}, {"id": 3}]}
    out = ed.preview(inputs)
    assert len(out["u"]) == 3


def test_preview_empty_input():
    ed = _new_editor()
    _add_dataset(ed, "src")
    _add_transform(ed, "flt", "filter", {"expression": "true"})
    ed.apply({"action": "add_edge", "edge": {"src": "src", "dst": "flt"}})
    out = ed.preview({})
    assert out["src"] == []
    assert out["flt"] == []


def test_preview_validation_failure():
    ed = _new_editor()
    ed.pipeline.nodes.append(_mk_node("t1", kind="transform", op="bogus"))
    with pytest.raises(PipelineEditorError) as exc:
        ed.preview({})
    assert exc.value.code == "VALIDATION_FAILED"


# --- 引擎：批量 --- #

def test_batch_command():
    ed = _new_editor()
    ed.apply({"action": "batch", "commands": [
        {"action": "add_node", "node": {"id": "a", "kind": "dataset", "label": "a"}},
        {"action": "add_node", "node": {"id": "b", "kind": "dataset", "label": "b"}},
        {"action": "add_edge", "edge": {"src": "a", "dst": "b"}},
    ]})
    assert len(ed.pipeline.nodes) == 2
    assert len(ed.pipeline.edges) == 1


def test_batch_atomic_rollback():
    ed = _new_editor()
    with pytest.raises(PipelineEditorError):
        ed.apply({"action": "batch", "commands": [
            {"action": "add_node", "node": {"id": "a", "kind": "dataset", "label": "a"}},
            {"action": "add_node", "node": {"id": "a", "kind": "dataset", "label": "dup"}},
        ]})
    assert len(ed.pipeline.nodes) == 0


# --- Store --- #

def test_store_lifecycle():
    store = PipelineStore()
    p = store.create("demo")
    assert p.name == "demo"
    assert store.get(p.id).id == p.id
    assert len(store.list_all()) == 1
    store.delete(p.id)
    with pytest.raises(PipelineEditorError):
        store.get(p.id)


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    fresh = PipelineStore()
    monkeypatch.setattr("aos_api.routers.pipelines.get_store", lambda: fresh)
    return TestClient(create_app())


def test_api_create_pipeline(client):
    resp = client.post("/v1/pipeline-builder", json={"name": "demo"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["name"] == "demo"


def test_api_list_pipelines(client):
    client.post("/v1/pipeline-builder", json={"name": "a"}, headers=_H)
    client.post("/v1/pipeline-builder", json={"name": "b"}, headers=_H)
    resp = client.get("/v1/pipeline-builder", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["pipelines"]) == 2


def test_api_apply_and_get(client):
    pid = client.post("/v1/pipeline-builder", json={"name": "x"}, headers=_H).json()["id"]
    resp = client.post(f"/v1/pipeline-builder/{pid}/apply", json={
        "command": {"action": "add_node", "node": {"id": "n1", "kind": "dataset", "label": "d"}}
    }, headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["nodes"]) == 1


def test_api_undo(client):
    pid = client.post("/v1/pipeline-builder", json={"name": "x"}, headers=_H).json()["id"]
    client.post(f"/v1/pipeline-builder/{pid}/apply", json={
        "command": {"action": "add_node", "node": {"id": "n1", "kind": "dataset", "label": "d"}}
    }, headers=_H)
    resp = client.post(f"/v1/pipeline-builder/{pid}/undo", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["nodes"] == []


def test_api_preview(client):
    pid = client.post("/v1/pipeline-builder", json={"name": "x"}, headers=_H).json()["id"]
    client.post(f"/v1/pipeline-builder/{pid}/apply", json={"command": {
        "action": "add_node", "node": {"id": "src", "kind": "dataset", "label": "src"}}}, headers=_H)
    client.post(f"/v1/pipeline-builder/{pid}/apply", json={"command": {
        "action": "add_node", "node": {"id": "flt", "kind": "transform", "op": "filter",
                                       "config": {"expression": "amount > 100"}}}}, headers=_H)
    client.post(f"/v1/pipeline-builder/{pid}/apply", json={"command": {
        "action": "add_edge", "edge": {"src": "src", "dst": "flt"}}}, headers=_H)
    resp = client.post(f"/v1/pipeline-builder/{pid}/preview", json={
        "inputs": {"src": [{"amount": 50}, {"amount": 200}]}
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["counts"]["flt"] == 1


def test_api_validate(client):
    pid = client.post("/v1/pipeline-builder", json={"name": "x"}, headers=_H).json()["id"]
    resp = client.post(f"/v1/pipeline-builder/{pid}/validate", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["errors"] == []


def test_api_delete(client):
    pid = client.post("/v1/pipeline-builder", json={"name": "x"}, headers=_H).json()["id"]
    resp = client.delete(f"/v1/pipeline-builder/{pid}", headers=_H)
    assert resp.status_code == 200
    resp2 = client.get(f"/v1/pipeline-builder/{pid}", headers=_H)
    assert resp2.status_code == 404


def test_api_404(client):
    resp = client.get("/v1/pipeline-builder/nonexistent", headers=_H)
    assert resp.status_code == 404
