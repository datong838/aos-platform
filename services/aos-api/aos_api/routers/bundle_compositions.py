"""Canonical HTTP adapter for immutable bundle composition locks."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Path, Request, Security, status
from fastapi.security import HTTPBearer

from aos_api.asset_registry.composition_contracts import (
    CompositionRequest,
    StoredCompositionLock,
)
from aos_api.asset_registry.control_protocols import CompositionControl
from aos_api.asset_registry.control_wiring import build_composition_service
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError, ErrorBody
from aos_api.routers.asset_control_headers import require_idempotency_key

_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/bundle-compositions",
    tags=["asset-control"],
    dependencies=[Security(_bearer)],
)
_ERRORS = {
    400: {"model": ErrorBody},
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    404: {"model": ErrorBody},
    409: {"model": ErrorBody},
    500: {"model": ErrorBody},
}
_IDEMPOTENCY_PARAMETER = {
    "name": "Idempotency-Key",
    "in": "header",
    "required": True,
    "schema": {"type": "string", "minLength": 1, "maxLength": 160},
}
ResultT = TypeVar("ResultT")
PrincipalDependency = Annotated[Principal, Depends(require_principal)]
CanonicalUuidPath = Annotated[
    str,
    Path(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    ),
]
PositiveRevisionPath = Annotated[int, Path(ge=1)]


@lru_cache(maxsize=1)
def get_composition_service() -> CompositionControl:
    return build_composition_service()


CompositionServiceDependency = Annotated[
    CompositionControl, Depends(get_composition_service)
]


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


@router.post(
    ":resolve",
    response_model=StoredCompositionLock,
    status_code=status.HTTP_201_CREATED,
    operation_id="resolve_bundle_composition",
    responses=_ERRORS,
    openapi_extra={"parameters": [_IDEMPOTENCY_PARAMETER]},
)
def resolve_bundle_composition(
    body: CompositionRequest,
    request: Request,
    principal: PrincipalDependency,
    service: CompositionServiceDependency,
) -> StoredCompositionLock:
    idempotency_key = _invoke(lambda: require_idempotency_key(request))
    receipt = _invoke(
        lambda: service.resolve(
            request=body,
            org_id=principal.org_id,
            project_id=principal.project_id,
            actor=principal.subject,
            roles=principal.roles,
            markings=principal.markings,
            idempotency_key=idempotency_key,
        )
    )
    return StoredCompositionLock.model_validate_json(json.dumps(receipt.response_json))


@router.get(
    "/{composition_id}/locks/{revision}",
    response_model=StoredCompositionLock,
    operation_id="get_bundle_composition_lock",
    responses=_ERRORS,
)
def get_bundle_composition_lock(
    composition_id: CanonicalUuidPath,
    revision: PositiveRevisionPath,
    principal: PrincipalDependency,
    service: CompositionServiceDependency,
) -> StoredCompositionLock:
    return _invoke(
        lambda: service.get_lock(
            org_id=principal.org_id,
            project_id=principal.project_id,
            composition_id=composition_id,
            revision=revision,
            roles=principal.roles,
            markings=principal.markings,
        )
    )
