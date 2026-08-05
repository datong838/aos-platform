"""221plan · Model Catalog 登记 — FastAPI 路由。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .aip_model_catalog import get_engine
from .auth import Principal, require_principal
from .tenant_scope import TenantScope

router = APIRouter(prefix="/api/aip/model-catalog", tags=["aip-model_catalog"])
_engine = get_engine()


class CreateRequest(BaseModel):
    name: str
    config: dict = {}


class UpdateRequest(BaseModel):
    name: str | None = None
    config: dict | None = None
    status: str | None = None


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


@router.get("")
def list_items(principal: Annotated[Principal, Depends(require_principal)]):
    return [item.model_dump() for item in _engine.list(_scope(principal))]


@router.post("")
def create_item(
    req: CreateRequest,
    principal: Annotated[Principal, Depends(require_principal)],
):
    try:
        return _engine.create(_scope(principal), req.name, req.config).model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/{item_id}")
def get_item(
    item_id: str,
    principal: Annotated[Principal, Depends(require_principal)],
):
    item = _engine.get(_scope(principal), item_id)
    if item is None:
        raise HTTPException(404, f"不存在 {item_id}")
    return item.model_dump()


@router.put("/{item_id}")
def update_item(
    item_id: str,
    req: UpdateRequest,
    principal: Annotated[Principal, Depends(require_principal)],
):
    try:
        return _engine.update(
            _scope(principal), item_id, **req.model_dump(exclude_none=True)
        ).model_dump()
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{item_id}")
def delete_item(
    item_id: str,
    principal: Annotated[Principal, Depends(require_principal)],
):
    if not _engine.delete(_scope(principal), item_id):
        raise HTTPException(404, f"不存在 {item_id}")
    return {"deleted": True}
