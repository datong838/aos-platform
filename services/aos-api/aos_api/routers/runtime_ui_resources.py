"""Anonymous signed static code resources; never a tenant data API."""
from __future__ import annotations

import os
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute

from aos_api.errors import ApiError
from aos_api.extension_runtime.ui_resource_reader import PublishedUiResourceReader


_HEADERS = {
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
}


def _origin(name: str) -> str:
    value = os.getenv(name, '')
    try:
        url = urlsplit(value)
        valid = (value == value.strip() and bool(url.netloc) and url.path in ('', '/')
                 and url.username is None and url.password is None and not url.query and not url.fragment
                 and url.hostname is not None and url.port != 0
                 and (url.scheme == 'https' or (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost')))
                 and not any(c.isspace() or c in "'\";\\*%" for c in value))
        if valid:
            return f'{url.scheme}://{url.netloc}'
    except ValueError:
        pass
    raise ApiError(code='RUNTIME_UI_RESOURCE_UNAVAILABLE', message='工作台页面资源尚未就绪。', status_code=503)


def get_parent_origin() -> str:
    _origin('AOS_EXTENSION_UI_RESOURCE_ORIGIN')
    return _origin('AOS_EXTENSION_UI_PARENT_ORIGIN')


def get_resource_reader(parent: Annotated[str, Depends(get_parent_origin)]) -> PublishedUiResourceReader:
    del parent
    from aos_api.asset_registry.control_wiring import build_runtime_ui_resource_reader
    return build_runtime_ui_resource_reader()


class _ResourceRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request: Request):
            try:
                response = await original(request)
            except Exception as exc:
                status = exc.status_code if isinstance(exc, ApiError) else (
                    404 if isinstance(exc, LookupError) else 400 if isinstance(exc, ValueError) else 503)
                response = JSONResponse(status_code=status, content={
                    'code': 'RUNTIME_UI_RESOURCE_UNAVAILABLE',
                    'message': '工作台页面资源校验未通过，请重新读取安装目录。',
                })
                response.headers['Content-Security-Policy'] = "default-src 'none'; sandbox; frame-ancestors 'none'"
            response.headers.update(_HEADERS)
            return response
        return handle


router = APIRouter(prefix='/v1/bundles', tags=['asset-control'], route_class=_ResourceRoute)


@router.get('/{publisher}/{bundle_id}/{version}/{entrypoint:path}',
            operation_id='get_signed_runtime_frontend', response_class=Response)
def get_resource(request: Request, publisher: str, bundle_id: str, version: str, entrypoint: str,
                 parent: Annotated[str, Depends(get_parent_origin)],
                 reader: Annotated[PublishedUiResourceReader, Depends(get_resource_reader)]):
    params = list(request.query_params.multi_items())
    if len(params) != 2 or {key for key, _ in params} != {'packageHash', 'contentHash'}:
        raise ValueError('invalid resource parameters')
    content = reader.read(publisher=publisher, bundle_id=bundle_id, version=version, entrypoint=entrypoint,
                          package_hash=request.query_params['packageHash'], content_hash=request.query_params['contentHash'])
    return Response(content=content, media_type='text/html', headers={
        'Content-Security-Policy': "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
            "connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'; "
            f"sandbox allow-scripts; frame-ancestors {parent}",
    })
