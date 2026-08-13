"""Phase 3 · AIP Agents — 单元测试。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.aip_agents_engine import get_engine, AgentsEngine, Agent, ToolRef, GuardrailRule
from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers.phase3_aip_agents import router


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def test_create_and_get():
    eng = get_engine()
    agent = eng.create("Test Agent", description="desc", tags=["t1"])
    assert agent.name == "Test Agent"
    fetched = eng.get(agent.id)
    assert fetched is not None
    assert fetched.id == agent.id


def test_list_with_filter():
    eng = get_engine()
    eng.create("A1", source="platform", tags=["data"])
    eng.create("A2", source="marketplace", tags=["ai"])
    eng.create("A3", source="platform", tags=["data", "build"])
    platform = eng.list(source="platform")
    assert len(platform) == 2
    tagged = eng.list(tag="data")
    assert len(tagged) == 2


def test_update():
    eng = get_engine()
    agent = eng.create("Agent")
    updated = eng.update(agent.id, description="Updated", status="draft")
    assert updated.description == "Updated"
    assert updated.status == "draft"


def test_delete():
    eng = get_engine()
    agent = eng.create("ToDelete")
    assert eng.delete(agent.id) is True
    assert eng.get(agent.id) is None


def test_prompt_ops():
    eng = get_engine()
    agent = eng.create("PromptAgent")
    assert eng.get_prompt(agent.id) == ""
    eng.set_prompt(agent.id, "You are a helpful agent")
    assert eng.get_prompt(agent.id) == "You are a helpful agent"


def test_tools():
    eng = get_engine()
    agent = eng.create("ToolAgent", tools=[ToolRef(id="t1", name="Tool1", category="data")])
    tools = eng.list_tools(agent.id)
    assert len(tools) == 1
    assert tools[0].name == "Tool1"


def test_set_tools_replays_from_engine():
    eng = get_engine()
    agent = eng.create("ToolAgent")
    eng.set_tools(agent.id, [{"id": "t1", "name": "Tool1", "category": "data", "enabled": True}])
    assert [tool.id for tool in eng.list_tools(agent.id)] == ["t1"]


def test_guardrails():
    eng = get_engine()
    agent = eng.create("GRAgent")
    eng.set_guardrails(agent.id, [
        {"id": "g1", "name": "PII", "type": "pii", "action": "redact", "enabled": True}
    ])
    rules = eng.get_guardrails(agent.id)
    assert len(rules) == 1
    assert rules[0].type == "pii"


def test_stats():
    eng = get_engine()
    eng.create("A1", source="platform", calls=100)
    eng.create("A2", source="marketplace", calls=50)
    stats = eng.stats()
    assert stats["total"] == 2
    assert stats["total_calls"] == 150
    assert stats["by_source"]["platform"] == 1


def test_get_nonexistent():
    eng = get_engine()
    assert eng.get("fake") is None
    assert eng.get_prompt("fake") is None
    assert eng.list_tools("fake") == []


def test_update_nonexistent():
    eng = get_engine()
    with pytest.raises(KeyError):
        eng.update("fake", name="x")


def test_singleton():
    e1 = get_engine()
    e2 = AgentsEngine()
    assert e1 is e2


def _principal():
    return Principal(subject="pytest", org_id="org-org", project_id="dev-project")


def test_legacy_agent_http_writes_are_retired():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_principal] = _principal
    register_exception_handlers(app)
    with TestClient(app) as client:
        created = client.post("/v1/aip/agents", json={"name": "HTTP Agent", "description": "desc", "status": "draft"})
        assert created.status_code == 409
        assert created.json()["code"] == "AIP_LEGACY_AGENT_WRITE_RETIRED"
        prompt = client.put("/v1/aip/agents/example/prompt", json={"prompt": "hello"})
        assert prompt.status_code == 409
        assert prompt.json()["code"] == "AIP_CANONICAL_OVERLAY_NOT_IMPLEMENTED"


def test_put_tools_requires_canonical_overlay_contract():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_principal] = _principal
    register_exception_handlers(app)
    with TestClient(app) as client:
        response = client.put("/v1/aip/agents/missing/tools", json={"items": []})
        assert response.status_code == 409
        assert response.json()["code"] == "AIP_CANONICAL_OVERLAY_NOT_IMPLEMENTED"
