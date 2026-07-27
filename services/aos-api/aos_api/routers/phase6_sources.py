"""Phase 6 · Sources 路由."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.phase6_datasource_engine import get_engine

router = APIRouter(prefix="/api/datasource/sources", tags=["phase6-sources"])


class CreateSourceRequest(BaseModel):
    name: str
    connector_id: str = ""
    source_type: str = "database"
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    config: dict[str, Any] = {}
    status: str = "active"
    tags: list[str] = []
    owner: str = "system"


class UpdateSourceRequest(BaseModel):
    name: str | None = None
    connector_id: str | None = None
    source_type: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    config: dict[str, Any] | None = None
    status: str | None = None
    tags: list[str] | None = None
    owner: str | None = None


@router.get("")
async def list_sources(
    search: str | None = Query(None),
    source_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_sources(search=search, source_type=source_type, page=page, page_size=page_size)
    return {"items": [s.model_dump() for s in items], "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_source(req: CreateSourceRequest) -> dict[str, Any]:
    eng = get_engine()
    s = eng.create_source(**req.model_dump())
    return s.model_dump()


@router.get("/{source_id}")
async def get_source(source_id: str) -> dict[str, Any]:
    eng = get_engine()
    s = eng.get_source(source_id)
    if s is None:
        raise HTTPException(404, f"Source {source_id} not found")
    return s.model_dump()


@router.put("/{source_id}")
async def update_source(source_id: str, req: UpdateSourceRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        s = eng.update_source(source_id, **data)
        return s.model_dump()
    except KeyError:
        raise HTTPException(404, f"Source {source_id} not found")


@router.delete("/{source_id}")
async def delete_source(source_id: str) -> dict[str, Any]:
    eng = get_engine()
    existed = eng.delete_source(source_id)
    if not existed:
        raise HTTPException(404, f"Source {source_id} not found")
    return {"deleted": True, "source_id": source_id}


@router.post("/{source_id}/test-connection")
async def test_connection(source_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.test_connection(source_id)
    except KeyError:
        raise HTTPException(404, f"Source {source_id} not found")
