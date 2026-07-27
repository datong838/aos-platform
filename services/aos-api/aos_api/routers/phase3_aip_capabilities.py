"""Phase 3 · AIP Capabilities & Registry 路由.

GET  /v1/aip/agent-registry       — 注册表（含统计汇总）
GET  /v1/aip/capabilities         — 能力列表
PUT  /v1/aip/capabilities/{id}    — 能力配置更新
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.aip_capabilities_engine import get_engine

router = APIRouter(prefix="/v1/aip", tags=["aip-capabilities"])


class CapabilityUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None


@router.get("/agent-registry")
async def list_registry(
    status: str | None = Query(None),
    scope: str | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_registry(status=status, scope=scope)
    stats = eng.registry_stats()
    return {
        "items": [e.model_dump() for e in items],
        "count": len(items),
        "stats": stats,
    }


@router.get("/capabilities")
async def list_capabilities(
    category: str | None = Query(None),
    enabled: bool | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_capabilities(category=category, enabled=enabled)
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.put("/capabilities/{cap_id}")
async def update_capability(cap_id: str, body: CapabilityUpdate) -> dict[str, Any]:
    eng = get_engine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    try:
        cap = eng.update_capability(cap_id, **updates)
    except KeyError:
        raise HTTPException(404, f"Capability {cap_id} not found")
    return {"ok": True, "item": cap.model_dump()}
