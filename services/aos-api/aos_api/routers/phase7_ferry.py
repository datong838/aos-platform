"""Phase 7 · Ferry 路由（2 API）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aos_api.phase7_ops_engine import get_engine

router = APIRouter(prefix="/api/v1/ops/ferry", tags=["phase7-ferry"])


class CreateBundleRequest(BaseModel):
    name: str
    version: str = "1.0.0"
    size_mb: float = 0.0
    artifacts: list[str] = []
    description: str = ""
    status: str = "ready"


class SubmitFerryRequest(BaseModel):
    bundle_id: str
    spoke_ids: list[str] = []


@router.get("/bundles")
async def list_bundles() -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_bundles()
    return {"items": [b.model_dump() for b in items], "total": len(items)}


@router.post("/bundles")
async def create_bundle(req: CreateBundleRequest) -> dict[str, Any]:
    eng = get_engine()
    b = eng.create_bundle(**req.model_dump())
    return b.model_dump()


@router.post("/submit")
async def submit_ferry(req: SubmitFerryRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        sub = eng.submit_ferry(bundle_id=req.bundle_id, spoke_ids=req.spoke_ids)
        return sub.model_dump()
    except KeyError as e:
        raise HTTPException(404, str(e))
