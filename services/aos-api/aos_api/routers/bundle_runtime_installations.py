"""Canonical HTTP adapter for extension-runtime installation controls."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Query, Request, Response, Security, status
from fastapi.security import HTTPBearer
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from psycopg import Error as DatabaseError

from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest
from aos_api.tenant_scope import TenantScope
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
    request: Request,
    principal: PrincipalDependency,
    view_reader: RuntimeViewReaderDependency,
    requested_route: Annotated[str | None, Query(alias='route', description='唯一工作台路径，长度 1 到 512 字符。')] = None,
) -> RuntimeInstallationView:
    if requested_route is not None:
        from aos_api.extension_runtime.ui_resources import _canonical_route
        if (len(request.query_params.getlist('route')) != 1 or len(requested_route) > 512
                or not _canonical_route(requested_route)):
            raise ApiError(code='RUNTIME_UI_ROUTE_INVALID', message='请提供唯一、有效的工作台路径。', status_code=422)
    return _invoke(lambda: view_reader.get_installation(
        installation_id=installation_id,
        org_id=principal.org_id,
        project_id=principal.project_id,
        roles=principal.roles,
        markings=principal.markings,
        **({'requested_route': requested_route} if requested_route is not None else {}),
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


# First registration creates fenced metadata only; activation is a separate review.
class _RegistrationRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise ApiError(code='REGISTRATION_REQUEST_INVALID', message='登记请求格式不符合要求。', status_code=422) from None
        return safe_handler


_registration_router = APIRouter(route_class=_RegistrationRoute)


def _registration_service(control_plane):
    service = getattr(control_plane, 'first_dispatch_registration_service', None)
    if service is None:
        raise ApiError(code='REGISTRATION_UNAVAILABLE', message='经营入口登记服务尚未配置。', status_code=503)
    return service


def _invoke_registration(operation):
    try:
        return _invoke(operation)
    except ValueError:
        raise ApiError(code='REGISTRATION_TARGET_CONFLICT', message='登记目标或证据已变化，请重新核对。', status_code=409) from None
    except DatabaseError as exc:
        code = exc.sqlstate
        if code == '42501':
            raise ApiError(code='REGISTRATION_ACCESS_DENIED', message='当前账号无权登记此经营入口。', status_code=403) from None
        if code in ('40001', '40P01', '55000', '23505'):
            raise ApiError(code='REGISTRATION_CONFLICT', message='登记状态已变化，请先查询回执并核对当前状态。', status_code=409) from None
        if code == '22023':
            raise ApiError(code='REGISTRATION_REQUEST_INVALID', message='登记请求不符合要求。', status_code=422) from None
        raise ApiError(code='REGISTRATION_STORAGE_UNAVAILABLE', message='登记结果暂时无法确认，请先查询回执。', status_code=503) from None
    except (RuntimeError, OSError):
        raise ApiError(code='REGISTRATION_UNAVAILABLE', message='登记服务暂不可用，请先查询回执。', status_code=503) from None


@_registration_router.post(
    '/{installation_id}/ecommerce-growth-registrations',
    operation_id='create_ecommerce_growth_registration',
    responses={201: {'description': 'Fenced registration receipt'}, **_ERRORS},
    openapi_extra={'parameters': [_IDEMPOTENCY_PARAMETER, _IF_MATCH_PARAMETER]},
)
def create_ecommerce_growth_registration(
    installation_id: CanonicalUuidPath, body: FirstDispatchRegistrationRequest,
    request: Request, response: Response, principal: PrincipalDependency,
    control_plane: ControlPlaneDependency,
) -> dict:
    key = _invoke(lambda: require_idempotency_key(request))
    match = _invoke(lambda: require_if_match(request))
    if (installation_id != body.installationRef.installation_id or key != body.idempotencyKey
            or match != f'"{body.installationRef.revision}"'):
        raise ApiError(code='REGISTRATION_REFERENCE_MISMATCH', message='安装、版本或请求编号不一致。', status_code=409)
    service = _registration_service(control_plane)
    result = _invoke_registration(lambda: service.register(
        scope=TenantScope(principal.org_id, principal.project_id), request=body, actor=principal.subject))
    response.status_code = 200 if result['replayed'] else 201
    return result


@_registration_router.get(
    '/{installation_id}/ecommerce-growth-registrations/receipt',
    operation_id='get_ecommerce_growth_registration_receipt', responses=_ERRORS,
    openapi_extra={'parameters': [_IDEMPOTENCY_PARAMETER]},
)
def get_ecommerce_growth_registration_receipt(
    installation_id: CanonicalUuidPath, request: Request, principal: PrincipalDependency,
    control_plane: ControlPlaneDependency,
) -> dict:
    key = _invoke(lambda: require_idempotency_key(request))
    service = _registration_service(control_plane)
    return _invoke_registration(lambda: service.read_receipt(
        scope=TenantScope(principal.org_id, principal.project_id), installation_id=installation_id,
        idempotency_key=key, actor=principal.subject))


@_registration_router.post(
    '/{installation_id}/ecommerce-growth-registrations/withdrawals',
    operation_id='withdraw_ecommerce_growth_registration',
    responses={201: {'description': 'Immutable registration withdrawal receipt'}, **_ERRORS},
    openapi_extra={'parameters': [_IDEMPOTENCY_PARAMETER, _IF_MATCH_PARAMETER]},
)
def withdraw_ecommerce_growth_registration(
    installation_id: CanonicalUuidPath, body: RegistrationWithdrawalRequest,
    request: Request, response: Response, principal: PrincipalDependency,
    control_plane: ControlPlaneDependency,
) -> dict:
    key = _invoke(lambda: require_idempotency_key(request))
    match = _invoke(lambda: require_if_match(request))
    if key != body.idempotencyKey or match != f'"{body.expectedInstallationEtag}"':
        raise ApiError(code='REGISTRATION_REFERENCE_MISMATCH', message='撤回版本或请求编号不一致。', status_code=409)
    service = _registration_service(control_plane)
    result = _invoke_registration(lambda: service.withdraw(
        scope=TenantScope(principal.org_id, principal.project_id), installation_id=installation_id,
        request=body, actor=principal.subject))
    response.status_code = 200 if result.get('replayed') is True else 201
    return result


@_registration_router.get(
    '/{installation_id}/ecommerce-growth-registrations/withdrawals/receipt',
    operation_id='get_ecommerce_growth_withdrawal_receipt', responses=_ERRORS,
    openapi_extra={'parameters': [_IDEMPOTENCY_PARAMETER]},
)
def get_ecommerce_growth_withdrawal_receipt(
    installation_id: CanonicalUuidPath, request: Request, principal: PrincipalDependency,
    control_plane: ControlPlaneDependency,
) -> dict:
    key = _invoke(lambda: require_idempotency_key(request))
    service = _registration_service(control_plane)
    return _invoke_registration(lambda: service.read_withdrawal_receipt(
        scope=TenantScope(principal.org_id, principal.project_id), installation_id=installation_id,
        idempotency_key=key, actor=principal.subject))


@_registration_router.get(
    '/{installation_id}/ecommerce-growth-registrations/status',
    operation_id='get_ecommerce_growth_registration_status', responses=_ERRORS,
)
def get_ecommerce_growth_registration_status(
    installation_id: CanonicalUuidPath, principal: PrincipalDependency,
    control_plane: ControlPlaneDependency,
) -> dict:
    service = _registration_service(control_plane)
    return _invoke_registration(lambda: service.registration_status(
        scope=TenantScope(principal.org_id, principal.project_id),
        installation_id=installation_id, actor=principal.subject))


router.include_router(_registration_router)


class _CutoverReadRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise ApiError(code='CUTOVER_REQUEST_INVALID', message='切换请求格式不符合要求。', status_code=422) from None
        return safe_handler


_cutover_read_router = APIRouter(route_class=_CutoverReadRoute)


def _cutover_read(control_plane, principal, installation_id, key, *, history):
    service = getattr(control_plane, 'ecommerce_growth_cutover_service', None)
    if service is None:
        raise ApiError(code='CUTOVER_UNAVAILABLE', message='经营入口切换查询服务尚未配置。', status_code=503)
    read = service.read_activation_history if history else service.read_prepare_receipt
    return _invoke_cutover_operation(lambda: read(scope=TenantScope(principal.org_id, principal.project_id),
        installation_id=installation_id, idempotency_key=key, actor=principal.subject))


def _invoke_cutover_operation(operation):
    from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverConflict, EcommerceGrowthCutoverBlocked
    try:
        return _invoke(operation)
    except EcommerceGrowthCutoverBlocked:
        raise ApiError(code='CUTOVER_BLOCKED', message='当前切换条件不满足，请核对审批和运行状态。', status_code=409) from None
    except (EcommerceGrowthCutoverConflict, ValueError):
        raise ApiError(code='CUTOVER_HISTORY_CONFLICT', message='切换证据不完整或已变化，请核对原回执。', status_code=409) from None
    except DatabaseError as error:
        if error.sqlstate == '42501':
            raise ApiError(code='CUTOVER_ACCESS_DENIED', message='当前账号无权查询此经营入口。', status_code=403) from None
        if error.sqlstate in ('40001', '40P01', '55000'):
            raise ApiError(code='CUTOVER_READ_CONFLICT', message='切换状态正在变化，请稍后查询。', status_code=409) from None
        raise ApiError(code='CUTOVER_UNAVAILABLE', message='切换记录暂时无法查询。', status_code=503) from None
    except (RuntimeError, OSError):
        raise ApiError(code='CUTOVER_UNAVAILABLE', message='切换查询服务暂不可用。', status_code=503) from None


@_cutover_read_router.get(
    '/{installation_id}/ecommerce-growth-cutovers/receipt',
    operation_id='get_ecommerce_growth_cutover_prepare_receipt', responses=_ERRORS,
    openapi_extra={'parameters': [_IDEMPOTENCY_PARAMETER]},
)
def get_ecommerce_growth_cutover_prepare_receipt(
    installation_id: CanonicalUuidPath, request: Request, principal: PrincipalDependency,
    control_plane: ControlPlaneDependency,
) -> dict:
    key = _invoke(lambda: require_idempotency_key(request))
    return _cutover_read(control_plane, principal, installation_id, key, history=False)


@_cutover_read_router.get(
    '/{installation_id}/ecommerce-growth-cutovers/history',
    operation_id='get_ecommerce_growth_cutover_history', responses=_ERRORS,
    openapi_extra={'parameters': [_IDEMPOTENCY_PARAMETER]},
)
def get_ecommerce_growth_cutover_history(
    installation_id: CanonicalUuidPath, request: Request, principal: PrincipalDependency,
    control_plane: ControlPlaneDependency,
) -> dict:
    key = _invoke(lambda: require_idempotency_key(request))
    return _cutover_read(control_plane, principal, installation_id, key, history=True)


from aos_api.ecommerce_growth_cutover_command import CutoverProductCommand


@_cutover_read_router.post(
    '/{installation_id}/ecommerce-growth-cutovers/commands',
    operation_id='execute_ecommerce_growth_cutover_phase', responses={201: {'description': 'New cutover phase receipt'}, **_ERRORS},
    openapi_extra={'parameters': [_IDEMPOTENCY_PARAMETER, _IF_MATCH_PARAMETER]},
)
def execute_ecommerce_growth_cutover_phase(
    installation_id: CanonicalUuidPath, body: CutoverProductCommand,
    request: Request, response: Response, principal: PrincipalDependency,
    control_plane: ControlPlaneDependency,
) -> dict:
    key = _invoke(lambda: require_idempotency_key(request))
    match = _invoke(lambda: require_if_match(request))
    if key != body.request.idempotency_key:
        raise ApiError(code='CUTOVER_REFERENCE_MISMATCH', message='切换请求编号不一致。', status_code=409)
    control = getattr(control_plane, 'ecommerce_growth_cutover_control', None)
    if control is None:
        raise ApiError(code='CUTOVER_UNAVAILABLE', message='经营入口切换控制服务尚未配置。', status_code=503)
    result = _invoke_cutover_operation(lambda: control.execute(
        scope=TenantScope(principal.org_id, principal.project_id), phase=body.phase,
        request=body.request, actor=principal.subject, validate_receipt_ref=body.validate_receipt_ref,
        expected_installation_id=installation_id, expected_installation_etag=int(match[1:-1])))
    response.status_code = 200 if result.replayed else 201
    return result.model_dump(mode='json', by_alias=True)


router.include_router(_cutover_read_router)
