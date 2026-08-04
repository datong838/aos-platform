"""Module variables router — Phase 1 Workshop backend.

GET/POST/PUT/DELETE /v1/modules/:id/variables — variable CRUD.
GET /v1/modules/:id/variables/:vid/usage — variable usage locations.

W1-A1: group 约定为作用域 page|app|global（Variables 页过滤）；兼容旧 default。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from aos_api.auth import require_principal
from aos_api.module_variables import (
    create_variable,
    delete_variable,
    list_usage,
    list_variables,
    update_variable,
)

router = APIRouter(
    prefix="/v1/modules",
    tags=["modules-variables"],
    dependencies=[Depends(require_principal)],
)

_ALLOWED_SCOPES = frozenset({"page", "app", "global", "default"})


def _normalize_group(group: str | None) -> str:
    raw = (group or "page").strip().lower()
    if raw in ("application", "应用", "应用级"):
        return "app"
    if raw in ("全局",):
        return "global"
    if raw in ("页面", "页面级"):
        return "page"
    if raw in _ALLOWED_SCOPES:
        return raw
    return "page"


class VariableCreate(BaseModel):
    name: str
    varType: str = "string"
    group: str = Field(default="page", description="scope: page|app|global")
    initialValue: Any = None
    description: str = ""


class VariableUpdate(BaseModel):
    name: str | None = None
    varType: str | None = None
    group: str | None = None
    initialValue: Any = None
    currentValue: Any = None
    description: str | None = None


@router.get("/{module_id}/variables")
def list_module_variables(module_id: str) -> dict[str, Any]:
    items = list_variables(module_id)
    return {"moduleId": module_id, "items": items, "count": len(items)}


@router.post("/{module_id}/variables")
def create_module_variable(
    module_id: str, body: VariableCreate
) -> dict[str, Any]:
    payload = body.model_dump()
    payload["group"] = _normalize_group(payload.get("group"))
    item = create_variable(module_id, payload)
    return {"ok": True, "item": item}


@router.put("/{module_id}/variables/{variable_id}")
def update_module_variable(
    module_id: str, variable_id: str, body: VariableUpdate
) -> dict[str, Any]:
    patch = body.model_dump(exclude_none=True)
    if "group" in patch:
        patch["group"] = _normalize_group(patch.get("group"))
    item = update_variable(variable_id, patch)
    if not item:
        raise HTTPException(status_code=404, detail="Variable not found")
    return {"ok": True, "item": item}


@router.delete("/{module_id}/variables/{variable_id}")
def delete_module_variable(
    module_id: str, variable_id: str
) -> dict[str, Any]:
    ok = delete_variable(variable_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Variable not found")
    return {"ok": True}


@router.get("/{module_id}/variables/{variable_id}/usage")
def get_variable_usage(
    module_id: str, variable_id: str
) -> dict[str, Any]:
    usages = list_usage(module_id, variable_id)
    return {"moduleId": module_id, "variableId": variable_id, "usages": usages}
