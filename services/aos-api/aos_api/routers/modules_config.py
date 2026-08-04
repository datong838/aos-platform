"""Canvas config router — Phase 1 Workshop backend.

GET/PUT /v1/modules/:id/config — complete canvas configuration.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.canvas_config import get_config, put_config
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/modules",
    tags=["modules-config"],
    dependencies=[Depends(require_principal)],
)


class ConfigBody(BaseModel):
    layout: dict[str, Any] = {}
    components: dict[str, Any] = {}


@router.get("/{module_id}/config")
def get_module_config(
    module_id: str, principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    cfg = get_config(scope, module_id)
    if not cfg:
        return {
            "moduleId": module_id,
            "layout": {"type": "page-layout", "children": []},
            "components": {},
            "version": 0,
        }
    return cfg


@router.put("/{module_id}/config")
def put_module_config(
    module_id: str,
    body: ConfigBody,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    try:
        return put_config(scope, module_id, body.layout, body.components)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Module not found") from exc
