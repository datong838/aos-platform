"""Phase 3 · AIP Tools & Evals — 单元测试。"""
import pytest

from aos_api.aip_tools_engine import get_engine, ToolsEngine


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def test_create_and_get_tool():
    eng = get_engine()
    tool = eng.create_tool("TestTool", category="data", description="desc")
    assert tool.name == "TestTool"
    fetched = eng.get_tool(tool.id)
    assert fetched is not None


def test_list_tools_filter():
    eng = get_engine()
    eng.create_tool("T1", category="data")
    eng.create_tool("T2", category="ai")
    eng.create_tool("T3", category="data", enabled=False)
    data_tools = eng.list_tools(category="data")
    assert len(data_tools) == 2
    enabled = eng.list_tools(enabled=True)
    assert len(enabled) == 2


def test_update_tool():
    eng = get_engine()
    tool = eng.create_tool("Tool")
    updated = eng.update_tool(tool.id, description="New", version="2.0.0")
    assert updated.description == "New"
    assert updated.version == "2.0.0"


def test_delete_tool():
    eng = get_engine()
    tool = eng.create_tool("ToDelete")
    assert eng.delete_tool(tool.id) is True
    assert eng.get_tool(tool.id) is None


def test_quality():
    eng = get_engine()
    tool = eng.create_tool("QTool")
    eng.set_quality(tool.id, overall=90.0, accuracy=92.0, latency=85.0, reliability=93.0)
    q = eng.get_quality(tool.id)
    assert q is not None
    assert q.overall == 90.0
    assert q.accuracy == 92.0


def test_eval_create():
    eng = get_engine()
    ev = eng.create_eval("Test Eval", eval_type="tool", status="passed", score=90.0, l4_allowed=True)
    assert ev.name == "Test Eval"
    assert ev.l4_allowed is True


def test_eval_list_filter():
    eng = get_engine()
    eng.create_eval("E1", eval_type="tool", status="passed")
    eng.create_eval("E2", eval_type="rag", status="running")
    tools = eng.list_evals(eval_type="tool")
    assert len(tools) == 1
    running = eng.list_evals(status="running")
    assert len(running) == 1


def test_eval_update():
    eng = get_engine()
    ev = eng.create_eval("Eval")
    updated = eng.update_eval(ev.id, score=85.0, l4_allowed=True)
    assert updated.score == 85.0
    assert updated.l4_allowed is True


def test_circuit_trip():
    eng = get_engine()
    tool = eng.create_tool("CTool")
    rec = eng.trip_circuit(tool.id, "timeout")
    assert rec.state == "open"
    assert rec.tool_id == tool.id
    # tool should be disabled
    assert eng.get_tool(tool.id).enabled is False


def test_circuit_reset():
    eng = get_engine()
    tool = eng.create_tool("RTool")
    rec = eng.trip_circuit(tool.id, "test")
    eng.reset_circuit(rec.id)
    assert rec.state == "closed"
    assert eng.get_tool(tool.id).enabled is True


def test_singleton():
    e1 = get_engine()
    e2 = ToolsEngine()
    assert e1 is e2
