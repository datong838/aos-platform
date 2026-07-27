"""Phase 7 · Hub & Spokes 路由（8 API）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.phase7_ops_engine import get_engine

router = APIRouter(prefix="/api/v1/ops", tags=["phase7-hub-spokes"])


class UpdateHubRequest(BaseModel):
    version: str | None = None
    cluster: str | None = None
    status: str | None = None
    region: str | None = None
    metadata: dict[str, Any] | None = None


class CreateSpokeRequest(BaseModel):
    name: str
    region: str = "us-east-1"
    status: str = "healthy"
    version: str = "3.14.0"
    url: str = ""
    description: str = ""


class UpdateSpokeRequest(BaseModel):
    name: str | None = None
    region: str | None = None
    status: str | None = None
    version: str | None = None
    url: str | None = None
    description: str | None = None


class UpdateConfigRequest(BaseModel):
    overrides: dict[str, Any]
    updated_by: str = "system"


# ── Hub ──

@router.get("/hub")
async def get_hub() -> dict[str, Any]:
    eng = get_engine()
    return eng.get_hub().model_dump()


@router.put("/hub")
async def update_hub(req: UpdateHubRequest) -> dict[str, Any]:
    eng = get_engine()
    hub = eng.update_hub(**req.model_dump(exclude_none=True))
    return hub.model_dump()


# ── Spokes ──

@router.get("/spokes")
async def list_spokes(
    status: str | None = Query(None),
    hub_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_spokes(status=status, hub_id=hub_id, page=page, page_size=page_size)
    return {"items": [s.model_dump() for s in items], "total": total, "page": page, "page_size": page_size}


@router.post("/spokes")
async def create_spoke(req: CreateSpokeRequest) -> dict[str, Any]:
    eng = get_engine()
    s = eng.create_spoke(**req.model_dump())
    return s.model_dump()


@router.get("/spokes/{spoke_id}")
async def get_spoke(spoke_id: str) -> dict[str, Any]:
    eng = get_engine()
    s = eng.get_spoke(spoke_id)
    if s is None:
        raise HTTPException(404, f"Spoke {spoke_id} not found")
    return s.model_dump()


@router.put("/spokes/{spoke_id}")
async def update_spoke(spoke_id: str, req: UpdateSpokeRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        s = eng.update_spoke(spoke_id, **req.model_dump(exclude_none=True))
        return s.model_dump()
    except KeyError:
        raise HTTPException(404, f"Spoke {spoke_id} not found")


@router.delete("/spokes/{spoke_id}")
async def delete_spoke(spoke_id: str) -> dict[str, Any]:
    eng = get_engine()
    ok = eng.delete_spoke(spoke_id)
    if not ok:
        raise HTTPException(404, f"Spoke {spoke_id} not found")
    return {"deleted": True, "id": spoke_id}


# ── Plan ──

@router.get("/spokes/{spoke_id}/plan")
async def get_spoke_plan(spoke_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        items = eng.get_spoke_plan(spoke_id)
        return {"spoke_id": spoke_id, "items": [i.model_dump() for i in items], "total": len(items)}
    except KeyError:
        raise HTTPException(404, f"Spoke {spoke_id} not found")


@router.get("/spokes/{spoke_id}/plan-diff")
async def get_plan_diff(spoke_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        diffs = eng.get_plan_diff(spoke_id)
        return {"spoke_id": spoke_id, "diffs": [d.model_dump() for d in diffs], "total": len(diffs)}
    except KeyError:
        raise HTTPException(404, f"Spoke {spoke_id} not found")


# ── Config ──

@router.get("/spokes/{spoke_id}/config")
async def get_spoke_config(spoke_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.get_spoke_config(spoke_id).model_dump()
    except KeyError:
        raise HTTPException(404, f"Spoke {spoke_id} not found")


@router.put("/spokes/{spoke_id}/config")
async def update_spoke_config(spoke_id: str, req: UpdateConfigRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        cfg = eng.update_spoke_config(spoke_id, overrides=req.overrides, updated_by=req.updated_by)
        return cfg.model_dump()
    except KeyError:
        raise HTTPException(404, f"Spoke {spoke_id} not found")


# ── Maintenance Windows ──

@router.get("/spokes/{spoke_id}/maintenance-window")
async def get_maintenance_windows(spoke_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        windows = eng.get_maintenance_windows(spoke_id)
        return {"spoke_id": spoke_id, "windows": [w.model_dump() for w in windows], "total": len(windows)}
    except KeyError:
        raise HTTPException(404, f"Spoke {spoke_id} not found")
