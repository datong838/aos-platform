"""Phase 3 · AIP Capabilities & Registry 路由.

PUT  /v1/aip/capabilities/{id}    — 能力配置更新（upsert）
POST /v1/aip/capabilities/test    — 连通测试（W4-B5）

能力列表的兼容 authority 是 ``wave_ext``；本模块不再注册重复 GET。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from aos_api.aip_capabilities_engine import get_engine
from aos_api.auth import Principal, require_principal

router = APIRouter(prefix="/v1/aip", tags=["aip-capabilities"])


class CapabilityUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None
    category: str | None = None


class CapabilityTestIn(BaseModel):
    id: str | None = None
    capabilityId: str | None = None
    endpoint: str | None = None


@router.get("/agent-registry")
async def list_registry(
    status: str | None = Query(None),
    scope: str | None = Query(None),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_engine()
    items = eng.list_registry(status=status, scope=scope)
    stats = eng.registry_stats()
    return {
        "items": [e.model_dump() for e in items],
        "count": len(items),
        "stats": stats,
    }


@router.put("/capabilities/{cap_id}")
async def update_capability(
    cap_id: str,
    body: CapabilityUpdate,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_engine()
    eng.ensure_plugin_defaults()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    cap = eng.upsert_capability(cap_id, **updates)
    return {"ok": True, "item": cap.model_dump()}


@router.post("/capabilities/test")
async def test_capability(
    body: CapabilityTestIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    eng = get_engine()
    cap_id = body.capabilityId or body.id
    result = eng.test_connectivity(cap_id=cap_id, endpoint=body.endpoint)
    return {"ok": True, **result}
