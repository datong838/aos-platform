"""Phase 3 · AIP Agents 路由.

GET  /v1/aip/agents                — Agent 列表（含统计）
GET  /v1/aip/agents/{id}           — Agent 详情
GET  /v1/aip/agents/{id}/prompt    — 系统提示词
PUT  /v1/aip/agents/{id}/prompt    — 更新提示词
GET  /v1/aip/agents/{id}/tools     — 工具列表
GET  /v1/aip/agents/{id}/guardrails — 安全护栏
PUT  /v1/aip/agents/{id}/guardrails — 更新护栏
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.aip_agents_engine import get_engine

router = APIRouter(prefix="/v1/aip", tags=["aip-agents"])


class PromptUpdate(BaseModel):
    prompt: str


class GuardrailsUpdate(BaseModel):
    rules: list[dict[str, Any]]


@router.get("/agents")
async def list_agents(
    source: str | None = Query(None),
    tag: str | None = Query(None),
    status: str | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list(source=source, tag=tag, status=status)
    stats = eng.stats()
    return {
        "items": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "source": a.source,
                "tags": a.tags,
                "status": a.status,
                "calls": a.calls,
                "success_rate": a.success_rate,
                "avg_latency_ms": a.avg_latency_ms,
            }
            for a in items
        ],
        "count": len(items),
        "stats": stats,
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    eng = get_engine()
    agent = eng.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return agent.model_dump()


@router.get("/agents/{agent_id}/prompt")
async def get_prompt(agent_id: str) -> dict[str, Any]:
    eng = get_engine()
    prompt = eng.get_prompt(agent_id)
    if prompt is None:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"agent_id": agent_id, "prompt": prompt}


@router.put("/agents/{agent_id}/prompt")
async def update_prompt(agent_id: str, body: PromptUpdate) -> dict[str, Any]:
    eng = get_engine()
    try:
        agent = eng.set_prompt(agent_id, body.prompt)
    except KeyError:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"ok": True, "prompt": agent.system_prompt}


@router.get("/agents/{agent_id}/tools")
async def get_tools(agent_id: str) -> dict[str, Any]:
    eng = get_engine()
    tools = eng.list_tools(agent_id)
    if not tools and eng.get(agent_id) is None:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"agent_id": agent_id, "items": [t.model_dump() for t in tools], "count": len(tools)}


@router.get("/agents/{agent_id}/guardrails")
async def get_guardrails(agent_id: str) -> dict[str, Any]:
    eng = get_engine()
    rules = eng.get_guardrails(agent_id)
    if not rules and eng.get(agent_id) is None:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"agent_id": agent_id, "items": [r.model_dump() for r in rules], "count": len(rules)}


@router.put("/agents/{agent_id}/guardrails")
async def update_guardrails(agent_id: str, body: GuardrailsUpdate) -> dict[str, Any]:
    eng = get_engine()
    try:
        agent = eng.set_guardrails(agent_id, body.rules)
    except KeyError:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return {"ok": True, "count": len(agent.guardrails)}
