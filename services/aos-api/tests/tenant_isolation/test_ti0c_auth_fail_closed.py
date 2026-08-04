from __future__ import annotations

import importlib

import pytest
from aos_api.auth import require_principal
from fastapi.routing import APIRoute

PROTECTED_ROUTER_MODULES = (
    "aos_api.routers.phase5_pipelines",
    "aos_api.routers.phase6_agents",
    "aos_api.routers.phase6_connectors",
    "aos_api.routers.phase6_documents",
    "aos_api.routers.phase6_media_sets",
    "aos_api.routers.phase6_schemas",
    "aos_api.routers.phase6_sources",
    "aos_api.routers.phase6_syncs",
    "aos_api.routers.pipelines",
    "aos_api.routers.modules_config",
    "aos_api.routers.modules_deployments",
    "aos_api.routers.modules_interface",
    "aos_api.routers.modules_queries",
    "aos_api.routers.modules_variables",
    "aos_api.routers.modules_widgets",
    "aos_api.module_events_router",
)

UNAUTHENTICATED_REQUESTS = (
    ("GET", "/v1/pipelines"),
    ("GET", "/api/datasource/agents"),
    ("GET", "/api/datasource/connectors"),
    ("GET", "/api/datasource/documents"),
    ("GET", "/api/datasource/media-sets/example"),
    ("GET", "/api/datasource/sources/example/schemas"),
    ("GET", "/api/datasource/sources"),
    ("GET", "/api/datasource/syncs"),
    ("GET", "/v1/pipeline-builder"),
    ("GET", "/v1/modules/example/config"),
    ("GET", "/v1/modules/example/deployments"),
    ("GET", "/v1/modules/example/interface"),
    ("GET", "/v1/modules/example/queries"),
    ("GET", "/v1/modules/example/variables"),
    ("GET", "/v1/modules/example/widgets"),
    ("GET", "/v1/modules/example/events"),
)


@pytest.mark.parametrize("module_name", PROTECTED_ROUTER_MODULES)
def test_ti0c_business_router_has_principal_gate(module_name: str) -> None:
    router = importlib.import_module(module_name).router
    routes = [route for route in router.routes if isinstance(route, APIRoute)]

    assert routes
    for route in routes:
        assert any(
            dependency.call is require_principal
            for dependency in route.dependant.dependencies
        ), f"{module_name}:{route.path} is missing require_principal"


def test_ti0c_business_routes_reject_missing_token(client) -> None:
    for method, path in UNAUTHENTICATED_REQUESTS:
        response = client.request(method, path)

        assert response.status_code == 401, (method, path, response.text)
        assert response.json()["code"] == "AUTH_REQUIRED"
