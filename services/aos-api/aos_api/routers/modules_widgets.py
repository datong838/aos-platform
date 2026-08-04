"""Widget instances router — Phase 1 Workshop backend.

GET/POST/PUT/DELETE /v1/modules/:id/widgets — component instances on canvas.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.widget_instances import (
    create_instance,
    delete_instance,
    list_instances,
    update_instance,
)
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/modules",
    tags=["modules-widgets"],
    dependencies=[Depends(require_principal)],
)


class WidgetCreate(BaseModel):
    widgetId: str = ""
    type: str = "unknown"
    title: str = ""
    config: dict[str, Any] = {}
    layout: dict[str, Any] = {}
    sortOrder: int = 0


class WidgetUpdate(BaseModel):
    widgetId: str | None = None
    type: str | None = None
    title: str | None = None
    config: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None
    sortOrder: int | None = None


@router.get("/{module_id}/widgets")
def list_module_widgets(
    module_id: str, principal: Principal = Depends(require_principal)
) -> dict[str, Any]:
    items = list_instances(TenantScope(principal.org_id, principal.project_id), module_id)
    return {"moduleId": module_id, "items": items, "count": len(items)}


@router.post("/{module_id}/widgets")
def create_module_widget(
    module_id: str,
    body: WidgetCreate,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    item = create_instance(scope, module_id, body.model_dump())
    return {"ok": True, "item": item}


@router.put("/{module_id}/widgets/{instance_id}")
def update_module_widget(
    module_id: str,
    instance_id: str,
    body: WidgetUpdate,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    item = update_instance(
        scope, module_id, instance_id, body.model_dump(exclude_none=True)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Widget instance not found")
    return {"ok": True, "item": item}


@router.delete("/{module_id}/widgets/{instance_id}")
def delete_module_widget(
    module_id: str,
    instance_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    ok = delete_instance(scope, module_id, instance_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Widget instance not found")
    return {"ok": True}
