"""
W5 — 输入输出分类
Router: /api/io-classifies
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aos_api.pp_io_classify import IOClassify, IOClassifyEngine

router = APIRouter(prefix="/api/io-classifies", tags=["w5-pp"])
_engine = IOClassifyEngine()


class CreateRequest(BaseModel):
    name: str
    description: str = ""
    enabled: bool = True
    config: dict = {}


class UpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    config: dict | None = None


@router.get("/")
async def list_items():
    return [item.model_dump() for item in _engine.list()]


@router.get("/{item_id}")
async def get_item(item_id: str):
    item = _engine.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not_found")
    return item.model_dump()


@router.post("/")
async def create_item(req: CreateRequest):
    item = IOClassify(
        name=req.name,
        description=req.description,
        enabled=req.enabled,
        config=req.config,
    )
    return _engine.register(item).model_dump()


@router.put("/{item_id}")
async def update_item(item_id: str, req: UpdateRequest):
    patch = req.model_dump(exclude_none=True)
    updated = _engine.update(item_id, patch)
    if updated is None:
        raise HTTPException(status_code=404, detail="not_found")
    return updated.model_dump()


@router.delete("/{item_id}")
async def delete_item(item_id: str):
    ok = _engine.delete(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="not_found")
    return {"deleted": True}
