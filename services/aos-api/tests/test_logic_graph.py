"""W2-#17 · Logic Wiki 字段 + LangGraph 图编排 单元测试。

详见 docs/palantier/20_tech/220tech_w2-f-funnel-logic-writeback.md §2.2。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.logic_engine import (
    Block,
    GraphEdge,
    LogicEngine,
    LogicGraph,
)
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-graph",
}


def _mock_chat(query: str, **kw) -> dict:
    return {"answer": f"mock:{query[:40]}", "provider": "mock"}


# --------------------------------------------------------------------------- #
# Wiki 字段注入
# --------------------------------------------------------------------------- #
def test_wiki_ref_injected_into_variables():
    def loader(ref):
        return "wiki-doc-content" if ref == "doc-1" else None

    eng = LogicEngine(chat_fn=_mock_chat, wiki_loader=loader)
    blk = Block(id="b1", kind="input", config={"x": 1}, wiki_ref="doc-1")
    ctx = eng.run([blk], {})
    assert ctx.variables["_wiki_b1"] == "wiki-doc-content"


def test_wiki_ref_none_not_injected():
    eng = LogicEngine(chat_fn=_mock_chat)
    blk = Block(id="b1", kind="input", config={"x": 1})
    ctx = eng.run([blk], {})
    assert "_wiki_b1" not in ctx.variables


def test_wiki_loader_exception_safe():
    def bad_loader(ref):
        raise RuntimeError("boom")

    eng = LogicEngine(chat_fn=_mock_chat, wiki_loader=bad_loader)
    blk = Block(id="b1", kind="input", config={"x": 1}, wiki_ref="any")
    ctx = eng.run([blk], {})  # 不应抛异常
    assert ctx.variables["x"] == 1
    assert "_wiki_b1" not in ctx.variables


def test_wiki_ref_missing_doc_skipped():
    eng = LogicEngine(chat_fn=_mock_chat, wiki_loader=lambda r: None)
    blk = Block(id="b1", kind="input", config={"x": 1}, wiki_ref="ghost")
    ctx = eng.run([blk], {})
    assert "_wiki_b1" not in ctx.variables


# --------------------------------------------------------------------------- #
# LogicGraph 图编排
# --------------------------------------------------------------------------- #
def test_graph_linear_default_edge():
    eng = LogicEngine(chat_fn=_mock_chat)
    g = LogicGraph(
        nodes=[
            Block(id="a", kind="input", config={"x": 10}),
            Block(id="b", kind="transform", config={"expr": "x * 2", "output_var": "y"}),
        ],
        edges=[GraphEdge(source="a", target="b")],
        entry="a",
    )
    ctx = eng.run_graph(g, {})
    assert ctx.variables["y"] == 20
    assert len(ctx.results) == 2


def test_graph_condition_branch_true():
    eng = LogicEngine(chat_fn=_mock_chat)
    g = LogicGraph(
        nodes=[
            Block(id="a", kind="input", config={"score": 80}),
            Block(id="hi", kind="transform", config={"expr": '"high"', "output_var": "grade"}),
            Block(id="lo", kind="transform", config={"expr": '"low"', "output_var": "grade"}),
        ],
        edges=[
            GraphEdge(source="a", target="hi", condition="score > 50"),
            GraphEdge(source="a", target="lo"),
        ],
        entry="a",
    )
    ctx = eng.run_graph(g, {})
    assert ctx.variables["grade"] == "high"


def test_graph_condition_branch_false_to_default():
    eng = LogicEngine(chat_fn=_mock_chat)
    g = LogicGraph(
        nodes=[
            Block(id="a", kind="input", config={"score": 30}),
            Block(id="hi", kind="transform", config={"expr": '"high"', "output_var": "grade"}),
            Block(id="lo", kind="transform", config={"expr": '"low"', "output_var": "grade"}),
        ],
        edges=[
            GraphEdge(source="a", target="hi", condition="score > 50"),
            GraphEdge(source="a", target="lo"),
        ],
        entry="a",
    )
    ctx = eng.run_graph(g, {})
    assert ctx.variables["grade"] == "low"


def test_graph_no_out_edge_terminates():
    eng = LogicEngine(chat_fn=_mock_chat)
    g = LogicGraph(
        nodes=[Block(id="a", kind="input", config={"x": 1})],
        edges=[],
        entry="a",
    )
    ctx = eng.run_graph(g, {})
    assert len(ctx.results) == 1


def test_graph_loop_protection_max_steps():
    eng = LogicEngine(chat_fn=_mock_chat)
    g = LogicGraph(
        nodes=[
            Block(id="a", kind="input", config={"x": 1}),
            Block(id="b", kind="transform", config={"expr": "x", "output_var": "x"}),
        ],
        edges=[
            GraphEdge(source="a", target="b"),
            GraphEdge(source="b", target="a"),
        ],
        entry="a",
    )
    ctx = eng.run_graph(g, {}, max_steps=5)
    assert len(ctx.results) <= 5  # 不会无限循环


def test_graph_apply_action_debug_collects_edits():
    eng = LogicEngine(chat_fn=_mock_chat)
    g = LogicGraph(
        nodes=[
            Block(id="a", kind="apply_action", config={
                "edits": [{"pk": "1", "field": "status", "value": "ok"}],
            }),
        ],
        edges=[],
        entry="a",
    )
    ctx = eng.run_graph(g, {}, debug=True)
    assert len(ctx.proposed_edits) == 1


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr("aos_api.routers.logic.LogicEngine", lambda: LogicEngine(chat_fn=_mock_chat))
    return TestClient(create_app())


def test_api_run_graph(client):
    resp = client.post("/v1/logic/run-graph", json={
        "graph": {
            "nodes": [
                {"id": "a", "kind": "input", "config": {"x": 5}},
                {"id": "b", "kind": "transform", "config": {"expr": "x + 1", "output_var": "y"}},
            ],
            "edges": [{"source": "a", "target": "b"}],
            "entry": "a",
        },
        "inputs": {},
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["variables"]["y"] == 6


def test_api_debug_graph(client):
    resp = client.post("/v1/logic/debug-graph", json={
        "graph": {
            "nodes": [
                {"id": "a", "kind": "apply_action", "config": {
                    "edits": [{"pk": "1", "field": "f", "value": "v"}],
                }},
            ],
            "edges": [],
            "entry": "a",
        },
        "inputs": {},
        "debug": True,
    }, headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["proposed_edits"]) == 1
