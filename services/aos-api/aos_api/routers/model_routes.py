"""Phase 2 · Model Routes router (admin view).

GET /v1/aip/model-admin/routes         — list routing rules
PUT /v1/aip/model-admin/routes         — bulk replace routing rules

NOTE: /v1/aip/model-routes is reserved by the runtime LLM routing layer
(wave_ext + llm_routing); this admin path is distinct.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from aos_api.model_routes import list_routes, upsert_route, delete_route

router = APIRouter(prefix="/v1/aip/model-admin", tags=["aip-model-routes"])


class RouteItem(BaseModel):
    id: str | None = None
    taskType: str
    primaryModel: str
    fallbackModel: str = ""
    outboundPolicy: str = "deny_public"
    priority: int = 100
    enabled: bool = True


class RoutesPutRequest(BaseModel):
    routes: list[RouteItem]


@router.get("/routes")
def list_routes_api(taskType: str | None = Query(None)) -> dict[str, Any]:
    items = list_routes(task_type=taskType)
    return {"items": items, "count": len(items)}


@router.put("/routes")
def put_routes_api(body: RoutesPutRequest) -> dict[str, Any]:
    # Collect existing ids so we can delete ones not in the new set
    from aos_api.model_routes import list_routes as _list_routes

    existing = {r["id"] for r in _list_routes()}
    new_ids: set[str] = set()
    items = []
    for r in body.routes:
        item = upsert_route(r.model_dump())
        new_ids.add(item["id"])
        items.append(item)
    # Delete removed rules
    for old_id in existing - new_ids:
        delete_route(old_id)
    return {"items": items, "count": len(items)}
