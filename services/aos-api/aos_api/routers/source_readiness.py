"""Principal-scoped, read-only SourceReadiness API."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Security
from fastapi.security import HTTPBearer

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError, ErrorBody
from aos_api.source_readiness import (
    SourceReadinessService,
    build_source_readiness_service,
)
from aos_api.source_readiness_contracts import SourceReadinessEnvelope


_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/data",
    tags=["source-readiness"],
    dependencies=[Security(_bearer)],
)
_ERRORS = {
    400: {"model": ErrorBody},
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    500: {"model": ErrorBody},
}
PrincipalDependency = Annotated[Principal, Depends(require_principal)]


@lru_cache(maxsize=1)
def get_source_readiness_service() -> SourceReadinessService:
    return build_source_readiness_service()


ServiceDependency = Annotated[
    SourceReadinessService, Depends(get_source_readiness_service)
]


@router.get(
    "/source-readiness",
    response_model=SourceReadinessEnvelope,
    operation_id="dataSourceReadinessGet",
    responses=_ERRORS,
)
def get_source_readiness(
    request: Request,
    principal: PrincipalDependency,
    service: ServiceDependency,
) -> SourceReadinessEnvelope:
    if request.query_params:
        raise ApiError(
            code="VALIDATION",
            message="SourceReadiness reads do not accept query parameters",
            status_code=400,
        )
    return service.read(org_id=principal.org_id, project_id=principal.project_id)
