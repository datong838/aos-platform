"""W2-#18 · 工具集注册与 Capability 深度集成测试。"""
from __future__ import annotations

import pytest

from aos_api.logic_engine import BLOCK_CATALOG, Block, LogicEngine, LogicError
from aos_api.tool_registry import (
    Capability,
    CapabilityStore,
    ToolDef,
    ToolError,
    ToolRegistry,
)


@pytest.fixture
def fresh_registry() -> ToolRegistry:
    return ToolRegistry()


# ---------- ToolRegistry 单元测试 ----------


def test_register_and_get(fresh_registry: ToolRegistry):
    tool = ToolDef(name="echo", description="回显参数")
    fresh_registry.register(tool, lambda args: args)
    assert fresh_registry.get(tool.id) is not None
    assert fresh_registry.get(tool.id).name == "echo"


def test_register_simple(fresh_registry: ToolRegistry):
    tool = fresh_registry.register_simple("addone", lambda args: args.get("x", 0) + 1, "加一")
    assert tool.name == "addone"
    assert fresh_registry.invoke(tool.id, {"x": 5}) == 6


def test_invoke_unknown_tool_raises(fresh_registry: ToolRegistry):
    with pytest.raises(ToolError) as exc:
        fresh_registry.invoke("nope", {})
    assert exc.value.code == "UNKNOWN_TOOL"


def test_invoke_handler_failure_wrapped(fresh_registry: ToolRegistry):
    def bad_handler(args):
        raise ValueError("boom")

    tool = fresh_registry.register_simple("bad", bad_handler)
    with pytest.raises(ToolError) as exc:
        fresh_registry.invoke(tool.id, {})
    assert exc.value.code == "TOOL_FAILED"


def test_find_by_name(fresh_registry: ToolRegistry):
    fresh_registry.register_simple("lookup", lambda a: a)
    tool = fresh_registry.find_by_name("lookup")
    assert tool is not None
    assert fresh_registry.find_by_name("missing") is None


def test_list_all_returns_all(fresh_registry: ToolRegistry):
    fresh_registry.register_simple("a", lambda a: 1)
    fresh_registry.register_simple("b", lambda a: 2)
    names = {t.name for t in fresh_registry.list_all()}
    assert names == {"a", "b"}


def test_remove_tool(fresh_registry: ToolRegistry):
    tool = fresh_registry.register_simple("tmp", lambda a: a)
    assert fresh_registry.remove(tool.id) is True
    assert fresh_registry.get(tool.id) is None
    assert fresh_registry.remove(tool.id) is False


def test_register_missing_name_raises(fresh_registry: ToolRegistry):
    with pytest.raises(ToolError) as exc:
        fresh_registry.register(ToolDef(name=""), lambda a: a)
    assert exc.value.code == "MISSING_NAME"


# ---------- CapabilityStore 测试 ----------


def test_capability_define_and_add_tool(fresh_registry: ToolRegistry):
    store = CapabilityStore(fresh_registry)
    tool = fresh_registry.register_simple("calc", lambda a: 42)
    cap = store.define(Capability(name="math_ops"))
    store.add_tool(cap.id, tool.id)
    tools = store.tools_of(cap.id)
    assert len(tools) == 1
    assert tools[0].name == "calc"


def test_capability_add_unknown_tool_raises(fresh_registry: ToolRegistry):
    store = CapabilityStore(fresh_registry)
    cap = store.define(Capability(name="c1"))
    with pytest.raises(ToolError) as exc:
        store.add_tool(cap.id, "ghost-tool")
    assert exc.value.code == "UNKNOWN_TOOL"


def test_capability_remove_tool(fresh_registry: ToolRegistry):
    store = CapabilityStore(fresh_registry)
    tool = fresh_registry.register_simple("t", lambda a: 1)
    cap = store.define(Capability(name="c", tool_ids=[tool.id]))
    store.remove_tool(cap.id, tool.id)
    assert store.tools_of(cap.id) == []


# ---------- use_tool Block 集成测试 ----------


def test_use_tool_block_writes_result_to_variable(fresh_registry: ToolRegistry):
    fresh_registry.register_simple("greet", lambda args: f"你好，{args.get('who', '世界')}")
    engine = LogicEngine(chat_fn=lambda *a, **k: {"answer": "mock"}, tool_registry=fresh_registry)
    blocks = [
        Block(kind="input", config={"who": "张三"}),
        Block(kind="use_tool", config={"tool_id": fresh_registry.find_by_name("greet").id, "args": {"who": "{{who}}"}, "output_var": "greeting"}),
    ]
    ctx = engine.run(blocks, {})
    assert ctx.variables["greeting"] == "你好，张三"


def test_use_tool_block_missing_tool_id_raises(fresh_registry: ToolRegistry):
    engine = LogicEngine(chat_fn=lambda *a, **k: {"answer": ""}, tool_registry=fresh_registry)
    with pytest.raises(LogicError) as exc:
        engine.run([Block(kind="use_tool", config={"args": {}})], {})
    assert exc.value.code == "MISSING_TOOL"


def test_use_tool_block_unknown_tool_raises(fresh_registry: ToolRegistry):
    engine = LogicEngine(chat_fn=lambda *a, **k: {"answer": ""}, tool_registry=fresh_registry)
    with pytest.raises(LogicError) as exc:
        engine.run([Block(kind="use_tool", config={"tool_id": "ghost"})], {})
    assert exc.value.code == "UNKNOWN_TOOL"


def test_block_catalog_includes_use_tool():
    kinds = {b["kind"] for b in BLOCK_CATALOG}
    assert "use_tool" in kinds
