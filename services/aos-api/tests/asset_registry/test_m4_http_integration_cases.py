"""M4-2 HTTP lifecycle through real JWT, Service and isolated PostgreSQL."""

from __future__ import annotations

from aos_api.asset_registry.integration_projection import IntegrationExpiryProjector
from aos_api.asset_registry.integration_reader import (
    PostgresIntegrationCaseReader,
    PrincipalMarkingResolver,
)
from aos_api.asset_registry.integration_service import IntegrationCaseService
from aos_api.asset_registry.integration_store import PostgresIntegrationStore
from aos_api.errors import register_exception_handlers
from aos_api.routers import auth_oidc, integration_cases
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.asset_registry.test_integration_store_pg import (
    INSTALLATION_ID,
    ORG,
    PROJECT,
    _schema,
    _seed_active_installation,
)


def _application(service: IntegrationCaseService) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth_oidc.router)
    app.include_router(integration_cases.router)
    app.dependency_overrides[integration_cases.get_integration_case_service] = (
        lambda: service
    )
    return app


def _token(
    client: TestClient,
    *,
    subject: str,
    org_id: str = ORG,
    markings: list[str] | None = None,
    roles: list[str] | None = None,
) -> str:
    response = client.post(
        "/v1/auth/token",
        json={
            "grantType": "dev",
            "subject": subject,
            "orgId": org_id,
            "projectId": PROJECT,
            "roles": roles
            or [
                "integration-case-reader",
                "integration-case-maker",
                "integration-case-projector",
            ],
            "markings": markings or ["internal"],
            "alg": "HS256",
        },
    )
    assert response.status_code == 200
    return response.json()["accessToken"]


def _headers(token: str, *, org_id: str = ORG, **extra: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "X-Project-Id": PROJECT,
        **extra,
    }


def test_m4_http_case_lifecycle_marking_tenant_replay_and_cas(monkeypatch) -> None:
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "1")
    with _schema() as connect_factory:
        _seed_active_installation(connect_factory)
        service = IntegrationCaseService(
            store=PostgresIntegrationStore(connect_factory),
            reader=PostgresIntegrationCaseReader(connect_factory),
            marking_resolver=PrincipalMarkingResolver(),
            expiry_projector=IntegrationExpiryProjector(connect_factory),
        )
        with TestClient(_application(service), raise_server_exceptions=False) as client:
            token = _token(client, subject="operator:m4")
            create_headers = _headers(token, **{"Idempotency-Key": "m4-create-1"})
            request = {
                "installationId": str(INSTALLATION_ID),
                "overlayRevision": "overlay-v1",
                "displayName": "M4 接入案例",
            }
            created_response = client.post(
                "/v1/integration-cases", json=request, headers=create_headers
            )
            assert created_response.status_code == 201
            assert created_response.headers["etag"] == '"1"'
            created = created_response.json()
            case_id = created["caseId"]
            assert created["computedStage"] == "planned"
            assert created["installationId"] == str(INSTALLATION_ID)

            replay = client.post(
                "/v1/integration-cases", json=request, headers=create_headers
            )
            assert replay.status_code == 201
            assert replay.json() == created

            listed = client.get(
                "/v1/integration-cases?scope=current&limit=20&offset=0",
                headers=_headers(token),
            )
            assert listed.status_code == 200
            assert listed.json()["total"] == 1
            assert listed.json()["stats"]["caseCount"]["value"] == 1

            detail = client.get(
                f"/v1/integration-cases/{case_id}", headers=_headers(token)
            )
            assert detail.status_code == 200
            assert detail.headers["etag"] == '"1"'

            projected = client.post(
                f"/v1/integration-cases/{case_id}/evidence-snapshots",
                json={},
                headers=_headers(
                    token,
                    **{"Idempotency-Key": "m4-project-1", "If-Match": '"1"'},
                ),
            )
            assert projected.status_code == 201
            assert projected.headers["etag"] == '"2"'
            assert projected.json()["etagVersion"] == 2

            stale = client.post(
                f"/v1/integration-cases/{case_id}/evidence-snapshots",
                json={},
                headers=_headers(
                    token,
                    **{"Idempotency-Key": "m4-project-stale", "If-Match": '"1"'},
                ),
            )
            assert stale.status_code == 409
            assert stale.json()["code"] == "REVISION_CONFLICT"

            timeline = client.get(
                f"/v1/integration-cases/{case_id}/timeline",
                headers=_headers(token),
            )
            assert timeline.status_code == 200
            assert timeline.json()["total"] == 1

            hidden_token = _token(
                client, subject="hidden:m4", markings=["public"]
            )
            hidden = client.get(
                f"/v1/integration-cases/{case_id}",
                headers=_headers(hidden_token),
            )
            assert hidden.status_code == 404
            hidden_list = client.get(
                "/v1/integration-cases?scope=current",
                headers=_headers(hidden_token),
            )
            assert hidden_list.status_code == 200
            assert hidden_list.json()["total"] == 0

            other_org = "org-other"
            other_token = _token(
                client, subject="other:m4", org_id=other_org
            )
            cross_tenant = client.get(
                f"/v1/integration-cases/{case_id}",
                headers=_headers(other_token, org_id=other_org),
            )
            assert cross_tenant.status_code == 404
