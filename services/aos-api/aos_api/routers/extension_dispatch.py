"""Single production HTTP entrypoint for installed extension routes."""

from __future__ import annotations

from fastapi import APIRouter

from aos_api.routers import ecommerce_business_investigations
from aos_api.routers import ecommerce_growth_dispatch
from aos_api.routers import ecommerce_workshop


_READ_ONLY_METHODS = frozenset({"GET", "HEAD"})

router = APIRouter(tags=["extension-dispatch"])
router.include_router(ecommerce_growth_dispatch.router)


def _include_legacy_read_routes(source: APIRouter) -> None:
    """Keep installed read projections without retaining legacy write paths."""

    for route in source.routes:
        methods = getattr(route, "methods", None)
        if methods and set(methods).issubset(_READ_ONLY_METHODS):
            router.routes.append(route)


_include_legacy_read_routes(ecommerce_workshop.router)
_include_legacy_read_routes(ecommerce_business_investigations.router)


__all__ = ["router"]
