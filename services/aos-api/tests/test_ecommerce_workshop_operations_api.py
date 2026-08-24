"""W2-01A GET-only Operations view API shell tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop
from aos_api.ecommerce_workshop_operations import EcommerceWorkshopOperations


class FakeCatalog:
    def __init__(self, *, installed: bool = True) -> None:
        self.installed = installed
        self.calls: list[dict[str, object]] = []

    def get_readiness(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if not self.installed:
            raise AssetNotFoundError("not installed")
        return object()


def _client(
    catalog: FakeCatalog | None = None,
    operations: EcommerceWorkshopOperations | None = None,
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
    if operations is not None:
        app.dependency_overrides[
            ecommerce_workshop.get_ecommerce_workshop_operations
        ] = lambda: operations
    return TestClient(app, raise_server_exceptions=False)


def test_operations_shell_is_tenant_bound_and_structurally_blocked() -> None:
    class ObjectReader:
        def read(self, **kwargs):
            return []

    class InventoryReader:
        def read(self, **kwargs):
            return type("Inventory", (), {"items": []})()

    class CaseStore:
        def list_cases(self, scope, *, limit=50):
            return []

    operations = EcommerceWorkshopOperations(
        object_reader=ObjectReader(),  # type: ignore[arg-type]
        inventory_reader=InventoryReader(),  # type: ignore[arg-type]
        case_store=CaseStore(),  # type: ignore[arg-type]
    )
    catalog = FakeCatalog()
    with _client(catalog, operations) as client:
        response = client.get("/v1/ecommerce-workshop/views/operations")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert body["readiness"] == "degraded"
    assert [item["sliceId"] for item in body["slices"]] == [
        "orders",
        "orderLines",
        "inventory",
        "shipments",
        "payments",
        "aftersaleEvents",
        "operationCases",
    ]
    assert [item["status"] for item in body["slices"]] == [
        "ready",
        "ready",
        "ready",
        "ready",
        "ready",
        "blocked",
        "ready",
    ]
    inventory = body["slices"][2]
    aftersales = body["slices"][5]
    assert inventory["authorityRefs"][0]["resourceType"] == "ProductSku"
    assert aftersales["authorityRefs"][0]["resourceType"] == "AfterSalesEvent"
    assert inventory["blockers"] == []
    assert inventory["authorityRefs"][0]["receiptId"].startswith("d0-")
    assert aftersales["blockers"][0]["code"] == "AFTERSALE_EVENTS_READER_NOT_WIRED"
    assert catalog.calls == [
        {
            "module_id": "ecommerce.operations",
            "org_id": "org-org",
            "project_id": "dev-project",
            "roles": ["operator"],
            "markings": ["public"],
        }
    ]


def test_operations_api_rejects_scope_injection_and_non_get_methods() -> None:
    with _client() as client:
        injected = client.get(
            "/v1/ecommerce-workshop/views/operations?orgId=dev-org"
        )
        posted = client.post("/v1/ecommerce-workshop/views/operations")

    assert injected.status_code == 400
    assert injected.json()["code"] == "VALIDATION"
    assert posted.status_code == 405


def test_operations_api_fails_closed_when_module_is_not_installed() -> None:
    with _client(FakeCatalog(installed=False)) as client:
        response = client.get("/v1/ecommerce-workshop/views/operations")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_openapi_exposes_only_the_operations_get_surface() -> None:
    with _client() as client:
        document = client.get("/openapi.json").json()

    surface = document["paths"]["/v1/ecommerce-workshop/views/operations"]
    assert set(surface) == {"get"}
    assert surface["get"]["operationId"] == "ecommerceWorkshopOperationsViewGet"
