"""
W5 — 多 Spoke 监控
Router: /api/multi-spoke-monitors
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aos_api.cp_multi_spoke_monitor import MultiSpokeMonitor, MultiSpokeMonitorEngine

router = APIRouter(prefix="/api/multi-spoke-monitors", tags=["w5-cp"])
_engine = MultiSpokeMonitorEngine()


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
    item = MultiSpokeMonitor(
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
