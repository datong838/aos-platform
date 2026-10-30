"""Single production HTTP entrypoint for installed extension routes."""

from __future__ import annotations

from fastapi import APIRouter

from aos_api.routers import ecommerce_business_investigations
from aos_api.routers import ecommerce_growth_dispatch
from aos_api.routers import ecommerce_workshop


_READ_ONLY_METHODS = frozenset({"GET", "HEAD"})
_ROUTE_WORKER_BUSINESS_COMMANDS = {
    "ecommerceWorkshopBackgroundProcessingConfigure": (
        "/v1/ecommerce-workshop/background-processing/configure",
        frozenset({"POST"}),
    ),
    "ecommerceWorkshopBackgroundProcessingDisable": (
        "/v1/ecommerce-workshop/background-processing/disable",
        frozenset({"POST"}),
    ),
    "ecommerceWorkshopBackgroundProcessingRestore": (
        "/v1/ecommerce-workshop/background-processing/restore",
        frozenset({"POST"}),
    ),
}

router = APIRouter(tags=["extension-dispatch"])
router.include_router(ecommerce_growth_dispatch.router)


def _include_legacy_read_routes(source: APIRouter) -> None:
    """Keep installed read projections without retaining legacy write paths."""

    for route in source.routes:
        methods = getattr(route, "methods", None)
        if methods and set(methods).issubset(_READ_ONLY_METHODS):
            router.routes.append(route)


def _include_route_worker_business_commands(source: APIRouter) -> None:
    """Expose only the reviewed route-worker commands and fail closed on drift."""

    selected = {}
    for route in source.routes:
        operation_id = getattr(route, "operation_id", None)
        if operation_id not in _ROUTE_WORKER_BUSINESS_COMMANDS:
            continue

        expected_path, expected_methods = _ROUTE_WORKER_BUSINESS_COMMANDS[operation_id]
        actual_methods = frozenset(getattr(route, "methods", None) or ())
        if (
            operation_id in selected
            or getattr(route, "path", None) != expected_path
            or actual_methods != expected_methods
        ):
            raise RuntimeError(
                f"route-worker business command contract drift: {operation_id}"
            )
        selected[operation_id] = route

    missing = set(_ROUTE_WORKER_BUSINESS_COMMANDS) - set(selected)
    if missing:
        raise RuntimeError(
            "route-worker business commands missing: " + ", ".join(sorted(missing))
        )

    for operation_id in _ROUTE_WORKER_BUSINESS_COMMANDS:
        router.routes.append(selected[operation_id])


_include_legacy_read_routes(ecommerce_workshop.router)
_include_route_worker_business_commands(ecommerce_workshop.router)
_include_legacy_read_routes(ecommerce_business_investigations.router)


__all__ = ["router"]
