"""LLM Node + Agent Proxy + Dynamic Scheduling API 路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.llm_node_agent_proxy import (
    AgentProxy,
    AgentProxyEngine,
    AgentProxyError,
    DynamicSchedulingEngine,
    LlmNode,
    LlmNodeEngine,
    LlmNodeError,
    SchedulingScenario,
    SchedulingScenarioError,
    get_agent_proxy_engine,
    get_dynamic_scheduling_engine,
    get_llm_node_engine,
)

router = APIRouter(prefix="/llm-node-agent-proxy", tags=["llm-node-agent-proxy"])


def _map_llm_node_error(err: LlmNodeError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_agent_proxy_error(err: AgentProxyError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_scenario_error(err: SchedulingScenarioError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


# ────────────────────────────────────────────────────────────────
# LLM Node 路由
# ────────────────────────────────────────────────────────────────

class CreateNodeRequest(BaseModel):
    name: str
    node_type: str
    prompt_template: str = ""
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ExecuteNodeRequest(BaseModel):
    input_data: dict[str, Any] = Field(default_factory=dict)


@router.post("/v1/nodes")
def create_node(
    req: CreateNodeRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        node = get_llm_node_engine().create_node(
            name=req.name,
            node_type=req.node_type,
            prompt_template=req.prompt_template,
            model_name=req.model_name,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            input_schema=req.input_schema,
            output_schema=req.output_schema,
            enabled=req.enabled,
        )
        return {"item": node.model_dump()}
    except LlmNodeError as err:
        raise _map_llm_node_error(err) from err


@router.get("/v1/nodes")
def list_nodes(
    node_type: str | None = None,
    enabled: bool | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    items = get_llm_node_engine().list_nodes(node_type=node_type, enabled=enabled)
    return {"items": [n.model_dump() for n in items], "count": len(items)}


@router.get("/v1/nodes/{node_id}")
def get_node(
    node_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        node = get_llm_node_engine().get_node(node_id)
        return {"item": node.model_dump()}
    except LlmNodeError as err:
        raise _map_llm_node_error(err) from err


@router.put("/v1/nodes/{node_id}")
def update_node(
    node_id: str,
    req: CreateNodeRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        node = get_llm_node_engine().update_node(
            node_id,
            name=req.name,
            node_type=req.node_type,
            prompt_template=req.prompt_template,
            model_name=req.model_name,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            input_schema=req.input_schema,
            output_schema=req.output_schema,
            enabled=req.enabled,
        )
        return {"item": node.model_dump()}
    except LlmNodeError as err:
        raise _map_llm_node_error(err) from err


@router.delete("/v1/nodes/{node_id}")
def delete_node(
    node_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    ok = get_llm_node_engine().delete_node(node_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"节点 {node_id} 不存在", status_code=404)
    return {"id": node_id, "deleted": True}


@router.post("/v1/nodes/{node_id}/execute")
def execute_node(
    node_id: str,
    req: ExecuteNodeRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        return get_llm_node_engine().execute_node(node_id, req.input_data)
    except LlmNodeError as err:
        raise _map_llm_node_error(err) from err


# ────────────────────────────────────────────────────────────────
# Agent Proxy 路由
# ────────────────────────────────────────────────────────────────

class CreateProxyRequest(BaseModel):
    name: str
    proxy_type: str
    target_url: str
    listen_port: int
    enabled: bool = True


@router.post("/v1/proxies")
def create_proxy(
    req: CreateProxyRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        proxy = get_agent_proxy_engine().create_proxy(
            name=req.name,
            proxy_type=req.proxy_type,
            target_url=req.target_url,
            listen_port=req.listen_port,
            enabled=req.enabled,
        )
        return {"item": proxy.model_dump()}
    except AgentProxyError as err:
        raise _map_agent_proxy_error(err) from err


@router.get("/v1/proxies")
def list_proxies(
    proxy_type: str | None = None,
    health_status: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    items = get_agent_proxy_engine().list_proxies(proxy_type=proxy_type, health_status=health_status)
    return {"items": [p.model_dump() for p in items], "count": len(items)}


@router.get("/v1/proxies/{proxy_id}")
def get_proxy(
    proxy_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        proxy = get_agent_proxy_engine().get_proxy(proxy_id)
        return {"item": proxy.model_dump()}
    except AgentProxyError as err:
        raise _map_agent_proxy_error(err) from err


@router.put("/v1/proxies/{proxy_id}")
def update_proxy(
    proxy_id: str,
    req: CreateProxyRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        proxy = get_agent_proxy_engine().update_proxy(
            proxy_id,
            name=req.name,
            proxy_type=req.proxy_type,
            target_url=req.target_url,
            listen_port=req.listen_port,
            enabled=req.enabled,
        )
        return {"item": proxy.model_dump()}
    except AgentProxyError as err:
        raise _map_agent_proxy_error(err) from err


@router.delete("/v1/proxies/{proxy_id}")
def delete_proxy(
    proxy_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    ok = get_agent_proxy_engine().delete_proxy(proxy_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"代理 {proxy_id} 不存在", status_code=404)
    return {"id": proxy_id, "deleted": True}


@router.post("/v1/proxies/{proxy_id}/toggle")
def toggle_proxy(
    proxy_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        proxy = get_agent_proxy_engine().toggle_proxy(proxy_id)
        return {"item": proxy.model_dump()}
    except AgentProxyError as err:
        raise _map_agent_proxy_error(err) from err


@router.post("/v1/proxies/{proxy_id}/health-check")
def health_check_proxy(
    proxy_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        proxy = get_agent_proxy_engine().health_check(proxy_id)
        return {"item": proxy.model_dump()}
    except AgentProxyError as err:
        raise _map_agent_proxy_error(err) from err


# ────────────────────────────────────────────────────────────────
# Dynamic Scheduling 路由
# ────────────────────────────────────────────────────────────────

class CreateScenarioRequest(BaseModel):
    name: str
    scenario_type: str
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    suggestion_rules: list[dict[str, Any]] = Field(default_factory=list)
    search_rules: list[dict[str, Any]] = Field(default_factory=list)
    realtime_evaluation: bool = False
    enabled: bool = True


@router.post("/v1/scenarios")
def create_scenario(
    req: CreateScenarioRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        scenario = get_dynamic_scheduling_engine().create_scenario(
            name=req.name,
            scenario_type=req.scenario_type,
            constraints=req.constraints,
            suggestion_rules=req.suggestion_rules,
            search_rules=req.search_rules,
            realtime_evaluation=req.realtime_evaluation,
            enabled=req.enabled,
        )
        return {"item": scenario.model_dump()}
    except SchedulingScenarioError as err:
        raise _map_scenario_error(err) from err


@router.get("/v1/scenarios")
def list_scenarios(
    scenario_type: str | None = None,
    enabled: bool | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    items = get_dynamic_scheduling_engine().list_scenarios(scenario_type=scenario_type, enabled=enabled)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/scenarios/{scenario_id}")
def get_scenario(
    scenario_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        scenario = get_dynamic_scheduling_engine().get_scenario(scenario_id)
        return {"item": scenario.model_dump()}
    except SchedulingScenarioError as err:
        raise _map_scenario_error(err) from err


@router.put("/v1/scenarios/{scenario_id}")
def update_scenario(
    scenario_id: str,
    req: CreateScenarioRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        scenario = get_dynamic_scheduling_engine().update_scenario(
            scenario_id,
            name=req.name,
            scenario_type=req.scenario_type,
            constraints=req.constraints,
            suggestion_rules=req.suggestion_rules,
            search_rules=req.search_rules,
            realtime_evaluation=req.realtime_evaluation,
            enabled=req.enabled,
        )
        return {"item": scenario.model_dump()}
    except SchedulingScenarioError as err:
        raise _map_scenario_error(err) from err


@router.delete("/v1/scenarios/{scenario_id}")
def delete_scenario(
    scenario_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    ok = get_dynamic_scheduling_engine().delete_scenario(scenario_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"场景 {scenario_id} 不存在", status_code=404)
    return {"id": scenario_id, "deleted": True}


@router.post("/v1/scenarios/{scenario_id}/evaluation")
def run_evaluation(
    scenario_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        return get_dynamic_scheduling_engine().run_evaluation(scenario_id)
    except SchedulingScenarioError as err:
        raise _map_scenario_error(err) from err


@router.post("/v1/scenarios/{scenario_id}/apply")
def apply_scenario(
    scenario_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        return get_dynamic_scheduling_engine().apply_scenario(scenario_id)
    except SchedulingScenarioError as err:
        raise _map_scenario_error(err) from err