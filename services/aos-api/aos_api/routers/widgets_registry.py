"""Widgets registry router — Phase 1 Workshop backend.

GET/POST /v1/widgets — widget catalog (filter by source).
GET /v1/widgets/:id — widget detail.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.tenant_scope import TenantScope
from aos_api.widget_catalog import create_widget, get_widget, list_widgets

PrincipalDep = Annotated[Principal, Depends(require_principal)]

router = APIRouter(
    prefix="/v1/widgets",
    tags=["widgets-registry"],
    dependencies=[Depends(require_principal)],
)


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


class WidgetCreate(BaseModel):
    name: str
    nameZh: str = ""
    type: str = "unknown"
    source: str = "builtin"
    category: str = "general"
    icon: str = ""
    description: str = ""
    configSchema: dict[str, Any] = {}
    version: str = "1.0.0"


@router.get("")
def list_widgets_api(
    principal: PrincipalDep,
    source: str | None = Query(default=None),
) -> dict[str, Any]:
    items = list_widgets(_scope(principal), source)
    return {"items": items, "count": len(items)}


@router.post("")
def create_widget_api(
    body: WidgetCreate, principal: PrincipalDep
) -> dict[str, Any]:
    try:
        item = create_widget(_scope(principal), body.model_dump())
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Widget not found") from exc
    return {"ok": True, "item": item}


@router.get("/{widget_id}")
def get_widget_api(
    widget_id: str, principal: PrincipalDep
) -> dict[str, Any]:
    item = get_widget(_scope(principal), widget_id)
    if not item:
        return {"item": None}
    return item
