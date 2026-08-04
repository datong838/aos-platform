"""Themes router — Phase 1 Workshop backend.

GET/POST /v1/themes — theme list / create.
GET/PUT/DELETE /v1/themes/:id — theme detail.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.tenant_scope import TenantScope
from aos_api.themes import (
    create_theme,
    delete_theme,
    get_theme,
    list_themes,
    update_theme,
)

PrincipalDep = Annotated[Principal, Depends(require_principal)]

router = APIRouter(
    prefix="/v1/themes",
    tags=["themes"],
    dependencies=[Depends(require_principal)],
)


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


class ThemeCreate(BaseModel):
    name: str
    mode: str = "light"
    isPreset: bool = False
    tokens: dict[str, Any] = {}
    description: str = ""


class ThemeUpdate(BaseModel):
    name: str | None = None
    mode: str | None = None
    tokens: dict[str, Any] | None = None
    description: str | None = None


@router.get("")
def list_themes_api(
    principal: PrincipalDep,
) -> dict[str, Any]:
    items = list_themes(_scope(principal))
    return {"items": items, "count": len(items)}


@router.post("")
def create_theme_api(
    body: ThemeCreate, principal: PrincipalDep
) -> dict[str, Any]:
    item = create_theme(_scope(principal), body.model_dump())
    return {"ok": True, "item": item}


@router.get("/{theme_id}")
def get_theme_api(
    theme_id: str, principal: PrincipalDep
) -> dict[str, Any]:
    item = get_theme(_scope(principal), theme_id)
    if not item:
        raise HTTPException(status_code=404, detail="Theme not found")
    return item


@router.put("/{theme_id}")
def update_theme_api(
    theme_id: str,
    body: ThemeUpdate,
    principal: PrincipalDep,
) -> dict[str, Any]:
    item = update_theme(
        _scope(principal), theme_id, body.model_dump(exclude_none=True)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Theme not found")
    return item


@router.delete("/{theme_id}")
def delete_theme_api(
    theme_id: str, principal: PrincipalDep
) -> dict[str, Any]:
    ok = delete_theme(_scope(principal), theme_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Theme not found or is a preset (cannot delete)",
        )
    return {"ok": True}
