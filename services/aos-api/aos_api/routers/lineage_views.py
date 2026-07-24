"""W2-#4 · Lineage 增强视图 API 路由。

详见 docs/palantier/20_tech/220tech_w2-e-media-lineage-ide.md §2.3。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.lineage_views import (
    ColumnLineage,
    LineageViewError,
    get_service,
    list_node_kinds,
    list_palette,
)

router = APIRouter(tags=["lineage-views"])


class ColumnLineageIn(BaseModel):
    source_columns: list[str] = Field(default_factory=list)
    target_column: str = ""
    transform_expr: str = ""


class SetColumnLineageRequest(BaseModel):
    source: str
    target: str
    columns: list[ColumnLineageIn]


@router.get("/v1/lineage-views/palette")
def get_palette():
    return {"items": list_palette(), "total": len(list_palette())}


@router.get("/v1/lineage-views/node-kinds")
def get_node_kinds():
    return {"items": list_node_kinds()}


@router.get("/v1/lineage-views/color")
def get_color(by: str = "type"):
    try:
        result = get_service().color(by)
    except LineageViewError as err:
        from aos_api.errors import ApiError
        raise ApiError(code=err.code, message=err.message, status_code=400) from err
    return {"by": by, "colors": result}


@router.get("/v1/lineage-views/layout")
def get_layout():
    return get_service().layout().model_dump()


@router.get("/v1/lineage-views/summary")
def get_summary():
    return get_service().summary()


@router.post("/v1/lineage-views/column-lineage")
def set_column_lineage(req: SetColumnLineageRequest):
    cols = [
        ColumnLineage(source_columns=c.source_columns, target_column=c.target_column, transform_expr=c.transform_expr)
        for c in req.columns
    ]
    get_service().set_column_lineage(req.source, req.target, cols)
    return {"source": req.source, "target": req.target, "count": len(cols)}


@router.get("/v1/lineage-views/column-lineage/{source}/{target}")
def get_column_lineage(source: str, target: str):
    cols = get_service().get_column_lineage(source, target)
    return {"source": source, "target": target, "columns": [c.model_dump() for c in cols]}
