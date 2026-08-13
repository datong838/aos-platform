"""Canonical read-only HTTP adapter for the ecommerce Workshop catalog."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Path, Request, Security
from fastapi.security import HTTPBearer

from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_workshop_catalog import (
    EcommerceWorkshopCatalog,
    build_ecommerce_workshop_catalog,
)
from aos_api.ecommerce_workshop_contracts import (
    EcommerceWorkshopModuleListResponse,
    EcommerceWorkshopModuleReadinessResponse,
)
from aos_api.errors import ApiError, ErrorBody

_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/ecommerce-workshop",
    tags=["ecommerce-workshop"],
    dependencies=[Security(_bearer)],
)
_ERRORS = {
    400: {"model": ErrorBody},
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    404: {"model": ErrorBody},
    500: {"model": ErrorBody},
}
PrincipalDependency = Annotated[Principal, Depends(require_principal)]
ModuleIdPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=160,
        pattern=r"^ecommerce[.][a-z0-9]+(?:[.-][a-z0-9]+)*$",
    ),
]
ResultT = TypeVar("ResultT")


@lru_cache(maxsize=1)
def get_ecommerce_workshop_catalog() -> EcommerceWorkshopCatalog:
    return build_ecommerce_workshop_catalog()


CatalogDependency = Annotated[
    EcommerceWorkshopCatalog, Depends(get_ecommerce_workshop_catalog)
]


def _reject_query_parameters(request: Request) -> None:
    if request.query_params:
        raise ApiError(
            code="VALIDATION",
            message="ecommerce Workshop reads do not accept query parameters",
            status_code=400,
        )


def _invoke(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except AssetRegistryError as exc:
        raise ApiError(
            code=exc.code.value,
            message=str(exc),
            status_code=exc.http_status,
            details=exc.details,
        ) from exc


@router.get(
    "/modules",
    response_model=EcommerceWorkshopModuleListResponse,
    operation_id="ecommerceWorkshopModulesList",
    responses=_ERRORS,
)
def list_ecommerce_workshop_modules(
    request: Request,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
) -> EcommerceWorkshopModuleListResponse:
    _reject_query_parameters(request)
    return _invoke(
        lambda: catalog.list_modules(
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


@router.get(
    "/modules/{module_id}/readiness",
    response_model=EcommerceWorkshopModuleReadinessResponse,
    operation_id="ecommerceWorkshopModuleReadinessGet",
    responses=_ERRORS,
)
def get_ecommerce_workshop_module_readiness(
    request: Request,
    module_id: ModuleIdPath,
    principal: PrincipalDependency,
    catalog: CatalogDependency,
) -> EcommerceWorkshopModuleReadinessResponse:
    _reject_query_parameters(request)
    return _invoke(
        lambda: catalog.get_readiness(
            module_id=module_id,
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )
