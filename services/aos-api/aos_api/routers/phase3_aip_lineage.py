"""Phase 3 · AIP Lineage 路由.

GET /v1/aip/lineage/{id} — Trace（6 段：输入/检索/推理/熔断/输出/回填）
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from aos_api.aip_lineage_engine import get_engine

router = APIRouter(prefix="/v1/aip", tags=["aip-lineage"])


@router.get("/lineage/{record_id}")
async def get_lineage(record_id: str) -> dict[str, Any]:
    eng = get_engine()
    rec = eng.get(record_id)
    if not rec:
        raise HTTPException(404, f"Lineage record {record_id} not found")
    return rec.model_dump()


@router.get("/lineage")
async def list_lineage(
    agent_id: str | None = Query(None),
    status: str | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list(agent_id=agent_id, status=status)
    return {"items": [r.model_dump() for r in items], "count": len(items), "stats": eng.stats()}
