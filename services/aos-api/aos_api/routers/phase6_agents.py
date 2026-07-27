"""Phase 6 · Agents 路由 (边缘代理)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.phase6_datasource_engine import get_engine

router = APIRouter(prefix="/api/datasource/agents", tags=["phase6-agents"])


class UpdateAgentConfigRequest(BaseModel):
    config: dict[str, Any]


@router.get("")
async def list_agents(
    status: str | None = Query(None),
    region: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_agents(status=status, region=region, page=page, page_size=page_size)
    return {"items": [a.model_dump() for a in items], "total": total, "page": page, "page_size": page_size}


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    eng = get_engine()
    a = eng.get_agent(agent_id)
    if a is None:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return a.model_dump()


@router.get("/{agent_id}/metrics")
async def get_agent_metrics(agent_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.get_agent_metrics(agent_id)
    except KeyError:
        raise HTTPException(404, f"Agent {agent_id} not found")


@router.get("/{agent_id}/sources")
async def get_agent_sources(agent_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        sources = eng.get_agent_sources(agent_id)
        return {"items": [s.model_dump() for s in sources], "count": len(sources)}
    except KeyError:
        raise HTTPException(404, f"Agent {agent_id} not found")


@router.get("/{agent_id}/health")
async def get_agent_health(agent_id: str) -> dict[str, Any]:
    eng = get_engine()
    try:
        return eng.get_agent_health(agent_id)
    except KeyError:
        raise HTTPException(404, f"Agent {agent_id} not found")


@router.put("/{agent_id}/config")
async def update_agent_config(agent_id: str, req: UpdateAgentConfigRequest) -> dict[str, Any]:
    eng = get_engine()
    try:
        a = eng.update_agent_config(agent_id, req.config)
        return a.model_dump()
    except KeyError:
        raise HTTPException(404, f"Agent {agent_id} not found")
