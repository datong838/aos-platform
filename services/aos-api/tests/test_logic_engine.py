"""W1-2 · Logic 编排引擎 单元测试。

详见 docs/palantier/20_tech/220tech_logic-engine.md §6。

Agnes 实连测试通过 .env 的 AGNES_* 参数自动运行（未配置时 skip）。
不写死任何模型名——模型由 llm_gateway 路由或测试参数注入。
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api.logic_engine import (
    BLOCK_CATALOG,
    Block,
    EditEntry,
    LogicEngine,
    merge_edits,
)
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _mock_chat(query: str, **kw) -> dict:
    return {"answer": f"mock-answer-for: {query[:50]}", "provider": "mock"}


def _agnes_configured() -> bool:
    return bool(
        os.environ.get("AGNES_API_KEY")
        and os.environ.get("AGNES_BASE_URL")
        and os.environ.get("AGNES_TEXT_MODEL")
    )


# --------------------------------------------------------------------------- #
# Block 单元测试
# --------------------------------------------------------------------------- #
def test_block_input():
    eng = LogicEngine(chat_fn=_mock_chat)
    blk = Block(kind="input", config={"user_name": "alice", "age": 30})
    ctx = eng.run([blk], {})
    assert ctx.variables["user_name"] == "alice"
    assert ctx.variables["age"] == 30


def test_block_create_variable():
    eng = LogicEngine(chat_fn=_mock_chat)
    blk = Block(kind="create_variable", config={"name": "greeting", "expr": '"hello"'})
    ctx = eng.run([blk], {})
    assert ctx.variables["greeting"] == "hello"


def test_block_get_property():
    eng = LogicEngine(chat_fn=_mock_chat)
    blocks = [
        Block(kind="input", config={"obj": {"name": "alice", "dept": "eng"}}),
        Block(kind="get_property", config={"source": "obj", "property": "name", "as": "person_name"}),
    ]
    ctx = eng.run(blocks, {})
    assert ctx.variables["person_name"] == "alice"


def test_block_use_llm_mock():
    eng = LogicEngine(chat_fn=_mock_chat)
    blk = Block(kind="use_llm", config={"prompt": "分析这个数据 {{input_text}}", "output_var": "analysis"})
    ctx = eng.run([blk], {"input_text": "销量下降"})
    assert "mock-answer-for" in ctx.variables["analysis"]
    assert len(ctx.cot) >= 2


def test_block_transform():
    eng = LogicEngine(chat_fn=_mock_chat)
    blocks = [
        Block(kind="input", config={"x": 10, "y": 20}),
        Block(kind="transform", config={"expr": "x + y", "output_var": "sum"}),
    ]
    ctx = eng.run(blocks, {})
    assert ctx.variables["sum"] == 30


def test_block_apply_action_debug():
    eng = LogicEngine(chat_fn=_mock_chat)
    blk = Block(kind="apply_action", config={
        "action_ref": "update_status",
        "edits": [
            {"pk": "obj-1", "field": "status", "value": "approved"},
            {"pk": "obj-2", "field": "status", "value": "rejected"},
        ],
    })
    ctx = eng.run([blk], {}, debug=True)
    assert len(ctx.proposed_edits) == 2
    assert ctx.results[0].output["applied"] is False


def test_block_apply_action_write():
    eng = LogicEngine(chat_fn=_mock_chat)
    blk = Block(kind="apply_action", config={
        "action_ref": "update_status",
        "edits": [{"pk": "obj-1", "field": "status", "value": "approved"}],
    })
    ctx = eng.run([blk], {}, debug=False)
    assert ctx.results[0].output["applied"] is True
    assert len(ctx.results[0].output["edits"]) == 1


def test_block_chain_sequential():
    eng = LogicEngine(chat_fn=_mock_chat)
    blocks = [
        Block(kind="input", config={"base_price": 100}),
        Block(kind="transform", config={"expr": "base_price * 110 / 100", "output_var": "price_with_tax"}),
        Block(kind="use_llm", config={"prompt": "价格是 {{price_with_tax}}", "output_var": "summary"}),
    ]
    ctx = eng.run(blocks, {})
    assert ctx.variables["price_with_tax"] == 110
    assert "110" in ctx.variables["summary"]


def test_debug_cot_collection():
    eng = LogicEngine(chat_fn=_mock_chat)
    blocks = [
        Block(kind="use_llm", config={"prompt": "第一步 {{x}}", "output_var": "step1"}),
        Block(kind="use_llm", config={"prompt": "第二步 {{step1}}", "output_var": "step2"}),
    ]
    ctx = eng.run(blocks, {"x": "data"}, debug=True)
    assert len(ctx.cot) >= 4
    assert any("第一步" in c or "data" in c for c in ctx.cot)


def test_debug_proposed_edits():
    eng = LogicEngine(chat_fn=_mock_chat)
    blocks = [
        Block(kind="apply_action", config={
            "edits": [{"pk": "1", "field": "score", "value": 95}],
        }),
    ]
    ctx = eng.run(blocks, {}, debug=True)
    assert len(ctx.proposed_edits) == 1
    assert ctx.proposed_edits[0]["field"] == "score"


# --------------------------------------------------------------------------- #
# Edits 合并策略
# --------------------------------------------------------------------------- #
def test_edits_merge_last_write_wins():
    edits = [
        EditEntry(pk="1", field="status", value="a", source_block_id="b1"),
        EditEntry(pk="1", field="status", value="b", source_block_id="b2"),
    ]
    merged = merge_edits(edits, "last_write_wins")
    assert len(merged) == 1
    assert merged[0].value == "b"


def test_edits_merge_field_level():
    edits = [
        EditEntry(pk="1", field="status", value="a", source_block_id="b1"),
        EditEntry(pk="1", field="name", value="x", source_block_id="b2"),
        EditEntry(pk="1", field="status", value="b", source_block_id="b3"),
    ]
    merged = merge_edits(edits, "field_level")
    pk1_edits = [e for e in merged if e.pk == "1"]
    status_edits = [e for e in pk1_edits if e.field == "status"]
    assert len(status_edits) == 1
    assert status_edits[0].value == "b"
    name_edits = [e for e in pk1_edits if e.field == "name"]
    assert len(name_edits) == 1


# --------------------------------------------------------------------------- #
# Prompt 工程
# --------------------------------------------------------------------------- #
def test_prompt_variable_injection():
    eng = LogicEngine(chat_fn=_mock_chat)
    blk = Block(kind="use_llm", config={
        "prompt": "你好 {{name}}，你的订单 {{order_id}} 已确认",
        "output_var": "msg",
    })
    ctx = eng.run([blk], {"name": "张三", "order_id": "A12345"})
    assert "张三" in ctx.variables["msg"] or "A12345" in ctx.variables["msg"]


def test_prompt_few_shot():
    calls: list[str] = []

    def capture_chat(query: str, **kw) -> dict:
        calls.append(query)
        return {"answer": "ok"}

    eng = LogicEngine(chat_fn=capture_chat)
    blk = Block(kind="use_llm", config={
        "prompt": "分类：{{text}}",
        "few_shot": ["示例1：正面", "示例2：负面"],
        "output_var": "result",
    })
    eng.run([blk], {"text": "很好"})
    assert len(calls) == 1
    assert "示例1" in calls[0]
    assert "示例2" in calls[0]
    assert "很好" in calls[0]


# --------------------------------------------------------------------------- #
# Ontology 写回四步链路
# --------------------------------------------------------------------------- #
def test_ontology_writeback_four_steps():
    eng = LogicEngine(chat_fn=_mock_chat)
    blocks = [
        Block(id="b1", kind="input", config={"record": {"id": "obj-1", "text": "需要审核"}}),
        Block(id="b2", kind="use_llm", config={
            "prompt": "分析这条记录是否通过 {{record}}",
            "output_var": "decision",
        }),
        Block(id="b3", kind="apply_action", config={
            "action_ref": "approve_record",
            "edits": [{"pk": "obj-1", "field": "status", "value": "{{decision}}"}],
        }),
    ]
    ctx = eng.run(blocks, {}, debug=True)
    assert len(ctx.proposed_edits) == 1
    edit = ctx.proposed_edits[0]
    assert edit["pk"] == "obj-1"
    assert edit["field"] == "status"
    assert "mock-answer" in edit["value"]


# --------------------------------------------------------------------------- #
# Block 目录
# --------------------------------------------------------------------------- #
def test_block_catalog_has_seven_types():
    kinds = {b["kind"] for b in BLOCK_CATALOG}
    expected = {"input", "create_variable", "get_property", "use_llm", "transform", "apply_action", "execute"}
    assert expected.issubset(kinds)


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr("aos_api.routers.logic.LogicEngine", lambda: LogicEngine(chat_fn=_mock_chat))
    return TestClient(create_app())


def test_api_list_blocks(client):
    resp = client.get("/v1/logic/blocks", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 7


def test_api_run(client):
    resp = client.post("/v1/logic/run", json={
        "blocks": [
            {"kind": "input", "config": {"x": 5}},
            {"kind": "transform", "config": {"expr": "x * 2", "output_var": "doubled"}},
        ],
        "inputs": {},
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["variables"]["doubled"] == 10


def test_api_debug(client):
    resp = client.post("/v1/logic/debug", json={
        "blocks": [
            {"kind": "use_llm", "config": {"prompt": "test {{val}}", "output_var": "out"}},
            {"kind": "apply_action", "config": {
                "edits": [{"pk": "1", "field": "f", "value": "v"}],
            }},
        ],
        "inputs": {"val": "hello"},
        "debug": True,
    }, headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["proposed_edits"]) == 1
    assert len(resp.json()["cot"]) >= 2


# --------------------------------------------------------------------------- #
# Agnes 实连（读 .env，不写死模型）
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _agnes_configured(), reason="AGNES_* 未配置（读 .env）")
def test_use_llm_with_agnes():
    from aos_api.env_load import load_dotenv
    load_dotenv(force=True)
    from aos_api.llm_gateway import _openai_chat, agnes_api_key, agnes_base_url, agnes_text_model

    def _force_agnes_chat(query: str, **kw) -> dict:
        out = _openai_chat(
            base_url=agnes_base_url(),
            api_key=agnes_api_key(),
            model=kw.get("model") or agnes_text_model(),
            query=query,
        )
        return {"answer": out["answer"], "provider": "agnes", "route": "agnes", "model": kw.get("model") or agnes_text_model()}

    eng = LogicEngine(chat_fn=_force_agnes_chat)
    blk = Block(kind="use_llm", config={
        "prompt": "请用一句话回答：1+1等于几？",
        "output_var": "answer",
    })
    ctx = eng.run([blk], {})
    answer = ctx.variables["answer"]
    assert isinstance(answer, str)
    assert len(answer) > 0
    assert "mock" not in answer.lower()
