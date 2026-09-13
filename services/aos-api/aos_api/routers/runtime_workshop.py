"""Read-only signed runtime Workshop resource discovery."""
from typing import Annotated, Any
import os
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from psycopg import Error as DatabaseError

from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalogResponse
from aos_api.errors import ApiError, error_payload
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.extension_runtime.ui_read_contracts import UiReadRequest


router = APIRouter(prefix='/v1/runtime-workshop', tags=['asset-control'])


def get_catalog(request: Request) -> Any:
    control = getattr(request.app.state, 'extension_runtime_control_plane', None)
    catalog = getattr(control, 'workshop_catalog', None)
    if catalog is None:
        catalog = getattr(request.app.state, 'extension_runtime_workshop_catalog', None)
    if catalog is None:
        raise ApiError(code='RUNTIME_CATALOG_UNAVAILABLE', message='工作台目录暂不可用，请稍后刷新。', status_code=503)
    return catalog


@router.get('/modules', response_model=RuntimeWorkshopCatalogResponse,
            operation_id='list_runtime_workshop_modules')
def list_modules(response: Response,
                 principal: Annotated[Principal, Depends(require_principal)],
                 catalog: Annotated[Any, Depends(get_catalog)]) -> RuntimeWorkshopCatalogResponse:
    response.headers['Cache-Control'] = 'no-store'
    try:
        return catalog.list_modules(org_id=principal.org_id, project_id=principal.project_id,
                                    roles=principal.roles, markings=principal.markings)
    except AssetRegistryError as exc:
        raise ApiError(code=exc.code.value, message='工作台资源校验未通过，请刷新安装状态。', status_code=exc.http_status) from exc
    except PermissionError as exc:
        raise ApiError(code='RUNTIME_CATALOG_ACCESS_DENIED', message='当前账号无权读取工作台目录。', status_code=403) from exc
    except LookupError as exc:
        raise ApiError(code='RUNTIME_CATALOG_NOT_FOUND', message='未找到当前租户可见的工作台资源。', status_code=404) from exc
    except (ValueError, DatabaseError) as exc:
        raise ApiError(code='RUNTIME_CATALOG_UNAVAILABLE', message='工作台目录暂不可用，请稍后刷新。', status_code=503) from exc


class _UiReadRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request):
            try:
                response = await original(request)
            except ApiError as exc:
                response = JSONResponse(status_code=exc.status_code,
                    content=error_payload(code=exc.code, message=exc.message))
            except RequestValidationError:
                response = JSONResponse(status_code=400, content=error_payload(
                    code='RUNTIME_UI_READ_INVALID', message='读取请求格式不正确，请刷新工作台后重试。'))
            except HTTPException as exc:
                response = JSONResponse(status_code=exc.status_code, headers=exc.headers,
                    content=error_payload(code='RUNTIME_UI_READ_AUTH_REQUIRED', message='请使用当前租户的有效账号。'))
            response.headers['Cache-Control'] = 'no-store'
            return response
        return handle


def get_ui_read_service(request: Request):
    from aos_api.extension_runtime.ui_read_connection import CREDENTIAL_FILE
    from aos_api.extension_runtime.ui_read_http_service import RuntimeUiReadHttpService
    if not os.getenv(CREDENTIAL_FILE, '').strip():
        raise ApiError(code='RUNTIME_UI_READ_UNAVAILABLE', message='工作台读取服务尚未就绪。', status_code=503)
    catalog = get_catalog(request)
    resolve = getattr(catalog, 'resolve_catalog', None)
    return RuntimeUiReadHttpService(catalog_provider=resolve if callable(resolve) else lambda: catalog)


def _read_call(method, **kwargs):
    try:
        return method(**kwargs)
    except AssetRegistryError as exc:
        raise ApiError(code=exc.code.value, message='当前工作台资源校验未通过。', status_code=exc.http_status) from exc
    except RuntimeConflict as exc:
        raise ApiError(code='RUNTIME_UI_READ_CONFLICT', message='当前读取条件已变化，请刷新工作台状态。', status_code=409) from exc
    except PermissionError as exc:
        raise ApiError(code='RUNTIME_UI_READ_DENIED', message='当前账号无权读取该工作台。', status_code=403) from exc
    except LookupError as exc:
        raise ApiError(code='RUNTIME_UI_READ_NOT_FOUND', message='未找到当前账号可见的读取请求。', status_code=404) from exc
    except (RuntimeError, ValueError, DatabaseError) as exc:
        raise ApiError(code='RUNTIME_UI_READ_UNAVAILABLE', message='工作台读取暂不可用，请稍后查看。', status_code=503) from exc


_reads = APIRouter(route_class=_UiReadRoute)


@_reads.post('/reads', status_code=202, operation_id='submit_runtime_workshop_read')
def submit_read(request: UiReadRequest,
                principal: Annotated[Principal, Depends(require_principal)],
                service: Annotated[Any, Depends(get_ui_read_service)],
                idempotency_key: Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=240)]):
    return _read_call(service.enqueue, scope=TenantScope(principal.org_id, principal.project_id),
        subject=principal.subject, markings=tuple(principal.markings),
        idempotency_key=idempotency_key, request=request)


@_reads.get('/reads/{request_id}', operation_id='get_runtime_workshop_read')
def get_read(request_id: UUID,
             principal: Annotated[Principal, Depends(require_principal)],
             service: Annotated[Any, Depends(get_ui_read_service)]):
    return _read_call(service.get, scope=TenantScope(principal.org_id, principal.project_id),
        subject=principal.subject, markings=tuple(principal.markings), request_id=request_id)


router.include_router(_reads)
