"""221plan · DocIntel 信息提取 — FastAPI 路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .aip_docintel_extract import get_engine, DocintelExtractItem

router = APIRouter(prefix="/api/aip/docintel-extract", tags=["aip-docintel_extract"])
_engine = get_engine()


class CreateRequest(BaseModel):
    name: str
    config: dict = {}


class UpdateRequest(BaseModel):
    name: str | None = None
    config: dict | None = None
    status: str | None = None


@router.get("")
def list_items():
    return [item.model_dump() for item in _engine.list()]


@router.post("")
def create_item(req: CreateRequest):
    try:
        return _engine.create(req.name, req.config).model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/{item_id}")
def get_item(item_id: str):
    item = _engine.get(item_id)
    if item is None:
        raise HTTPException(404, f"不存在 {item_id}")
    return item.model_dump()


@router.put("/{item_id}")
def update_item(item_id: str, req: UpdateRequest):
    try:
        return _engine.update(item_id, **req.model_dump(exclude_none=True)).model_dump()
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{item_id}")
def delete_item(item_id: str):
    if not _engine.delete(item_id):
        raise HTTPException(404, f"不存在 {item_id}")
    return {"deleted": True}
