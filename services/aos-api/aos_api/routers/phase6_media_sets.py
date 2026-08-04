"""Phase 6 · Media Sets 路由."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.phase6_datasource_engine import get_engine

router = APIRouter(
    prefix="/api/datasource/media-sets",
    tags=["phase6-media-sets"],
    dependencies=[Depends(require_principal)],
)


class TransformRequest(BaseModel):
    operation: str = "resize"
    params: dict[str, Any] = {}


@router.get("/{media_set_id}")
async def get_media_set(media_set_id: str) -> dict[str, Any]:
    eng = get_engine()
    ms = eng.get_media_set(media_set_id)
    if ms is None:
        raise HTTPException(404, f"MediaSet {media_set_id} not found")
    return ms.model_dump()


@router.get("/{media_set_id}/files")
async def list_media_files(media_set_id: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_media_set(media_set_id) is None:
        raise HTTPException(404, f"MediaSet {media_set_id} not found")
    items = eng.list_media_set_files(media_set_id)
    return {"items": [f.model_dump() for f in items], "count": len(items)}


@router.post("/{media_set_id}/transform")
async def transform_files(media_set_id: str, req: TransformRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.transform_media_files(media_set_id, req.operation, req.params)
    except KeyError:
        raise HTTPException(404, f"MediaSet {media_set_id} not found")
