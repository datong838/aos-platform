"""W2-BG 批次 API 路由 — 对象物化 + 行级权限 + 列级权限 + Agent六工具."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.materialized_access_control import (
    AgentToolsEngineError,
    ColumnLevelEngineError,
    MaterializationEngineError,
    RowLevelEngineError,
    get_agent_tools_engine,
    get_column_level_engine,
    get_materialization_engine,
    get_row_level_engine,
)

router = APIRouter(prefix="/materialized-access-control", tags=["materialized-access-control"])


def _map_materialization_error(err: MaterializationEngineError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_row_level_error(err: RowLevelEngineError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_column_level_error(err: ColumnLevelEngineError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_agent_tools_error(err: AgentToolsEngineError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class CreateMaterializationTaskRequest(BaseModel):
    object_id: str
    materialization_type: str = "auto"
    interval_hours: int = 6
    description: str = ""


class RunMaterializationRequest(BaseModel):
    task_id: str


class CreateRowLevelPolicyRequest(BaseModel):
    view_id: str
    name: str
    policy_type: str
    condition_expression: str
    status: str = "active"
    description: str = ""


class RowLevelEvaluateRequest(BaseModel):
    user_id: str


class CreateColumnLevelPolicyRequest(BaseModel):
    mdo_id: str
    name: str
    policy_type: str
    columns: list[str] = []
    status: str = "active"
    description: str = ""
    max_sources: int = 70


class ColumnLevelEvaluateRequest(BaseModel):
    user_id: str


class CreateAgentToolRequest(BaseModel):
    name: str
    tool_type: str
    description: str = ""
    schema: dict[str, Any] = {}
    status: str = "enabled"


class ExecuteToolRequest(BaseModel):
    executed_by: str
    params: dict[str, Any] = {}


# ════════════════════ Materialization API ════════════════════

@router.post("/materialization-tasks")
def create_materialization_task(
    req: CreateMaterializationTaskRequest, _principal: Principal = Depends(require_principal),
):
    try:
        return get_materialization_engine().create_task(
            object_id=req.object_id,
            materialization_type=req.materialization_type,
            interval_hours=req.interval_hours,
        )
    except MaterializationEngineError as err:
        raise _map_materialization_error(err) from err


@router.get("/materialization-tasks/{task_id}")
def get_materialization_task(
    task_id: str, _principal: Principal = Depends(require_principal),
):
    try:
        return get_materialization_engine().get_task(task_id)
    except MaterializationEngineError as err:
        raise _map_materialization_error(err) from err


@router.get("/materialization-tasks")
def list_materialization_tasks(
    object_id: str | None = None,
    materialization_type: str | None = None,
    status: str | None = None,
    _principal: Principal = Depends(require_principal),
):
    return {
        "items": get_materialization_engine().list_tasks(
            object_id=object_id,
            materialization_type=materialization_type,
            status=status,
        ),
    }


@router.put("/materialization-tasks/{task_id}")
def update_materialization_task(
    task_id: str,
    updates: dict[str, Any],
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_materialization_engine().update_task(task_id, **updates)
    except MaterializationEngineError as err:
        raise _map_materialization_error(err) from err


@router.delete("/materialization-tasks/{task_id}")
def delete_materialization_task(
    task_id: str, _principal: Principal = Depends(require_principal),
):
    ok = get_materialization_engine().delete_task(task_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"任务 {task_id} 不存在", status_code=404)
    return {"deleted": True, "id": task_id}


@router.post("/materialization-tasks/{task_id}/run")
def run_materialization(
    task_id: str, _principal: Principal = Depends(require_principal),
):
    try:
        return get_materialization_engine().run_materialization(task_id)
    except MaterializationEngineError as err:
        raise _map_materialization_error(err) from err


# ════════════════════ Row Level API ════════════════════

@router.post("/row-level-policies")
def create_row_level_policy(
    req: CreateRowLevelPolicyRequest, _principal: Principal = Depends(require_principal),
):
    try:
        return get_row_level_engine().create_policy(
            view_id=req.view_id,
            name=req.name,
            policy_type=req.policy_type,
            condition_expression=req.condition_expression,
            status=req.status,
            description=req.description,
        )
    except RowLevelEngineError as err:
        raise _map_row_level_error(err) from err


@router.get("/row-level-policies/{policy_id}")
def get_row_level_policy(
    policy_id: str, _principal: Principal = Depends(require_principal),
):
    try:
        return get_row_level_engine().get_policy(policy_id)
    except RowLevelEngineError as err:
        raise _map_row_level_error(err) from err


@router.get("/row-level-policies")
def list_row_level_policies(
    view_id: str | None = None,
    policy_type: str | None = None,
    status: str | None = None,
    _principal: Principal = Depends(require_principal),
):
    return {
        "items": get_row_level_engine().list_policies(
            view_id=view_id,
            policy_type=policy_type,
            status=status,
        ),
    }


@router.put("/row-level-policies/{policy_id}")
def update_row_level_policy(
    policy_id: str,
    updates: dict[str, Any],
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_row_level_engine().update_policy(policy_id, **updates)
    except RowLevelEngineError as err:
        raise _map_row_level_error(err) from err


@router.delete("/row-level-policies/{policy_id}")
def delete_row_level_policy(
    policy_id: str, _principal: Principal = Depends(require_principal),
):
    ok = get_row_level_engine().delete_policy(policy_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"策略 {policy_id} 不存在", status_code=404)
    return {"deleted": True, "id": policy_id}


@router.post("/row-level-policies/{policy_id}/evaluate")
def evaluate_row_level_policy(
    policy_id: str,
    req: RowLevelEvaluateRequest,
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_row_level_engine().evaluate(policy_id, req.user_id)
    except RowLevelEngineError as err:
        raise _map_row_level_error(err) from err


@router.post("/row-level-policies/evaluate-all")
def evaluate_all_row_level_policies(
    view_id: str,
    req: RowLevelEvaluateRequest,
    _principal: Principal = Depends(require_principal),
):
    return {"items": get_row_level_engine().evaluate_all(view_id, req.user_id)}


# ════════════════════ Column Level API ════════════════════

@router.post("/column-level-policies")
def create_column_level_policy(
    req: CreateColumnLevelPolicyRequest, _principal: Principal = Depends(require_principal),
):
    try:
        return get_column_level_engine().create_policy(
            mdo_id=req.mdo_id,
            name=req.name,
            policy_type=req.policy_type,
            columns=req.columns,
            status=req.status,
            description=req.description,
            max_sources=req.max_sources,
        )
    except ColumnLevelEngineError as err:
        raise _map_column_level_error(err) from err


@router.get("/column-level-policies/{policy_id}")
def get_column_level_policy(
    policy_id: str, _principal: Principal = Depends(require_principal),
):
    try:
        return get_column_level_engine().get_policy(policy_id)
    except ColumnLevelEngineError as err:
        raise _map_column_level_error(err) from err


@router.get("/column-level-policies")
def list_column_level_policies(
    mdo_id: str | None = None,
    policy_type: str | None = None,
    status: str | None = None,
    _principal: Principal = Depends(require_principal),
):
    return {
        "items": get_column_level_engine().list_policies(
            mdo_id=mdo_id,
            policy_type=policy_type,
            status=status,
        ),
    }


@router.put("/column-level-policies/{policy_id}")
def update_column_level_policy(
    policy_id: str,
    updates: dict[str, Any],
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_column_level_engine().update_policy(policy_id, **updates)
    except ColumnLevelEngineError as err:
        raise _map_column_level_error(err) from err


@router.delete("/column-level-policies/{policy_id}")
def delete_column_level_policy(
    policy_id: str, _principal: Principal = Depends(require_principal),
):
    ok = get_column_level_engine().delete_policy(policy_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"策略 {policy_id} 不存在", status_code=404)
    return {"deleted": True, "id": policy_id}


@router.post("/column-level-policies/{policy_id}/evaluate")
def evaluate_column_level_policy(
    policy_id: str,
    req: ColumnLevelEvaluateRequest,
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_column_level_engine().evaluate(policy_id, req.user_id)
    except ColumnLevelEngineError as err:
        raise _map_column_level_error(err) from err


# ════════════════════ Agent Tools API ════════════════════

@router.post("/agent-tools")
def create_agent_tool(
    req: CreateAgentToolRequest, _principal: Principal = Depends(require_principal),
):
    try:
        return get_agent_tools_engine().create_tool(
            name=req.name,
            tool_type=req.tool_type,
            description=req.description,
            schema=req.schema,
            status=req.status,
        )
    except AgentToolsEngineError as err:
        raise _map_agent_tools_error(err) from err


@router.get("/agent-tools/{tool_id}")
def get_agent_tool(
    tool_id: str, _principal: Principal = Depends(require_principal),
):
    try:
        return get_agent_tools_engine().get_tool(tool_id)
    except AgentToolsEngineError as err:
        raise _map_agent_tools_error(err) from err


@router.get("/agent-tools")
def list_agent_tools(
    tool_type: str | None = None,
    status: str | None = None,
    _principal: Principal = Depends(require_principal),
):
    return {
        "items": get_agent_tools_engine().list_tools(
            tool_type=tool_type,
            status=status,
        ),
    }


@router.put("/agent-tools/{tool_id}")
def update_agent_tool(
    tool_id: str,
    updates: dict[str, Any],
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_agent_tools_engine().update_tool(tool_id, **updates)
    except AgentToolsEngineError as err:
        raise _map_agent_tools_error(err) from err


@router.delete("/agent-tools/{tool_id}")
def delete_agent_tool(
    tool_id: str, _principal: Principal = Depends(require_principal),
):
    ok = get_agent_tools_engine().delete_tool(tool_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"工具 {tool_id} 不存在", status_code=404)
    return {"deleted": True, "id": tool_id}


@router.post("/agent-tools/{tool_id}/execute")
def execute_agent_tool(
    tool_id: str,
    req: ExecuteToolRequest,
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_agent_tools_engine().execute_tool(
            tool_id=tool_id,
            executed_by=req.executed_by,
            params=req.params,
        )
    except AgentToolsEngineError as err:
        raise _map_agent_tools_error(err) from err


@router.get("/agent-tools/types")
def get_agent_tool_types(_principal: Principal = Depends(require_principal)):
    return {"types": get_agent_tools_engine().get_tool_types()}