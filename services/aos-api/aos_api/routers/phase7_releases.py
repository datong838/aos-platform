"""Phase 7 · Releases & Hotfix & Recall 路由（5 API）."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.phase7_ops_engine import get_engine

router = APIRouter(prefix="/api/v1/ops/releases", tags=["phase7-releases"])


class CreateReleaseRequest(BaseModel):
    channel: str = "beta"  # rc|beta|stable
    version: str
    changelog: list[str] = []
    commit_hash: str = ""
    artifacts: list[str] = []
    status: str = "published"


class CreateHotfixRequest(BaseModel):
    version: str
    base_version: str = ""
    description: str = ""
    target_spokes: list[str] = []


class PushHotfixRequest(BaseModel):
    hotfix_id: str


class ExecuteRecallRequest(BaseModel):
    target_version: str
    from_version: str = ""
    reason: str = ""


@router.get("")
async def list_releases(channel: str | None = Query(None)) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_releases(channel=channel)
    return {"items": [r.model_dump() for r in items], "total": len(items)}


@router.post("")
async def create_release(req: CreateReleaseRequest) -> dict[str, Any]:
    eng = get_engine()
    r = eng.create_release(**req.model_dump())
    return r.model_dump()


@router.get("/hotfix")
async def get_hotfix() -> dict[str, Any]:
    eng = get_engine()
    h = eng.get_current_hotfix()
    if h is None:
        return {"hotfix": None}
    return h.model_dump()


@router.post("/hotfix/push")
async def push_hotfix(req: PushHotfixRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        h = eng.push_hotfix(req.hotfix_id)
        return h.model_dump()
    except KeyError:
        raise HTTPException(404, f"Hotfix {req.hotfix_id} not found")


@router.get("/recall")
async def list_recalls(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_recalls(limit=limit)
    return {"items": [r.model_dump() for r in items], "total": len(items)}


@router.post("/recall/execute")
async def execute_recall(req: ExecuteRecallRequest) -> dict[str, Any]:
    eng = get_engine()
    r = eng.create_recall(
        from_version=req.from_version,
        to_version=req.target_version,
        reason=req.reason,
    )
    r = eng.execute_recall(r.id)
    return r.model_dump()
