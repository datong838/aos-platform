"""Read-only signed runtime Workshop resource discovery."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from psycopg import Error as DatabaseError

from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalogResponse
from aos_api.errors import ApiError


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
