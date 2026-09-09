"""HTTP adapter for ecommerce growth Canonical Router dispatch."""

from __future__ import annotations

from typing import Annotated, Any, Mapping

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPBearer

from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter
from aos_api.ecommerce_growth_host_composition import (
    ECOMMERCE_GROWTH_OPERATIONS,
    select_ecommerce_growth_registry,
)
from aos_api.ecommerce_growth_host_ports import (
    EcommerceGrowthHostBlocked,
    EcommerceGrowthHostConflict,
    EcommerceGrowthHostError,
)
from aos_api.errors import ApiError, ErrorBody
from aos_api.tenant_scope import TenantScope


_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/ecommerce-growth/operations",
    tags=["ecommerce-growth-dispatch"],
    dependencies=[Security(_bearer)],
)
_ERRORS = {
    400: {"model": ErrorBody},
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    409: {"model": ErrorBody},
    503: {"model": ErrorBody},
}
PrincipalDependency = Annotated[Principal, Depends(require_principal)]


def get_canonical_router() -> EcommerceGrowthCanonicalRouter:
    return EcommerceGrowthCanonicalRouter(select_ecommerce_growth_registry())


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, ApiError):
        return exc
    if isinstance(exc, EcommerceGrowthHostConflict):
        return ApiError(
            code="ECOMMERCE_GROWTH_DISPATCH_CONFLICT",
            message="ecommerce growth dispatch authority drifted",
            status_code=409,
        )
    if isinstance(exc, EcommerceGrowthHostBlocked):
        reason = str(exc)
        if "AR2_7D_RUNTIME_WIRING_REQUIRED" in reason:
            return ApiError(
                code="AR2_7D_RUNTIME_WIRING_REQUIRED",
                message="ecommerce growth runtime wiring is not enabled",
                status_code=503,
            )
        return ApiError(
            code="ECOMMERCE_GROWTH_DISPATCH_BLOCKED",
            message="ecommerce growth dispatch is not executable",
            status_code=409,
        )
    if isinstance(exc, EcommerceGrowthHostError):
        return ApiError(
            code="ECOMMERCE_GROWTH_DISPATCH_FAILED",
            message="ecommerce growth dispatch failed",
            status_code=409,
        )
    if isinstance(exc, (TypeError, ValueError)):
        return ApiError(
            code="ECOMMERCE_GROWTH_INVALID_COMMAND",
            message="ecommerce growth command is invalid",
            status_code=400,
        )
    return ApiError(
        code="ECOMMERCE_GROWTH_DISPATCH_FAILED",
        message="ecommerce growth dispatch failed",
        status_code=409,
    )


@router.post(
    "/{operation_id}",
    status_code=200,
    responses=_ERRORS,
    operation_id="ecommerceGrowthDispatch",
)
def dispatch_operation(
    operation_id: str,
    command: dict[str, Any],
    principal: PrincipalDependency,
    canonical: EcommerceGrowthCanonicalRouter = Depends(get_canonical_router),
) -> Mapping[str, Any]:
    if operation_id not in ECOMMERCE_GROWTH_OPERATIONS:
        raise ApiError(
            code="ECOMMERCE_GROWTH_UNKNOWN_OPERATION",
            message="unknown ecommerce growth operation",
            status_code=409,
        )
    try:
        return canonical.dispatch(
            scope=_scope(principal),
            operation_id=operation_id,
            command=command,
        )
    except Exception as exc:
        raise _map_error(exc) from exc
