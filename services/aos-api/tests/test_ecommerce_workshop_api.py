"""Canonical W1 ecommerce Workshop HTTP contract tests."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_workshop_contracts import (
    EcommerceWorkshopModuleListResponse,
    EcommerceWorkshopModuleReadinessResponse,
)
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop

NOW = datetime(2026, 8, 14, tzinfo=UTC)


def _module():
    return {
        "moduleId": "ecommerce.operations",
        "displayName": "统一运营驾驶舱",
        "menuLabel": "统一运营驾驶舱",
        "route": "/workshop/operations",
        "slot": "workshop.primary.ecommerce",
        "order": 30,
        "installationRef": {
            "installationId": "11111111-1111-4111-8111-111111111111",
            "revision": 5,
            "compositionId": "22222222-2222-4222-8222-222222222222",
            "lockRevision": 1,
            "lockHash": "sha256:" + "a" * 64,
            "overlayRevision": "overlay-5",
        },
        "moduleRef": {
            "publisher": "aos",
            "bundleId": "solution.ecommerce.operations-base",
            "version": "1.1.0",
            "bundleContentHash": "sha256:" + "b" * 64,
            "moduleArtifactRef": "bundle://catalog/solutions/ecommerce-operations-base/content/workshops/ecommerce.operations.json",
            "moduleArtifactHash": "sha256:" + "c" * 64,
        },
        "readiness": "unknown",
        "blockers": [
            {
                "dependencyType": "aip_feature",
                "dependencyId": "aip.task-runtime",
                "state": "unknown",
                "reasonCode": "AIP_FEATURE_UNVERIFIED",
                "recoverable": True,
                "requiredAction": "等待 canonical reader 回读",
                "ref": None,
            }
        ],
        "permissions": {
            "roles": [],
            "markings": [],
            "dataScopes": ["ecommerce.workshop.read"],
            "actionTypes": [],
        },
        "requiredObjects": ["Order"],
        "requiredCapabilities": ["performance.review"],
        "requiredAipFeatures": ["aip.task-runtime"],
        "viewRefs": [],
        "evalPackRefs": [],
        "productionContractRefs": [],
        "responsibilityTemplateRefs": [],
        "impactCalculatorRefs": [],
        "legacyAssetRefs": [],
        "legacyRoutes": ["/workshop/orders"],
        "minimumRuntimeVersion": "1.7.0",
        "lastReceiptRef": None,
    }


class FakeCatalog:
    def __init__(self):
        self.calls = []

    def list_modules(self, **kwargs):
        self.calls.append(("list", kwargs))
        return EcommerceWorkshopModuleListResponse.model_validate(
            {
                "schemaVersion": "aos.ecommerce-workshop/v1",
                "tenant": {"orgId": kwargs["org_id"], "projectId": kwargs["project_id"]},
                "evaluatedAt": NOW,
                "dataCutoff": None,
                "items": [_module()],
                "count": 1,
            }
        )

    def get_readiness(self, **kwargs):
        self.calls.append(("readiness", kwargs))
        if kwargs["module_id"] == "ecommerce.not-installed":
            raise AssetNotFoundError("Workshop module is not installed")
        return EcommerceWorkshopModuleReadinessResponse.model_validate(
            {
                "schemaVersion": "aos.ecommerce-workshop/v1",
                "tenant": {"orgId": kwargs["org_id"], "projectId": kwargs["project_id"]},
                "evaluatedAt": NOW,
                "dataCutoff": None,
                "item": _module(),
            }
        )


def _client(catalog: FakeCatalog) -> TestClient:
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
    app.dependency_overrides[ecommerce_workshop.get_ecommerce_workshop_catalog] = lambda: catalog
    return TestClient(app, raise_server_exceptions=False)


def test_routes_use_principal_tenant_and_have_no_scope_injection_surface() -> None:
    catalog = FakeCatalog()
    with _client(catalog) as client:
        response = client.get("/v1/ecommerce-workshop/modules")
        assert response.status_code == 200
        assert response.json()["tenant"] == {
            "orgId": "org-org",
            "projectId": "dev-project",
        }
        injected = client.get(
            "/v1/ecommerce-workshop/modules?orgId=dev-org&projectId=other"
        )
        assert injected.status_code == 400
        assert injected.json()["code"] == "VALIDATION"
        duplicated = client.get(
            "/v1/ecommerce-workshop/modules/ecommerce.operations/readiness?x=1&x=2"
        )
        assert duplicated.status_code == 400
        readiness = client.get(
            "/v1/ecommerce-workshop/modules/ecommerce.operations/readiness"
        )
        assert readiness.status_code == 200

    assert all(call[1]["org_id"] == "org-org" for call in catalog.calls)
    assert all(call[1]["project_id"] == "dev-project" for call in catalog.calls)
    assert all("org_id" not in call[1].get("body", {}) for call in catalog.calls)
    assert [call[0] for call in catalog.calls] == ["list", "readiness"]


def test_not_installed_and_invalid_module_id_fail_explicitly() -> None:
    with _client(FakeCatalog()) as client:
        missing = client.get(
            "/v1/ecommerce-workshop/modules/ecommerce.not-installed/readiness"
        )
        assert missing.status_code == 404
        assert missing.json()["code"] == "NOT_FOUND"
        invalid = client.get(
            "/v1/ecommerce-workshop/modules/other-module/readiness"
        )
        assert invalid.status_code == 400
        assert invalid.json()["code"] == "VALIDATION"


def test_openapi_freezes_w1_and_w2_core_operations_and_no_writes() -> None:
    app = FastAPI()
    app.include_router(ecommerce_workshop.router)
    schema = app.openapi()
    operations = {
        operation["operationId"]: (path, method)
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert operations == {
        "ecommerceWorkshopModulesList": (
            "/v1/ecommerce-workshop/modules",
            "get",
        ),
        "ecommerceWorkshopModuleReadinessGet": (
            "/v1/ecommerce-workshop/modules/{module_id}/readiness",
            "get",
        ),
        "ecommerceWorkshopTaskCockpitCoreGet": (
            "/v1/ecommerce-workshop/views/task-cockpit",
            "get",
        ),
    }
    assert all(method == "get" for _, method in operations.values())
