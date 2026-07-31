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


# ── Task 路由（Phase 1 — TAOR 循环）──

from aos_api.aip_task_model import (
    ActionRequest, ExecutionPlan, Task, TaskStep,
)
from aos_api.aip_llm_adapter import get_llm_adapter
from aos_api.public_contracts import ContractViolation, TaskStatus

# 内存存储（Phase 2 替换为 Redis）
_tasks: dict[str, Task] = {}


class CreateTaskRequest(BaseModel):
    type: str = "generic"
    title: str = ""
    description: str = ""
    context: dict[str, Any] = {}
    # 可选：直接传入步骤（跳过 Plan Mode）
    steps: list[dict[str, Any]] | None = None


class ApprovePlanRequest(BaseModel):
    approved_by: str = "user"


@router.post("/tasks")
async def create_task(req: CreateTaskRequest) -> dict[str, Any]:
    """创建任务 — Plan Mode 生成执行计划。

    如果传入 steps，直接构建计划；
    否则用 LLM 生成计划（Phase 2 实现）。
    """
    task = Task(
        type=req.type,
        title=req.title,
        description=req.description,
        context=req.context,
    )

    if req.steps:
        # 直接构建计划
        steps = []
        for s in req.steps:
            step = TaskStep(
                name=s.get("name", ""),
                action=ActionRequest(
                    action_type=s.get("action_type", "llm_call"),
                    params=s.get("params", {}),
                ),
                action_config=s.get("config", {}),
            )
            steps.append(step)
        task.plan = ExecutionPlan(steps=steps, task_id=task.id, status="draft")
    else:
        # Plan Mode — LLM 生成计划（Phase 2）
        # Phase 1: 创建空计划，等待人工添加步骤
        task.plan = ExecutionPlan(steps=[], task_id=task.id, status="draft")

    task.transition(TaskStatus.PLANNING)
    _tasks[task.id] = task
    return {"ok": True, "task": task.model_dump()}


@router.get("/tasks")
async def list_tasks(status: str | None = Query(None)) -> dict[str, Any]:
    items = list(_tasks.values())
    if status:
        items = [t for t in items if t.status == status]
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return {"task": task.model_dump()}


@router.post("/tasks/{task_id}/plan/approve")
async def approve_plan(task_id: str, req: ApprovePlanRequest) -> dict[str, Any]:
    """审批执行计划 — Plan Mode 的用户确认环节。"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    if not task.plan:
        raise HTTPException(400, "Task has no plan")

    try:
        if task.status == TaskStatus.PLANNING:
            task.transition(TaskStatus.AWAITING_APPROVAL)
        task.transition(TaskStatus.APPROVED)
    except ContractViolation as exc:
        raise HTTPException(409, {"code": exc.code, "message": exc.message}) from exc
    task.plan.status = "approved"
    task.plan.approved_by = req.approved_by
    from time import time as _time
    task.plan.approved_at = _time()
    return {"ok": True, "plan": task.plan.model_dump()}


@router.post("/tasks/{task_id}/execute")
async def execute_task(task_id: str) -> dict[str, Any]:
    """执行任务 — 走 TAOR 循环。"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")

    from aos_api.aip_taor_loop import get_controller

    controller = get_controller()
    try:
        result = controller.run(task)
    except ContractViolation as exc:
        raise HTTPException(409, {"code": exc.code, "message": exc.message}) from exc
    _tasks[task_id] = task  # 更新存储
    return {"ok": True, "result": result.model_dump(), "task": task.model_dump()}
