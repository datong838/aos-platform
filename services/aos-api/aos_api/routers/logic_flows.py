"""W2-AF · 逻辑流与 Data Connection Agent 组路由：#111 LogicFlow + #112 AgentProxy + #113 AgentWorker."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.logic_flows import (
    AgentProxy,
    AgentWorker,
    FlowStep,
    LogicFlow,
    LogicFlowsError,
    WorkerJob,
    get_flow_engine,
    get_proxy_engine,
    get_worker_engine,
)

router = APIRouter(tags=["logic-flows"])
log = get_logger("aos-api.logic-flows")


def _map_err(err: LogicFlowsError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #111 LogicFlow ════════════════════

class FlowStepIn(BaseModel):
    kind: str = Field(min_length=1)
    name: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    next_step_id: str = ""


class LogicFlowIn(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    steps: list[FlowStepIn] = Field(default_factory=list)


class LogicFlowUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[FlowStepIn] | None = None
    status: str | None = None


@router.post("/v1/logic-flows")
def register_flow(
    body: LogicFlowIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#111 · 注册逻辑流。"""
    _ = principal
    try:
        steps = [FlowStep(**s.model_dump()) for s in body.steps]
        f = get_flow_engine().register(LogicFlow(
            name=body.name, description=body.description, steps=steps,
        ))
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": f.model_dump()}


