from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.routers.aip_fde import router


def _client(org_id: str) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="pytest", org_id=org_id, project_id="dev-project"
    )
    return TestClient(app)


def _payload() -> dict[str, object]:
    return {
        "requirement": "接入微商城订单与商品，形成六步受控计划",
        "platform": "niushop",
        "dataTypes": ["orders", "products"],
        "syncFrequency": "hourly",
        "secretRef": "keychain://aos/agnes-api-key",
        "secretVersion": "1",
    }


def test_preview_exposes_six_steps_and_does_not_infer_source_readiness() -> None:
    with _client("org-org") as client:
        response = client.post("/v1/aip/fde/sessions/preview", json=_payload())

    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["stepKey"] for row in body["steps"]] == [
        "fde.s1.requirement",
        "fde.s2.auth-draft",
        "fde.s3.capability-probe",
        "fde.s4.mapping-proposal",
        "fde.s5.controlled-sync",
        "fde.s6.validation",
    ]
    assert body["steps"][5]["facts"]["sourceReadinessStatus"] == "not_supplied"
    assert len(body["reflectionRuleSetHash"]) == 64


def test_preview_tenant_envelopes_are_isolated() -> None:
    with _client("org-org") as primary, _client("dev-org") as canary:
        primary_body = primary.post("/v1/aip/fde/sessions/preview", json=_payload()).json()
        canary_body = canary.post("/v1/aip/fde/sessions/preview", json=_payload()).json()

    assert primary_body["tenant"]["orgId"] == "org-org"
    assert canary_body["tenant"]["orgId"] == "dev-org"
    assert primary_body["planHash"] == canary_body["planHash"]
