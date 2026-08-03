"""Canonical HTTP adapter for the bundle installation control plane."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, Path, Query, Request, Response, Security, status
from fastapi.security import HTTPBearer

from aos_api.asset_registry.composition_contracts import (
    MAX_INSTALLATION_LIST_LIMIT,
    MAX_INSTALLATION_LIST_OFFSET,
    ApproveInstallationRequest,
    CreateInstallationRequest,
    EmptyInstallationActionRequest,
    InstallationListQuery,
    InstallationListResponse,
    InstallationResponse,
    InstallationState,
    RejectInstallationRequest,
    RollbackInstallationRequest,
)
from aos_api.asset_registry.control_protocols import InstallationControl
from aos_api.asset_registry.control_wiring import build_installation_service
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError, ErrorBody
from aos_api.routers.asset_control_headers import (
    require_idempotency_key,
    require_if_match,
)

_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/bundle-installations",
    tags=["asset-control"],
    dependencies=[Security(_bearer)],
)
_ERRORS = {
    400: {"model": ErrorBody},
    401: {"model": ErrorBody},
    403: {"model": ErrorBody},
    404: {"model": ErrorBody},
    409: {"model": ErrorBody},
    412: {"model": ErrorBody},
    428: {"model": ErrorBody},
    500: {"model": ErrorBody},
}
_IDEMPOTENCY_PARAMETER = {
    "name": "Idempotency-Key",
    "in": "header",
    "required": True,
    "schema": {"type": "string", "minLength": 1, "maxLength": 160},
}
_IF_MATCH_PARAMETER = {
    "name": "If-Match",
    "in": "header",
    "required": True,
    "schema": {"type": "string", "pattern": '^"[1-9][0-9]*"$'},
}
_ETAG_HEADER = {
    "ETag": {
        "description": "Strong installation revision validator.",
        "schema": {"type": "string"},
    }
}
ResultT = TypeVar("ResultT")
PrincipalDependency = Annotated[Principal, Depends(require_principal)]
CanonicalUuidPath = Annotated[
    str,
    Path(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    ),
]
ListLimitQuery = Annotated[int, Query(ge=1, le=MAX_INSTALLATION_LIST_LIMIT)]
ListOffsetQuery = Annotated[int, Query(ge=0, le=MAX_INSTALLATION_LIST_OFFSET)]


@lru_cache(maxsize=1)
def get_installation_service() -> InstallationControl:
    return build_installation_service()


InstallationServiceDependency = Annotated[
    InstallationControl, Depends(get_installation_service)
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


def _receipt_response(receipt: Any, response: Response) -> InstallationResponse:
    if receipt.response_etag is not None:
        response.headers["ETag"] = receipt.response_etag
    return InstallationResponse.model_validate_json(json.dumps(receipt.response_json))


@router.post(
    "",
    response_model=InstallationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_bundle_installation",
    responses={201: {"headers": _ETAG_HEADER}, **_ERRORS},
    openapi_extra={"parameters": [_IDEMPOTENCY_PARAMETER]},
)
def create_bundle_installation(
    body: CreateInstallationRequest,
    request: Request,
    response: Response,
    principal: PrincipalDependency,
    service: InstallationServiceDependency,
) -> InstallationResponse:
    key = _invoke(lambda: require_idempotency_key(request))
    receipt = _invoke(
        lambda: service.create(
            request=body,
            org_id=principal.org_id,
            project_id=principal.project_id,
            actor=principal.subject,
            roles=principal.roles,
            markings=principal.markings,
            idempotency_key=key,
        )
    )
    return _receipt_response(receipt, response)


@router.get(
    "",
    response_model=InstallationListResponse,
    operation_id="list_bundle_installations",
    responses=_ERRORS,
)
def list_bundle_installations(
    principal: PrincipalDependency,
    service: InstallationServiceDependency,
    state: InstallationState | None = None,
    limit: ListLimitQuery = 50,
    offset: ListOffsetQuery = 0,
) -> InstallationListResponse:
    query = InstallationListQuery.model_validate(
        {"state": state, "limit": limit, "offset": offset}
    )
    return _invoke(
        lambda: service.list(
            query=query,
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )


@router.get(
    "/{installation_id}",
    response_model=InstallationResponse,
    operation_id="get_bundle_installation",
    responses={200: {"headers": _ETAG_HEADER}, **_ERRORS},
)
def get_bundle_installation(
    installation_id: CanonicalUuidPath,
    response: Response,
    principal: PrincipalDependency,
    service: InstallationServiceDependency,
) -> InstallationResponse:
    result = _invoke(
        lambda: service.get(
            installation_id=installation_id,
            org_id=principal.org_id,
            project_id=principal.project_id,
            roles=principal.roles,
            markings=principal.markings,
        )
    )
    response.headers["ETag"] = f'"{result.etag_version}"'
    return result


def _action(
    *,
    operation: str,
    installation_id: str,
    body: Any,
    request: Request,
    response: Response,
    principal: Principal,
    service: InstallationControl,
) -> InstallationResponse:
    key = _invoke(lambda: require_idempotency_key(request))
    if_match = _invoke(lambda: require_if_match(request))
    method = getattr(service, operation)
    receipt = _invoke(
        lambda: method(
            installation_id=installation_id,
            request=body,
            org_id=principal.org_id,
            project_id=principal.project_id,
            actor=principal.subject,
            roles=principal.roles,
            markings=principal.markings,
            idempotency_key=key,
            if_match=if_match,
        )
    )
    return _receipt_response(receipt, response)


def _action_route(operation: str, request_type: type, operation_id: str):
    def endpoint(
        installation_id: CanonicalUuidPath,
        body: request_type,
        request: Request,
        response: Response,
        principal: PrincipalDependency,
        service: InstallationServiceDependency,
    ) -> InstallationResponse:
        return _action(
            operation=operation,
            installation_id=installation_id,
            body=body,
            request=request,
            response=response,
            principal=principal,
            service=service,
        )

    endpoint.__name__ = operation_id
    endpoint.__annotations__["body"] = request_type
    return router.post(
        f"/{{installation_id}}/{operation}",
        response_model=InstallationResponse,
        operation_id=operation_id,
        responses={200: {"headers": _ETAG_HEADER}, **_ERRORS},
        openapi_extra={"parameters": [_IDEMPOTENCY_PARAMETER, _IF_MATCH_PARAMETER]},
    )(endpoint)


submit_bundle_installation = _action_route(
    "submit", EmptyInstallationActionRequest, "submit_bundle_installation"
)
approve_bundle_installation = _action_route(
    "approve", ApproveInstallationRequest, "approve_bundle_installation"
)
reject_bundle_installation = _action_route(
    "reject", RejectInstallationRequest, "reject_bundle_installation"
)
apply_bundle_installation = _action_route(
    "apply", EmptyInstallationActionRequest, "apply_bundle_installation"
)
verify_bundle_installation = _action_route(
    "verify", EmptyInstallationActionRequest, "verify_bundle_installation"
)
rollback_bundle_installation = _action_route(
    "rollback", RollbackInstallationRequest, "rollback_bundle_installation"
)
