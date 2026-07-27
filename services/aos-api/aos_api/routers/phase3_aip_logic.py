"""Phase 3 · AIP Logic 路由.

POST /v1/aip/logic/execute      — 逻辑执行（DAG 分支/汇聚）
GET  /v1/aip/logic/automations  — 自动化触发器列表
POST /v1/aip/logic/automations  — 创建自动化触发器
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.aip_logic_engine import get_engine, LogicBlock

router = APIRouter(prefix="/v1/aip", tags=["aip-logic"])


class ExecuteBlock(BaseModel):
    id: str = ""
    kind: str = "task"
    name: str = ""
    config: dict[str, Any] = {}
    inputs: list[str] = []


class LogicExecuteRequest(BaseModel):
    blocks: list[ExecuteBlock]
    context: dict[str, Any] = {}


class CreateAutomationRequest(BaseModel):
    name: str
    trigger_type: str = "schedule"
    trigger_config: dict[str, Any] = {}
    flow_id: str = ""


@router.post("/logic/execute")
async def execute_logic(req: LogicExecuteRequest) -> dict[str, Any]:
    eng = get_engine()
    blocks = [LogicBlock(**b.model_dump()) for b in req.blocks]
    result = eng.execute_flow(blocks, context=req.context)
    return result


@router.get("/logic/automations")
async def list_automations(
    status: str | None = Query(None),
    trigger_type: str | None = Query(None),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_automations(status=status, trigger_type=trigger_type)
    return {"items": [a.model_dump() for a in items], "count": len(items)}


@router.post("/logic/automations")
async def create_automation(req: CreateAutomationRequest) -> dict[str, Any]:
    eng = get_engine()
    auto = eng.create_automation(
        name=req.name,
        trigger_type=req.trigger_type,
        trigger_config=req.trigger_config,
        flow_id=req.flow_id,
    )
    return {"ok": True, "item": auto.model_dump()}
