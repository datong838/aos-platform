"""Widgets registry router — Phase 1 Workshop backend.

GET/POST /v1/widgets — widget catalog (filter by source).
GET /v1/widgets/:id — widget detail.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from aos_api.widget_catalog import create_widget, get_widget, list_widgets

router = APIRouter(prefix="/v1/widgets", tags=["widgets-registry"])


class WidgetCreate(BaseModel):
    name: str
    nameZh: str = ""
    type: str = "unknown"
    source: str = "builtin"
    category: str = "general"
    icon: str = ""
    description: str = ""
    configSchema: dict[str, Any] = {}
    version: str = "1.0.0"


@router.get("")
def list_widgets_api(
    source: str | None = Query(default=None),
) -> dict[str, Any]:
    items = list_widgets(source)
    return {"items": items, "count": len(items)}


@router.post("")
def create_widget_api(body: WidgetCreate) -> dict[str, Any]:
    item = create_widget(body.model_dump())
    return {"ok": True, "item": item}


@router.get("/{widget_id}")
def get_widget_api(widget_id: str) -> dict[str, Any]:
    item = get_widget(widget_id)
    if not item:
        return {"item": None}
    return item
