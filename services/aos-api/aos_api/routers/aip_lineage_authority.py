"""Canonical tenant-scoped AIP lineage projection and query endpoints."""

# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends

from aos_api.aip_eval_contracts import LineageEvent, LineageRootType
from aos_api.aip_lineage_service import (
    AipLineageConflict,
    AipLineageNotFound,
    AipLineagePersistenceError,
    AipLineageService,
    AipLineageUnsupportedRoot,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/lineage-authority", tags=["aip-lineage-authority"])
_SERVICE = AipLineageService()


def get_aip_lineage_service() -> AipLineageService:
    return _SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, AipLineageNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipLineageConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipLineageUnsupportedRoot):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, AipLineagePersistenceError):
        return ApiError(
            code=exc.code,
            message="lineage authority persistence is unavailable",
            status_code=503,
        )
    return ApiError(
        code="AIP_LINEAGE_AUTHORITY_FAILED",
        message="lineage authority operation failed",
        status_code=500,
    )


@router.get(
    "/roots/{root_type}/{root_id}",
    response_model=list[LineageEvent],
)
def list_lineage_events(
    root_type: LineageRootType,
    root_id: str,
    principal: Principal = Depends(require_principal),
    service: AipLineageService = Depends(get_aip_lineage_service),
) -> list[LineageEvent]:
    try:
        return service.list_events(_scope(principal), root_type, root_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/roots/{root_type}/{root_id}/reconcile",
    response_model=list[LineageEvent],
)
def reconcile_lineage(
    root_type: LineageRootType,
    root_id: str,
    principal: Principal = Depends(require_principal),
    service: AipLineageService = Depends(get_aip_lineage_service),
) -> list[LineageEvent]:
    if not {role.lower() for role in principal.roles}.intersection(
        {"admin", "executor", "aip_executor"}
    ):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted runtime role required for lineage reconciliation",
            status_code=403,
        )
    try:
        return service.reconcile(_scope(principal), root_type, root_id)
    except Exception as exc:
        raise _map_error(exc) from exc


__all__ = ["get_aip_lineage_service", "router"]
