"""W2-#12 · OE 探索图表可视化 API 路由。

详见 docs/palantier/20_tech/220tech_w2-c-ontology-manager.md §2.2。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.object_explorer import (
    ExplorerDesign,
    ExplorerError,
    ExplorerFilter,
    ExplorerMetric,
    get_store,
    list_chart_catalog,
)

router = APIRouter(tags=["object-explorer"])


def _map_error(err: ExplorerError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


class MetricIn(BaseModel):
    field: str
    agg: str = "count"


class FilterIn(BaseModel):
    field: str
    expr: str


class CreateDesignRequest(BaseModel):
    name: str
    otd_id: str
    chart_kind: str
    group_by: str = ""
    metrics: list[MetricIn] = Field(default_factory=list)
    filters: list[FilterIn] = Field(default_factory=list)
    sort_order: int = 0


class UpdateDesignRequest(BaseModel):
    name: str | None = None
    chart_kind: str | None = None
    group_by: str | None = None
    metrics: list[MetricIn] | None = None
    filters: list[FilterIn] | None = None
    sort_order: int | None = None


class RenderRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/v1/object-explorer/charts")
def list_charts():
    return {"items": list_chart_catalog()}


@router.get("/v1/object-explorer/designs")
def list_designs(otd_id: str | None = None):
    store = get_store()
    designs = store.list_by_otd(otd_id) if otd_id else store.list_all()
    return {"items": [d.model_dump() for d in designs]}


@router.post("/v1/object-explorer/designs")
def create_design(req: CreateDesignRequest):
    metrics = [ExplorerMetric(field=m.field, agg=m.agg) for m in req.metrics]  # type: ignore[arg-type]
    filters = [ExplorerFilter(field=f.field, expr=f.expr) for f in req.filters]
    design = ExplorerDesign(
        name=req.name,
        otd_id=req.otd_id,
        chart_kind=req.chart_kind,  # type: ignore[arg-type]
        group_by=req.group_by,
        metrics=metrics,
        filters=filters,
        sort_order=req.sort_order,
    )
    try:
        created = get_store().create(design)
    except ExplorerError as err:
        raise _map_error(err) from err
    return created.model_dump()


@router.get("/v1/object-explorer/designs/{design_id}")
def get_design(design_id: str):
    design = get_store().get(design_id)
    if design is None:
        raise ApiError(code="NOT_FOUND", message=f"设计 {design_id} 不存在", status_code=404)
    return design.model_dump()


@router.put("/v1/object-explorer/designs/{design_id}")
def update_design(design_id: str, req: UpdateDesignRequest):
    fields: dict[str, Any] = {}
    if req.name is not None:
        fields["name"] = req.name
    if req.chart_kind is not None:
        fields["chart_kind"] = req.chart_kind
    if req.group_by is not None:
        fields["group_by"] = req.group_by
    if req.metrics is not None:
        fields["metrics"] = [ExplorerMetric(field=m.field, agg=m.agg) for m in req.metrics]  # type: ignore[arg-type]
    if req.filters is not None:
        fields["filters"] = [ExplorerFilter(field=f.field, expr=f.expr) for f in req.filters]
    if req.sort_order is not None:
        fields["sort_order"] = req.sort_order
    try:
        design = get_store().update(design_id, **fields)
    except ExplorerError as err:
        raise _map_error(err) from err
    return design.model_dump()


@router.post("/v1/object-explorer/designs/{design_id}/render")
def render_design(design_id: str, req: RenderRequest):
    try:
        result = get_store().render(design_id, req.rows)
    except ExplorerError as err:
        raise _map_error(err) from err
    return result


@router.post("/v1/object-explorer/designs/{design_id}/undo")
def undo_design(design_id: str):
    try:
        design = get_store().undo(design_id)
    except ExplorerError as err:
        raise _map_error(err) from err
    return design.model_dump()


@router.post("/v1/object-explorer/designs/{design_id}/redo")
def redo_design(design_id: str):
    try:
        design = get_store().redo(design_id)
    except ExplorerError as err:
        raise _map_error(err) from err
    return design.model_dump()


@router.delete("/v1/object-explorer/designs/{design_id}")
def delete_design(design_id: str):
    ok = get_store().delete(design_id)
    return {"design_id": design_id, "deleted": ok}
