"""Phase 4 · Ontology Types 路由.

object-types + objects + properties + column-mapping + automap + preview + recent + count
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.ontology_engine import get_engine

router = APIRouter(prefix="/v1/ontology", tags=["ontology-types"])


# ─────────── Request models ───────────


class UpdateObjectTypeRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    status: str | None = None
    category: str | None = None
    backing_dataset: str | None = None


class AddPropertyRequest(BaseModel):
    name: str
    display_name: str = ""
    datatype: str = "string"
    nullable: bool = True
    is_primary_key: bool = False
    is_display_name: bool = False
    description: str = ""


class AutomapRequest(BaseModel):
    columns: list[str] | None = None


class SetColumnMappingRequest(BaseModel):
    mappings: list[dict[str, Any]]


# ─────────── object-types ───────────


@router.get("/object-types")
async def list_object_types(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc"),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_object_types(
        search=search, page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order
    )
    return {
        "items": [o.model_dump() for o in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/object-types/{ot_id}")
async def get_object_type(ot_id: str) -> dict[str, Any]:
    eng = get_engine()
    ot = eng.get_object_type(ot_id)
    if ot is None:
        raise HTTPException(404, f"ObjectType {ot_id} not found")
    eng.add_recent(ot_id)
    return ot.model_dump()


@router.put("/object-types/{ot_id}")
async def update_object_type(ot_id: str, req: UpdateObjectTypeRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        ot = eng.update_object_type(ot_id, **data)
        return ot.model_dump()
    except KeyError:
        raise HTTPException(404, f"ObjectType {ot_id} not found")


@router.get("/object-types/{ot_id}/count")
async def count_instances(ot_id: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_object_type(ot_id) is None:
        raise HTTPException(404, f"ObjectType {ot_id} not found")
    return {"object_type_id": ot_id, "count": eng.count_instances(ot_id)}


@router.get("/recent")
async def list_recent(
    user_id: str = Query("default"),
    limit: int = Query(10, ge=1, le=100),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_recent(user_id=user_id, limit=limit)
    return {"items": items, "count": len(items)}


# ─────────── objects ───────────


@router.get("/objects")
async def list_objects(
    object_type: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_objects(
        object_type_id=object_type, search=search, page=page, page_size=page_size
    )
    return {
        "items": [o.model_dump() for o in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/objects/{obj_id}")
async def get_object(obj_id: str) -> dict[str, Any]:
    eng = get_engine()
    obj = eng.get_object(obj_id)
    if obj is None:
        raise HTTPException(404, f"Object {obj_id} not found")
    return obj.model_dump()


# ─────────── properties ───────────


@router.get("/object-types/{ot_id}/properties")
async def list_properties(ot_id: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_object_type(ot_id) is None:
        raise HTTPException(404, f"ObjectType {ot_id} not found")
    items = eng.list_properties(ot_id)
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.post("/object-types/{ot_id}/properties")
async def add_property(ot_id: str, req: AddPropertyRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        prop = eng.add_property(ot_id, **req.model_dump())
        return prop.model_dump()
    except KeyError:
        raise HTTPException(404, f"ObjectType {ot_id} not found")


# ─────────── column-mapping / automap / preview ───────────


@router.get("/object-types/{ot_id}/column-mapping")
async def get_column_mapping(ot_id: str) -> dict[str, Any]:
    eng = get_engine()
    if eng.get_object_type(ot_id) is None:
        raise HTTPException(404, f"ObjectType {ot_id} not found")
    items = eng.list_column_mapping(ot_id)
    return {"items": [m.model_dump() for m in items], "count": len(items)}


@router.post("/object-types/{ot_id}/automap")
async def automap(ot_id: str, req: AutomapRequest | None = None) -> dict[str, Any]:
    eng = get_engine()
    try:
        cols = req.columns if req and req.columns else None
        items = eng.automap(ot_id, cols)
        return {"items": [m.model_dump() for m in items], "count": len(items)}
    except KeyError:
        raise HTTPException(404, f"ObjectType {ot_id} not found")


@router.get("/object-types/{ot_id}/preview")
async def preview(ot_id: str, limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.preview(ot_id, limit=limit)
    except KeyError:
        raise HTTPException(404, f"ObjectType {ot_id} not found")
