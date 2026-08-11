"""Phase 3 · AIP Logic — 单元测试。"""
import pytest

from aos_api.aip_logic_engine import get_engine, LogicEngine, LogicBlock
from aos_api.aip_logic_engine import LegacyLogicExecutionDisabled
from aos_api.tenant_scope import TenantScope


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def _demo_execute(eng, blocks):
    return eng.execute_flow(
        blocks,
        demo_scope=TenantScope("dev-org", "dev-project"),
    )


def test_create_and_get_flow():
    eng = get_engine()
    flow = eng.create_flow("Test Flow", [{"kind": "task", "name": "Step1"}])
    assert flow.name == "Test Flow"
    fetched = eng.get_flow(flow.id)
    assert fetched is not None


def test_list_flows_filter():
    eng = get_engine()
    eng.create_flow("F1", status="active")
    eng.create_flow("F2", status="draft")
    active = eng.list_flows(status="active")
    assert len(active) == 1


def test_update_flow():
    eng = get_engine()
    flow = eng.create_flow("Flow")
    updated = eng.update_flow(flow.id, description="Updated", status="archived")
    assert updated.description == "Updated"
    assert updated.status == "archived"


def test_delete_flow():
    eng = get_engine()
    flow = eng.create_flow("ToDelete")
    assert eng.delete_flow(flow.id) is True
    assert eng.get_flow(flow.id) is None


def test_execute_dag_task(monkeypatch):
    monkeypatch.setenv("AIP_DEMO_MOCK_ENABLED", "1")
    eng = get_engine()
    blocks = [LogicBlock(kind="task", name="Step1")]
    result = _demo_execute(eng, blocks)
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["kind"] == "task"
    assert result["source"] == "demo"
    assert result["nonAuthoritative"] is True


def test_execute_dag_branch(monkeypatch):
    monkeypatch.setenv("AIP_DEMO_MOCK_ENABLED", "1")
    eng = get_engine()
    blocks = [
        LogicBlock(kind="branch", name="Gate", config={"condition": "success", "paths": ["a", "b"]}),
    ]
    result = _demo_execute(eng, blocks)
    assert result["results"][0]["kind"] == "branch"
    assert "branch_path" in result["results"][0]


def test_execute_dag_handoff(monkeypatch):
    monkeypatch.setenv("AIP_DEMO_MOCK_ENABLED", "1")
    eng = get_engine()
    blocks = [
        LogicBlock(kind="task", name="Before"),
        LogicBlock(kind="handoff", name="Merge"),
    ]
    result = _demo_execute(eng, blocks)
    assert len(result["results"]) == 2
    assert "merged_context" in result["results"][1]


def test_execute_dag_llm(monkeypatch):
    monkeypatch.setenv("AIP_DEMO_MOCK_ENABLED", "1")
    eng = get_engine()
    blocks = [LogicBlock(kind="llm", name="Generate", config={"prompt": "Hello"})]
    result = _demo_execute(eng, blocks)
    assert "tokens" in result["results"][0]
    assert result["total_tokens"] > 0


def test_legacy_execution_fails_closed_in_real_scope(monkeypatch):
    monkeypatch.setenv("AIP_DEMO_MOCK_ENABLED", "1")
    eng = get_engine()
    with pytest.raises(LegacyLogicExecutionDisabled):
        eng.execute_flow(
            [LogicBlock(kind="task", name="must not run")],
            demo_scope=TenantScope("org-org", "dev-project"),
        )


def test_automation_create():
    eng = get_engine()
    auto = eng.create_automation("Test Auto", trigger_type="schedule")
    assert auto.name == "Test Auto"
    assert eng.get_automation(auto.id) is not None


def test_automation_list_filter():
    eng = get_engine()
    eng.create_automation("A1", trigger_type="schedule", status="active")
    eng.create_automation("A2", trigger_type="event", status="paused")
    active = eng.list_automations(status="active")
    assert len(active) == 1
    events = eng.list_automations(trigger_type="event")
    assert len(events) == 1


def test_automation_update():
    eng = get_engine()
    auto = eng.create_automation("Auto")
    updated = eng.update_automation(auto.id, status="paused")
    assert updated.status == "paused"


def test_singleton():
    e1 = get_engine()
    e2 = LogicEngine()
    assert e1 is e2
