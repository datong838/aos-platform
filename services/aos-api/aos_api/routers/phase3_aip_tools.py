"""Phase 3 · AIP Tools & Evals 路由.

GET  /v1/aip/tools                — 工具目录（7 类）
GET  /v1/aip/tools/{id}/quality   — 工具质量评分
GET  /v1/aip/evals                — Eval 状态（含 l4_allowed）
POST /v1/aip/circuit/trip         — 模拟熔断（bonus）
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.aip_tools_engine import get_engine

router = APIRouter(prefix="/v1/aip", tags=["aip-tools-evals"])


class CircuitTripRequest(BaseModel):
    tool_id: str
    reason: str = "manual_trip"


@router.get("/tools")
async def list_tools(
    category: str | None = Query(None),
    enabled: bool | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_tools(category=category, enabled=enabled)
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.get("/tools/{tool_id}/quality")
async def get_quality(tool_id: str) -> dict[str, Any]:
    eng = get_engine()
    quality = eng.get_quality(tool_id)
    if quality is None:
        raise HTTPException(404, f"Quality score for tool {tool_id} not found")
    return quality.model_dump()


@router.get("/evals")
async def list_evals(
    eval_type: str | None = Query(None),
    status: str | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_evals(eval_type=eval_type, status=status)
    return {
        "items": [
            {
                "id": e.id,
                "name": e.name,
                "eval_type": e.eval_type,
                "target_id": e.target_id,
                "status": e.status,
                "score": e.score,
                "l4_allowed": e.l4_allowed,
                "metrics": e.metrics,
            }
            for e in items
        ],
        "count": len(items),
    }


@router.post("/circuit/trip")
async def trip_circuit(req: CircuitTripRequest) -> dict[str, Any]:
    eng = get_engine()
    rec = eng.trip_circuit(req.tool_id, req.reason)
    return {"ok": True, "circuit_id": rec.id, "state": rec.state}
