from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute

from aos_api.routers import ecommerce_workshop, extension_dispatch


COMMANDS = {
    "ecommerceWorkshopBackgroundProcessingConfigure": (
        "/v1/ecommerce-workshop/background-processing/configure",
        {"POST"},
    ),
    "ecommerceWorkshopBackgroundProcessingDisable": (
        "/v1/ecommerce-workshop/background-processing/disable",
        {"POST"},
    ),
    "ecommerceWorkshopBackgroundProcessingRestore": (
        "/v1/ecommerce-workshop/background-processing/restore",
        {"POST"},
    ),
}


def _routes(router) -> dict[str, APIRoute]:
    return {
        route.operation_id: route
        for route in router.routes
        if isinstance(route, APIRoute) and route.operation_id is not None
    }


def test_formal_dispatch_exposes_only_the_three_bounded_workshop_commands():
    source = _routes(ecommerce_workshop.router)
    formal = _routes(extension_dispatch.router)
    source_writes = {
        operation_id
        for operation_id, route in source.items()
        if route.methods and not route.methods.issubset({"GET", "HEAD"})
    }

    assert source_writes & formal.keys() == COMMANDS.keys()
    for operation_id, (path, methods) in COMMANDS.items():
        assert formal[operation_id].path == path
        assert formal[operation_id].methods == methods


def test_formal_openapi_contains_status_and_exact_business_command_paths():
    app = FastAPI()
    app.include_router(extension_dispatch.router)
    paths = app.openapi()["paths"]

    assert set(paths["/v1/ecommerce-workshop/background-processing"]) == {"get"}
    for path, _methods in COMMANDS.values():
        assert set(paths[path]) == {"post"}
