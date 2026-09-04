"""GET-only API tests for the tenant-bound operation case workspace."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_operation_case_workspace_contracts import (
    OperationCaseWorkspaceEnvelope,
)
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop


NOW = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)


class FakeCatalog:
    def __init__(self, *, installed: bool = True) -> None:
        self.installed = installed
        self.calls: list[dict[str, object]] = []

    def get_readiness(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if not self.installed:
            raise AssetNotFoundError("not installed")
        return object()


class FakeWorkspace:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def read(self, *, org_id: str, project_id: str) -> OperationCaseWorkspaceEnvelope:
        self.calls.append({"org_id": org_id, "project_id": project_id})
        return OperationCaseWorkspaceEnvelope.model_validate({
            "tenant": {"orgId": org_id, "projectId": project_id},
            "status": "ready",
            "evaluatedAt": NOW,
            "dataCutoff": NOW,
            "sources": [
                {"sourceId": source_id, "status": "ready", "count": 0}
                for source_id in (
                    "orders", "inventory", "shipments", "aftersaleEvents",
                    "payments", "operationCases",
                )
            ],
            "cases": [],
            "candidates": [],
            "availableRefs": [],
            "ledger": {
                "sourceTotal": 0, "assigned": 0, "unassigned": 0,
                "candidates": 0, "openCases": 0, "pausedCases": 0,
                "closedCases": 0,
            },
            "externalEffectAllowed": False,
        })


def _client(
    *,
    catalog: FakeCatalog | None = None,
    workspace: FakeWorkspace | None = None,
) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-org",
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_catalog] = (
        lambda: catalog or FakeCatalog()
    )
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_operation_case_workspace] = (
        lambda: workspace or FakeWorkspace()
    )
    return TestClient(app, raise_server_exceptions=False)


def test_operation_case_workspace_is_get_only_and_tenant_bound() -> None:
    catalog = FakeCatalog()
    workspace = FakeWorkspace()
    with _client(catalog=catalog, workspace=workspace) as client:
        response = client.get("/v1/ecommerce-workshop/views/operations/cases")
        injected = client.get(
            "/v1/ecommerce-workshop/views/operations/cases?orgId=dev-org"
        )
        posted = client.post("/v1/ecommerce-workshop/views/operations/cases")

    assert response.status_code == 200
    assert response.json()["tenant"] == {
        "orgId": "org-org", "projectId": "dev-project",
    }
    assert workspace.calls == [{"org_id": "org-org", "project_id": "dev-project"}]
    assert catalog.calls[0]["module_id"] == "ecommerce.operations"
    assert injected.status_code == 400
    assert injected.json()["code"] == "VALIDATION"
    assert posted.status_code == 405


def test_operation_case_workspace_fails_closed_without_installation() -> None:
    workspace = FakeWorkspace()
    with _client(catalog=FakeCatalog(installed=False), workspace=workspace) as client:
        response = client.get("/v1/ecommerce-workshop/views/operations/cases")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert workspace.calls == []


def test_openapi_exposes_only_operation_case_workspace_get() -> None:
    with _client() as client:
        document = client.get("/openapi.json").json()

    surface = document["paths"][
        "/v1/ecommerce-workshop/views/operations/cases"
    ]
    assert set(surface) == {"get"}
    assert surface["get"]["operationId"] == (
        "ecommerceWorkshopOperationCaseWorkspaceGet"
    )
