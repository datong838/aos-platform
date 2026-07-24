"""W2-#13 · Object Views 微件系统 API 路由。

详见 docs/palantier/20_tech/220tech_w2-c-ontology-manager.md §2.1。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from aos_api.errors import ApiError
from aos_api.object_views import (
    ObjectView,
    ObjectViewError,
    ViewWidget,
    get_store,
    list_widget_catalog,
)

router = APIRouter(tags=["object-views"])


def _map_error(err: ObjectViewError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


class WidgetIn(BaseModel):
    kind: str
    title: str = ""
    bound_field: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class CreateViewRequest(BaseModel):
    name: str
    otd_id: str
    widgets: list[WidgetIn] = Field(default_factory=list)
    is_default: bool = False


class UpdateViewRequest(BaseModel):
    name: str | None = None
    is_default: bool | None = None


class ReorderRequest(BaseModel):
    widget_ids: list[str]


@router.get("/v1/object-views/widgets")
def list_widgets():
    return {"items": list_widget_catalog()}


@router.get("/v1/object-views")
def list_views(otd_id: str | None = None):
    store = get_store()
    views = store.list_by_otd(otd_id) if otd_id else store.list_all()
    return {"items": [v.model_dump() for v in views]}


@router.post("/v1/object-views")
def create_view(req: CreateViewRequest):
    widgets = [
        ViewWidget(kind=w.kind, title=w.title, bound_field=w.bound_field, config=w.config)
        for w in req.widgets
    ]
    view = ObjectView(name=req.name, otd_id=req.otd_id, widgets=widgets, is_default=req.is_default)
    try:
        created = get_store().create(view)
    except ObjectViewError as err:
        raise _map_error(err) from err
    return created.model_dump()


@router.get("/v1/object-views/{view_id}")
def get_view(view_id: str):
    view = get_store().get(view_id)
    if view is None:
        raise ApiError(code="NOT_FOUND", message=f"视图 {view_id} 不存在", status_code=404)
    return view.model_dump()


@router.put("/v1/object-views/{view_id}")
def update_view(view_id: str, req: UpdateViewRequest):
    fields: dict[str, Any] = {}
    if req.name is not None:
        fields["name"] = req.name
    if req.is_default is not None:
        fields["is_default"] = req.is_default
    try:
        view = get_store().update(view_id, **fields)
    except ObjectViewError as err:
        raise _map_error(err) from err
    return view.model_dump()


@router.post("/v1/object-views/{view_id}/widgets")
def add_widget(view_id: str, req: WidgetIn):
    widget = ViewWidget(kind=req.kind, title=req.title, bound_field=req.bound_field, config=req.config)
    try:
        view = get_store().add_widget(view_id, widget)
    except ObjectViewError as err:
        raise _map_error(err) from err
    return view.model_dump()


@router.post("/v1/object-views/{view_id}/reorder")
def reorder_widgets(view_id: str, req: ReorderRequest):
    try:
        view = get_store().reorder_widgets(view_id, req.widget_ids)
    except ObjectViewError as err:
        raise _map_error(err) from err
    return view.model_dump()


@router.delete("/v1/object-views/{view_id}/widgets/{widget_id}")
def remove_widget(view_id: str, widget_id: str):
    try:
        view = get_store().remove_widget(view_id, widget_id)
    except ObjectViewError as err:
        raise _map_error(err) from err
    return view.model_dump()


@router.delete("/v1/object-views/{view_id}")
def delete_view(view_id: str):
    ok = get_store().delete(view_id)
    return {"view_id": view_id, "deleted": ok}
