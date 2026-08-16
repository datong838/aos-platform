"""AIP Agent 兼容路由的退役契约测试。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers.phase3_aip_agents import router


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
