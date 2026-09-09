from __future__ import annotations

import ast
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostBlocked, EcommerceGrowthHostConflict
from aos_api.errors import register_exception_handlers
from aos_api.tenant_scope import TenantScope


SOURCE = Path(__file__).resolve().parents[2] / "aos_api" / "routers" / "ecommerce_growth_dispatch.py"
FORBIDDEN_IMPORTS = {
    "aos_api.ecommerce_business_investigation_application",
    "aos_api.ecommerce_business_investigation_case",
    "aos_api.ecommerce_business_investigation_schedule",
    "aos_api.ecommerce_business_investigation_review_command",
    "aos_api.ecommerce_business_investigation_handoff",
    "aos_api.ecommerce_content_campaign_workflow",
}

RECEIPT = {
    "receiptRef": {
        "resourceType": "BusinessInvestigationCase",
        "resourceId": "case-qyh-001",
        "revision": 3,
        "contentHash": "sha256:" + "a" * 64,
        "receiptId": "receipt-qyh-001",
    }
}


def _principal() -> Principal:
    return Principal(
        subject="operator-1",
        org_id="org-org",
        project_id="dev-project",
        roles=["admin"],
        markings=["public"],
    )


class FakeCanonicalRouter:
    def __init__(self, error=None, payload=RECEIPT):
        self.error = error
        self.payload = payload
        self.calls = []

    def dispatch(self, *, scope, operation_id, command, occurred_at=None):
        self.calls.append(
            {
                "scope": scope,
                "operation_id": operation_id,
                "command": command,
                "occurred_at": occurred_at,
            }
        )
        if self.error is not None:
            raise self.error
        return self.payload


def _app(canonical=None):
    from aos_api.routers import ecommerce_growth_dispatch

    app = FastAPI()
    app.include_router(ecommerce_growth_dispatch.router)
    app.dependency_overrides[require_principal] = _principal
    if canonical is not None:
        app.dependency_overrides[ecommerce_growth_dispatch.get_canonical_router] = lambda: canonical
    register_exception_handlers(app)
    return app


def test_dispatch_http_source_does_not_import_legacy_write_services():
    tree = ast.parse(SOURCE.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not imported.intersection(FORBIDDEN_IMPORTS)


def test_dispatch_http_posts_command_through_canonical_router():
    canonical = FakeCanonicalRouter()
    response = TestClient(_app(canonical)).post(
        "/v1/ecommerce-growth/operations/ecommerce_growth_case_put",
        json={"idempotencyKey": "case-1", "businessTitle": "栖月汇经营分析"},
        headers={"Authorization": "Bearer ignored"},
    )
    assert response.status_code == 200
    assert response.json() == RECEIPT
    assert len(canonical.calls) == 1
    call = canonical.calls[0]
    assert type(call["scope"]) is TenantScope
    assert call["scope"].key == ("org-org", "dev-project")
    assert call["operation_id"] == "ecommerce_growth_case_put"
    assert call["command"] == {"idempotencyKey": "case-1", "businessTitle": "栖月汇经营分析"}


def test_dispatch_http_rejects_unknown_operation_without_canonical_call():
    canonical = FakeCanonicalRouter()
    response = TestClient(_app(canonical)).post(
        "/v1/ecommerce-growth/operations/ecommerce_growth_secret_export",
        json={"businessTitle": "栖月汇"},
        headers={"Authorization": "Bearer ignored"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ECOMMERCE_GROWTH_UNKNOWN_OPERATION"
    assert canonical.calls == []


def test_dispatch_http_maps_runtime_wiring_required_to_unavailable():
    canonical = FakeCanonicalRouter(error=EcommerceGrowthHostBlocked("AR2_7D_RUNTIME_WIRING_REQUIRED"))
    response = TestClient(_app(canonical)).post(
        "/v1/ecommerce-growth/operations/ecommerce_growth_case_put",
        json={"businessTitle": "栖月汇经营分析"},
        headers={"Authorization": "Bearer ignored"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "AR2_7D_RUNTIME_WIRING_REQUIRED"
    assert canonical.calls[0]["operation_id"] == "ecommerce_growth_case_put"


def test_dispatch_http_maps_authority_conflict():
    canonical = FakeCanonicalRouter(error=EcommerceGrowthHostConflict("exact dispatch authority drifted"))
    response = TestClient(_app(canonical)).post(
        "/v1/ecommerce-growth/operations/ecommerce_growth_schedule_put",
        json={"idempotencyKey": "schedule-1"},
        headers={"Authorization": "Bearer ignored"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ECOMMERCE_GROWTH_DISPATCH_CONFLICT"


def test_dispatch_http_exposes_all_nine_signed_operations():
    from aos_api.routers.ecommerce_growth_dispatch import router

    paths = {route.path for route in router.routes}
    assert paths == {"/v1/ecommerce-growth/operations/{operation_id}"}
    assert ECOMMERCE_GROWTH_OPERATIONS == (
        "ecommerce_growth_investigation_describe",
        "ecommerce_growth_case_put",
        "ecommerce_growth_schedule_put",
        "ecommerce_growth_schedule_trigger",
        "ecommerce_growth_data_fulfill",
        "ecommerce_growth_analysis_advance",
        "ecommerce_growth_review_advance",
        "ecommerce_growth_content_generate",
        "ecommerce_growth_content_review",
    )
