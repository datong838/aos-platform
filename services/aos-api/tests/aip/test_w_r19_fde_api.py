from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.routers.aip_fde import router


def _principal(org_id: str = "org-org") -> Principal:
    return Principal(subject="pytest", org_id=org_id, project_id="dev-project")


def _payload() -> dict[str, object]:
    return {
        "requirement": "接入微商城订单与商品，只生成 S1-S6 计划",
        "platform": "niushop",
        "dataTypes": ["orders", "products"],
        "syncFrequency": "hourly",
        "secretRef": "keychain://aos/agnes-api-key",
        "secretVersion": "1",
    }


def _client(org_id: str = "org-org") -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_principal] = lambda: _principal(org_id)
    return TestClient(app)


def test_preview_route_is_tenant_scoped_and_creates_no_execution_authority() -> None:
    with _client() as client:
        response = client.post("/v1/aip/fde/sessions/preview", json=_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert body["status"] == "external_required"
    assert body["executable"] is True
    assert body["steps"][2]["facts"]["onlineVerification"] == "not_started"
    assert len(body["steps"]) == 6
    assert body["steps"][4]["facts"]["pipelineExecuted"] is False
    assert body["steps"][5]["blockerCodes"] == ["FDE_SOURCE_READINESS_REQUIRED"]


def test_preview_route_fails_closed_without_opaque_secret_ref() -> None:
    payload = _payload()
    payload.pop("secretRef")
    payload.pop("secretVersion")

    with _client() as client:
        response = client.post("/v1/aip/fde/sessions/preview", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["executable"] is False
    assert body["steps"][1]["blockerCodes"] == ["FDE_SECRET_REF_REQUIRED"]


def test_canary_route_never_leaks_primary_tenant_context() -> None:
    with _client("dev-org") as client:
        response = client.post("/v1/aip/fde/sessions/preview", json=_payload())

    assert response.status_code == 200
    assert response.json()["tenant"] == {
        "orgId": "dev-org",
        "projectId": "dev-project",
    }


def test_router_exposes_only_preview_plan_and_exact_run_execution() -> None:
    paths = {route.path for route in router.routes}

    assert paths == {
        "/v1/aip/fde/sessions/preview",
        "/v1/aip/fde/sessions",
        "/v1/aip/fde/task-runs/{run_id}/execute",
    }
