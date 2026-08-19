"""AIP Agent 兼容路由的退役契约与 overlay 读写测试。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers.phase3_aip_agents import get_agent_overlay_store, router


def _principal():
    return Principal(subject="pytest", org_id="org-org", project_id="dev-project")


class _FakeOverlayStore:
    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}
        self.tools: dict[str, list[dict]] = {}
        self.guardrails: dict[str, list[dict]] = {}

    def get_prompt(self, scope, instance_id: str) -> dict:
        _ = scope
        if instance_id == "missing":
            raise AipAgentRegistryNotFound("agent instance not found")
        return {"agent_id": instance_id, "prompt": self.prompts.get(instance_id, "")}

    def put_prompt(self, scope, instance_id: str, *, prompt: str, actor: str) -> dict:
        _ = scope, actor
        if instance_id == "missing":
            raise AipAgentRegistryNotFound("agent instance not found")
        self.prompts[instance_id] = prompt
        return {"ok": True, "agent_id": instance_id, "prompt": prompt}

    def get_tools(self, scope, instance_id: str) -> dict:
        _ = scope
        if instance_id == "missing":
            raise AipAgentRegistryNotFound("agent instance not found")
        return {"agent_id": instance_id, "items": list(self.tools.get(instance_id, []))}

    def put_tools(self, scope, instance_id: str, *, items: list[dict], actor: str) -> dict:
        _ = scope, actor
        if instance_id == "missing":
            raise AipAgentRegistryNotFound("agent instance not found")
        self.tools[instance_id] = list(items)
        return {"agent_id": instance_id, "items": list(items)}

    def get_guardrails(self, scope, instance_id: str) -> dict:
        _ = scope
        if instance_id == "missing":
            raise AipAgentRegistryNotFound("agent instance not found")
        return {"agent_id": instance_id, "items": list(self.guardrails.get(instance_id, []))}

    def put_guardrails(self, scope, instance_id: str, *, items: list[dict], actor: str) -> dict:
        _ = scope, actor
        if instance_id == "missing":
            raise AipAgentRegistryNotFound("agent instance not found")
        self.guardrails[instance_id] = list(items)
        return {"agent_id": instance_id, "items": list(items)}


def _app_with_overlay(store: _FakeOverlayStore | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_principal] = _principal
    fake = store or _FakeOverlayStore()
    app.dependency_overrides[get_agent_overlay_store] = lambda: fake
    register_exception_handlers(app)
    return app


def test_legacy_agent_http_writes_are_retired():
    app = _app_with_overlay()
    with TestClient(app) as client:
        created = client.post(
            "/v1/aip/agents",
            json={"name": "HTTP Agent", "description": "desc", "status": "draft"},
        )
        assert created.status_code == 409
        assert created.json()["code"] == "AIP_LEGACY_AGENT_WRITE_RETIRED"


def test_prompt_overlay_roundtrip_for_existing_instance():
    store = _FakeOverlayStore()
    app = _app_with_overlay(store)
    with TestClient(app) as client:
        empty = client.get("/v1/aip/agents/ecommerce.content_officer.default/prompt")
        assert empty.status_code == 200
        assert empty.json() == {
            "agent_id": "ecommerce.content_officer.default",
            "prompt": "",
        }
        written = client.put(
            "/v1/aip/agents/ecommerce.content_officer.default/prompt",
            json={"prompt": "hello overlay"},
        )
        assert written.status_code == 200
        assert written.json()["ok"] is True
        assert written.json()["prompt"] == "hello overlay"
        reread = client.get("/v1/aip/agents/ecommerce.content_officer.default/prompt")
        assert reread.status_code == 200
        assert reread.json()["prompt"] == "hello overlay"


def test_tools_overlay_roundtrip_for_existing_instance():
    store = _FakeOverlayStore()
    app = _app_with_overlay(store)
    items = [{"id": "tool.a", "name": "A", "category": "tool", "enabled": True}]
    with TestClient(app) as client:
        written = client.put(
            "/v1/aip/agents/ecommerce.content_officer.default/tools",
            json={"items": items},
        )
        assert written.status_code == 200
        assert written.json()["items"] == items
        reread = client.get("/v1/aip/agents/ecommerce.content_officer.default/tools")
        assert reread.status_code == 200
        assert reread.json()["items"] == items


def test_overlay_missing_instance_returns_404():
    app = _app_with_overlay()
    with TestClient(app) as client:
        prompt = client.put("/v1/aip/agents/missing/prompt", json={"prompt": "hello"})
        assert prompt.status_code == 404
        assert prompt.json()["code"] == "AIP_AGENT_REGISTRY_NOT_FOUND"
        tools = client.put("/v1/aip/agents/missing/tools", json={"items": []})
        assert tools.status_code == 404
        assert tools.json()["code"] == "AIP_AGENT_REGISTRY_NOT_FOUND"
        guardrails = client.put("/v1/aip/agents/missing/guardrails", json={"items": []})
        assert guardrails.status_code == 404
        assert guardrails.json()["code"] == "AIP_AGENT_REGISTRY_NOT_FOUND"


def test_guardrails_overlay_roundtrip_for_existing_instance():
    store = _FakeOverlayStore()
    app = _app_with_overlay(store)
    items = [{"id": "no_fs_write", "name": "禁止写文件系统", "enabled": True}]
    with TestClient(app) as client:
        empty = client.get("/v1/aip/agents/ecommerce.content_officer.default/guardrails")
        assert empty.status_code == 200
        assert empty.json() == {
            "agent_id": "ecommerce.content_officer.default",
            "items": [],
        }
        written = client.put(
            "/v1/aip/agents/ecommerce.content_officer.default/guardrails",
            json={"items": items},
        )
        assert written.status_code == 200
        assert written.json()["items"] == items
        reread = client.get("/v1/aip/agents/ecommerce.content_officer.default/guardrails")
        assert reread.status_code == 200
        assert reread.json()["items"] == items


def test_activate_agent_requires_idempotency_key():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_principal] = _principal
    register_exception_handlers(app)
    with TestClient(app) as client:
        response = client.post(
            "/v1/aip/agents/ecommerce.data_advisor.default/activate",
            json={"expectedVersion": 1, "capabilityBindingIds": ["binding-1"]},
        )
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"
