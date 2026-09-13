"""Configuration receipt HTTP adapter; no inline registration or activation."""
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from psycopg import Error as DatabaseError

from aos_api.auth import Principal, require_principal
from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION, require_control_role
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.errors import ApiError, error_payload
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.configuration_stage_contracts import ConfigurationStageRequest
from aos_api.extension_runtime.configuration_stage_connection import CREDENTIAL_FILE
from aos_api.extension_runtime.configuration_stage_http_service import ConfigurationStageHttpService


class _StageRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handle(request):
            try: response = await original(request)
            except RequestValidationError:
                response = JSONResponse(status_code=400, content=error_payload(code='CONFIGURATION_REQUEST_INVALID', message='配置登记请求格式不正确，请刷新安装状态。'))
            except HTTPException as exc:
                response = JSONResponse(status_code=exc.status_code, content=error_payload(code='CONFIGURATION_AUTH_REQUIRED', message='请使用当前租户的有效账号。'))
            except ApiError as exc:
                response = JSONResponse(status_code=exc.status_code, content=error_payload(code=exc.code, message=exc.message))
            except AssetRegistryError as exc:
                response = JSONResponse(status_code=exc.http_status, content=error_payload(code=exc.code.value, message='当前账号或登记条件未通过校验。'))
            except Exception:
                response = JSONResponse(status_code=503, content=error_payload(code='CONFIGURATION_STAGE_UNAVAILABLE', message='登记结果暂无法确认，请保留本次请求，不要重复提交。'))
            response.headers['Cache-Control'] = 'no-store'
            return response
        return handle


router = APIRouter(route_class=_StageRoute)


def stage_principal(principal: Annotated[Principal, Depends(require_principal)]):
    require_control_role(roles=principal.roles, operation=APPLY_INSTALLATION_OPERATION)
    return principal


def get_stage_service():
    if not os.getenv(CREDENTIAL_FILE, '').strip():
        raise ApiError(code='CONFIGURATION_STAGE_UNAVAILABLE', message='配置登记服务尚未就绪。', status_code=503)
    return ConfigurationStageHttpService()


def _call(method, **arguments):
    try: return method(**arguments)
    except LookupError as exc:
        raise ApiError(code='CONFIGURATION_REQUEST_NOT_FOUND', message='未找到当前账号可见的登记请求。', status_code=404) from exc
    except DatabaseError as exc:
        status = 403 if exc.sqlstate == '42501' else 409 if exc.sqlstate in {'23514','40001'} else 503
        message = ('当前账号无权操作此登记请求。' if status==403 else
                   '当前配置条件已变化，请刷新安装状态。' if status==409 else
                   '登记结果暂无法确认，请保留本次请求，不要重复提交。')
        raise ApiError(code='CONFIGURATION_STAGE_DENIED' if status==403 else 'CONFIGURATION_STAGE_CONFLICT' if status==409 else 'CONFIGURATION_STAGE_UNAVAILABLE', message=message, status_code=status) from exc


@router.post('/configuration-requests', status_code=202, operation_id='submit_runtime_configuration_stage')
def submit(request: ConfigurationStageRequest,
           principal: Annotated[Principal, Depends(stage_principal)],
           service: Annotated[ConfigurationStageHttpService, Depends(get_stage_service)],
           idempotency_key: Annotated[str, Header(alias='Idempotency-Key', min_length=1, max_length=160)]):
    return _call(service.enqueue, scope=TenantScope(principal.org_id,principal.project_id),
                 subject=principal.subject, idempotency_key=idempotency_key, request=request)


@router.get('/configuration-requests/{request_id}', operation_id='get_runtime_configuration_stage')
def get(request_id: UUID, principal: Annotated[Principal, Depends(stage_principal)],
        service: Annotated[ConfigurationStageHttpService, Depends(get_stage_service)]):
    return _call(service.get, scope=TenantScope(principal.org_id,principal.project_id),
                 subject=principal.subject, request_id=request_id)
