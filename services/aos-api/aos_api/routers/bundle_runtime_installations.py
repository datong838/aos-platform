"""Canonical HTTP adapter for extension-runtime installation controls."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Request, Response, Security, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator

from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError, ErrorBody
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict
from aos_api.extension_runtime.runtime_view import RuntimeInstallationView, RuntimeOperationView
from aos_api.routers.asset_control_headers import require_idempotency_key, require_if_match


_bearer = HTTPBearer(auto_error=False)
router = APIRouter(
    prefix="/v1/bundle-runtime-installations",
    tags=["asset-control"],
    dependencies=[Security(_bearer)],
)
PrincipalDependency = Annotated[Principal, Depends(require_principal)]
CanonicalUuidPath = Annotated[
    str,
    Path(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"),
]


class RuntimeOperationRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)

    kind: Literal["runtime-apply", "runtime-verify", "configure", "enable", "disable"]
    target: dict[str, Any] | None = None

    @model_validator(mode="after")
    def target_matches_kind(self) -> "RuntimeOperationRequest":
        if self.kind in {"runtime-apply", "runtime-verify"} and self.target is not None:
            raise ValueError("preparation operations do not accept a target")
        if self.kind in {"configure", "enable", "disable"} and self.target is None:
            raise ValueError("runtime control operation requires an exact target")
        return self


class RuntimeOperationAccepted(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    installationId: str
    operationId: str
    phase: str
    status: str
    revision: int = Field(ge=1)


_ERRORS = {
    400: {"model": ErrorBody}, 401: {"model": ErrorBody}, 403: {"model": ErrorBody},
    404: {"model": ErrorBody}, 409: {"model": ErrorBody}, 412: {"model": ErrorBody},
    422: {"model": ErrorBody}, 428: {"model": ErrorBody}, 500: {"model": ErrorBody},
    503: {"model": ErrorBody},
}
_IDEMPOTENCY_PARAMETER = {
    "name": "Idempotency-Key", "in": "header", "required": True,
    "schema": {"type": "string", "minLength": 1, "maxLength": 160},
}
_IF_MATCH_PARAMETER = {
    "name": "If-Match", "in": "header", "required": True,
    "schema": {"type": "string", "pattern": '^"[1-9][0-9]*"$'},
}
_ETAG_HEADER = {"ETag": {"description": "Strong runtime operation revision validator.", "schema": {"type": "string"}}}


def get_runtime_control_plane(request: Request) -> Any:
    control_plane = getattr(request.app.state, "extension_runtime_control_plane", None)
    if control_plane is None:
        raise ApiError(
            code="RUNTIME_CONTROL_UNAVAILABLE",
            message="运行控制服务当前不可用，请稍后刷新。",
            status_code=503,
        )
    return control_plane


def get_runtime_view_reader(request: Request) -> Any:
    control_plane = getattr(request.app.state, "extension_runtime_control_plane", None)
    if control_plane is not None and getattr(control_plane, "view_reader", None) is not None:
        return control_plane.view_reader
    reader = getattr(request.app.state, "extension_runtime_view_reader", None)
    if reader is None:
        raise ApiError(
            code="RUNTIME_VIEW_UNAVAILABLE",
            message="运行状态读取服务当前不可用，请稍后刷新。",
            status_code=503,
        )
    return reader


ControlPlaneDependency = Annotated[Any, Depends(get_runtime_control_plane)]
RuntimeViewReaderDependency = Annotated[Any, Depends(get_runtime_view_reader)]


def _invoke(operation):
    try:
        return operation()
    except ApiError:
        raise
    except AssetRegistryError as exc:
        raise ApiError(code=exc.code.value, message=str(exc), status_code=exc.http_status, details=exc.details) from exc
    except RuntimeRevisionConflict as exc:
        raise ApiError(code="RUNTIME_REVISION_CONFLICT", message="运行状态已变化，请刷新后重试。", status_code=412) from exc
    except RuntimeConflict as exc:
        raise ApiError(code="RUNTIME_STATE_CONFLICT", message="当前运行状态不允许此操作，请刷新查看进度。", status_code=409) from exc
    except PermissionError as exc:
        raise ApiError(code="RUNTIME_ACCESS_DENIED", message="当前账号无权执行此运行操作。", status_code=403) from exc
    except LookupError as exc:
        raise ApiError(code="RUNTIME_NOT_FOUND", message="未找到当前租户可见的运行记录。", status_code=404) from exc


@router.get(
    "/{installation_id}",
    response_model=RuntimeInstallationView,
    operation_id="get_bundle_runtime_installation",
    responses=_ERRORS,
)
def get_bundle_runtime_installation(
    installation_id: CanonicalUuidPath,
    principal: PrincipalDependency,
    view_reader: RuntimeViewReaderDependency,
) -> RuntimeInstallationView:
    return _invoke(lambda: view_reader.get_installation(
        installation_id=installation_id,
        org_id=principal.org_id,
        project_id=principal.project_id,
        roles=principal.roles,
        markings=principal.markings,
    ))


@router.get(
    "/operations/{operation_id}",
    response_model=RuntimeOperationView,
    operation_id="get_bundle_runtime_operation",
    responses={200: {"headers": _ETAG_HEADER}, **_ERRORS},
)
def get_bundle_runtime_operation(
    operation_id: CanonicalUuidPath,
    response: Response,
    principal: PrincipalDependency,
    view_reader: RuntimeViewReaderDependency,
) -> RuntimeOperationView:
    result = _invoke(lambda: view_reader.get_operation(
        operation_id=operation_id,
        org_id=principal.org_id,
        project_id=principal.project_id,
        roles=principal.roles,
        markings=principal.markings,
    ))
    response.headers["ETag"] = f'"{result.revision}"'
    return result


@router.post(
    "/{installation_id}/operations",
    response_model=RuntimeOperationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="create_bundle_runtime_operation",
    responses={202: {"headers": _ETAG_HEADER}, **_ERRORS},
    openapi_extra={"parameters": [_IDEMPOTENCY_PARAMETER, _IF_MATCH_PARAMETER]},
)
def create_bundle_runtime_operation(
    installation_id: CanonicalUuidPath,
    body: RuntimeOperationRequest,
    request: Request,
    response: Response,
    principal: PrincipalDependency,
    control_plane: ControlPlaneDependency,
) -> RuntimeOperationAccepted:
    key = _invoke(lambda: require_idempotency_key(request))
    if_match = _invoke(lambda: require_if_match(request))
    common = dict(
        installation_id=installation_id,
        org_id=principal.org_id,
        project_id=principal.project_id,
        actor=principal.subject,
        roles=principal.roles,
        markings=principal.markings,
        idempotency_key=key,
        if_match=if_match,
    )
    if body.kind in {"runtime-apply", "runtime-verify"}:
        receipt = _invoke(lambda: control_plane.lifecycle_service.request_preparation(kind=body.kind, **common))
    elif body.kind in {"configure", "enable"}:
        receipt = _invoke(lambda: control_plane.configuration_service.request(kind=body.kind, target=body.target, **common))
    else:
        receipt = _invoke(lambda: control_plane.disable_service.request(target=body.target, **common))
    if receipt.response_etag is not None:
        response.headers["ETag"] = receipt.response_etag
    result = RuntimeOperationAccepted.model_validate(receipt.response_json)
    response.headers["Location"] = f"/v1/bundle-runtime-installations/operations/{result.operationId}"
    return result
