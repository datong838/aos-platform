"""Phase 6 · Schemas 路由 (Schema 探索)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.phase6_datasource_engine import get_engine

router = APIRouter(prefix="/api/datasource", tags=["phase6-schemas"])


class PreviewRequest(BaseModel):
    schema_name: str = ""
    table_name: str = ""
    limit: int = 50


@router.get("/sources/{source_id}/schemas")
async def list_schemas(source_id: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        raise HTTPException(404, f"Source {source_id} not found")
    items = eng.list_schemas(source_id)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/sources/{source_id}/schemas/{schema_name}/tables")
async def list_tables(source_id: str, schema_name: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        raise HTTPException(404, f"Source {source_id} not found")
    items = eng.list_tables(source_id, schema_name)
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.get("/sources/{source_id}/schemas/{schema_name}/tables/{table_name}/columns")
async def list_columns(source_id: str, schema_name: str, table_name: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        raise HTTPException(404, f"Source {source_id} not found")
    items = eng.list_columns(source_id, schema_name, table_name)
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.get("/sources/{source_id}/schemas/{schema_name}/tables/{table_name}/foreign-keys")
async def list_foreign_keys(source_id: str, schema_name: str, table_name: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_source(source_id) is None:
        raise HTTPException(404, f"Source {source_id} not found")
    items = eng.list_foreign_keys(source_id, schema_name, table_name)
    return {"items": [fk.model_dump() for fk in items], "count": len(items)}


@router.post("/sources/{source_id}/preview")
async def preview_data(source_id: str, req: PreviewRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.preview_data(source_id, schema_name=req.schema_name, table_name=req.table_name, limit=req.limit)
    except KeyError:
        raise HTTPException(404, f"Source {source_id} not found")


@router.get("/sources/{source_id}/capabilities")
async def get_source_capabilities(source_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        caps = eng.get_source_capabilities(source_id)
        return {"source_id": source_id, "capabilities": caps}
    except KeyError:
        raise HTTPException(404, f"Source {source_id} not found")