@router.get("/v1/logic-flows")
def list_flows(
    status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#111 · 逻辑流列表。"""
    _ = principal
    items = get_flow_engine().list(status=status)
    return {"items": [f.model_dump() for f in items], "count": len(items)}


@router.get("/v1/logic-flows/{flow_id}")
def get_flow(
    flow_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#111 · 单条逻辑流。"""
    _ = principal
    try:
        return {"item": get_flow_engine().get(flow_id).model_dump()}
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/logic-flows/{flow_id}")
def update_flow(
    flow_id: str, body: LogicFlowUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#111 · 更新逻辑流。"""
    _ = principal
    updates: dict[str, Any] = {}
    for k, v in body.model_dump().items():
        if v is None:
            continue
        if k == "steps":
            updates[k] = [FlowStep(**s.model_dump()) for s in v]
        else:
            updates[k] = v
    try:
        f = get_flow_engine().update(flow_id, updates)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": f.model_dump()}


@router.delete("/v1/logic-flows/{flow_id}")
def delete_flow(
    flow_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#111 · 删除逻辑流。"""
    _ = principal
    ok = get_flow_engine().delete(flow_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"逻辑流 {flow_id} 不存在", status_code=404)
    return {"id": flow_id, "deleted": True}


@router.post("/v1/logic-flows/{flow_id}/execute")
def execute_flow(
    flow_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#111 · 执行逻辑流。"""
    _ = principal
    try:
        exec_ = get_flow_engine().execute(flow_id)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": exec_.model_dump()}


@router.get("/v1/logic-flows/executions")
def list_executions(
    flow_id: str | None = None, limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#111 · 执行列表。"""
    _ = principal
    items = get_flow_engine().list_executions(flow_id=flow_id, limit=limit)
    return {"items": [e.model_dump() for e in items], "count": len(items)}


# ════════════════════ #112 AgentProxy ════════════════════

class AgentProxyIn(BaseModel):
    name: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    proxy_url: str = Field(min_length=1)
    auth_token: str = ""
    status: str = "offline"


class AgentProxyUpdateIn(BaseModel):
    name: str | None = None
    proxy_url: str | None = None
    auth_token: str | None = None
    status: str | None = None


class ForwardRequestIn(BaseModel):
    request: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/agent-proxies")
def register_proxy(
    body: AgentProxyIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#112 · 注册代理。"""
    _ = principal
    try:
        p = get_proxy_engine().register(AgentProxy(**body.model_dump()))
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.get("/v1/agent-proxies")
def list_proxies(
    status: str | None = None, agent_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#112 · 代理列表。"""
    _ = principal
    items = get_proxy_engine().list(status=status, agent_id=agent_id)
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.get("/v1/agent-proxies/{proxy_id}")
def get_proxy(
    proxy_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#112 · 单条代理。"""
    _ = principal
    try:
        return {"item": get_proxy_engine().get(proxy_id).model_dump()}
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/agent-proxies/{proxy_id}")
def update_proxy(
    proxy_id: str, body: AgentProxyUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#112 · 更新代理。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        p = get_proxy_engine().update(proxy_id, updates)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.delete("/v1/agent-proxies/{proxy_id}")
def delete_proxy(
    proxy_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#112 · 删除代理。"""
    _ = principal
    ok = get_proxy_engine().delete(proxy_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"代理 {proxy_id} 不存在", status_code=404)
    return {"id": proxy_id, "deleted": True}


@router.post("/v1/agent-proxies/{proxy_id}/heartbeat")
def heartbeat_proxy(
    proxy_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#112 · 代理心跳。"""
    _ = principal
    try:
        p = get_proxy_engine().heartbeat(proxy_id)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.post("/v1/agent-proxies/{proxy_id}/drain")
def drain_proxy(
    proxy_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#112 · 代理排空。"""
    _ = principal
    try:
        p = get_proxy_engine().drain(proxy_id)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": p.model_dump()}


@router.post("/v1/agent-proxies/{proxy_id}/forward")
def forward_request(
    proxy_id: str, body: ForwardRequestIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#112 · 代理转发请求。"""
    _ = principal
    try:
        result = get_proxy_engine().forward_request(proxy_id, body.request)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"result": result}


# ════════════════════ #113 AgentWorker ════════════════════

class AgentWorkerIn(BaseModel):
    agent_id: str = Field(min_length=1)
    host: str = Field(min_length=1)
    version: str = "1.0.0"
    status: str = "registered"
    capabilities: list[str] = Field(default_factory=list)


class AgentWorkerUpdateIn(BaseModel):
    version: str | None = None
    status: str | None = None
    capabilities: list[str] | None = None


class AssignJobIn(BaseModel):
    capability: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class CompleteJobIn(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/agent-workers")
def register_worker(
    body: AgentWorkerIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#113 · 注册 Worker。"""
    _ = principal
    try:
        w = get_worker_engine().register(AgentWorker(**body.model_dump()))
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": w.model_dump()}


@router.get("/v1/agent-workers")
def list_workers(
    status: str | None = None, agent_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#113 · Worker 列表。"""
    _ = principal
    items = get_worker_engine().list(status=status, agent_id=agent_id)
    return {"items": [w.model_dump() for w in items], "count": len(items)}


@router.get("/v1/agent-workers/{worker_id}")
def get_worker(
    worker_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#113 · 单条 Worker。"""
    _ = principal
    try:
        return {"item": get_worker_engine().get(worker_id).model_dump()}
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/agent-workers/{worker_id}")
def update_worker(
    worker_id: str, body: AgentWorkerUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#113 · 更新 Worker。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        w = get_worker_engine().update(worker_id, updates)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": w.model_dump()}


@router.delete("/v1/agent-workers/{worker_id}")
def delete_worker(
    worker_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#113 · 删除 Worker。"""
    _ = principal
    ok = get_worker_engine().delete(worker_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"Worker {worker_id} 不存在", status_code=404)
    return {"id": worker_id, "deleted": True}


@router.post("/v1/agent-workers/{worker_id}/heartbeat")
def heartbeat_worker(
    worker_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#113 · Worker 心跳。"""
    _ = principal
    try:
        w = get_worker_engine().heartbeat(worker_id)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": w.model_dump()}


@router.post("/v1/agent-workers/{worker_id}/jobs")
def assign_job(
    worker_id: str, body: AssignJobIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#113 · 分配任务。"""
    _ = principal
    try:
        job = get_worker_engine().assign_job(worker_id, body.capability, body.payload)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": job.model_dump()}


@router.post("/v1/agent-workers/jobs/{job_id}/complete")
def complete_job(
    job_id: str, body: CompleteJobIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#113 · 完成任务。"""
    _ = principal
    try:
        job = get_worker_engine().complete_job(job_id, body.result)
    except LogicFlowsError as exc:
        raise _map_err(exc) from exc
    return {"item": job.model_dump()}


@router.get("/v1/agent-workers/jobs")
def list_jobs(
    worker_id: str | None = None, status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#113 · 任务列表。"""
    _ = principal
    items = get_worker_engine().list_jobs(worker_id=worker_id, status=status)
    return {"items": [j.model_dump() for j in items], "count": len(items)}
