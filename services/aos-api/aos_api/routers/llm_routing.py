"""W2-T · k-LLM 路由编排组路由：#71 智能路由 + #72 场景化路由 + #73 熔断/热切换."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.llm_routing import (
    BlockRoute,
    CallRecord,
    CircuitConfig,
    CircuitState,
    LLMRoutingFacade,
    ModelCandidate,
    RouteRule,
    RoutingError,
    RoutingRequest,
    ScenarioRouter,
    SmartRouter,
    get_failover_engine,
    get_llm_routing_facade,
    get_scenario_router,
    get_smart_router,
)
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["llm-routing"])
log = get_logger("aos-api.llm-routing")


def _map_routing_error(err: RoutingError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    elif err.code in {
        "PRIMARY_FAILED_NO_FALLBACK",
        "FALLBACK_OPEN",
        "ALL_FAILED",
        "NO_PRIMARY",
    }:
        status = 503
    elif err.code == "NO_CANDIDATE":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #71 智能路由 ════════════════════

class ModelCandidateIn(BaseModel):
    id: str = Field(min_length=1)
    tier: str = "mid"
    max_context: int = 8192
    modalities: list[str] = Field(default_factory=lambda: ["text"])
    cost_per_1k: float = 0.0
    egress: str = "allow"
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class RoutingRequestIn(BaseModel):
    query: str = ""
    context_length: int = 0
    complexity: int = 1
    tools_required: list[str] = Field(default_factory=list)
    security_label: str = "internal"
    cost_budget: float | None = None
    preferred_modalities: list[str] = Field(default_factory=lambda: ["text"])
    prefer_tags: list[str] = Field(default_factory=list)


@router.get("/v1/aip/smart-router/candidates")
def list_candidates(
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#71 · 列出智能路由候选模型。"""
    _ = principal
    items = get_smart_router().list(enabled_only=enabled_only)
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.post("/v1/aip/smart-router/candidates")
def register_candidate(
    body: ModelCandidateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#71 · 注册候选模型。"""
    _ = principal
    c = get_smart_router().register(
        ModelCandidate(**body.model_dump()),
    )
    return {"item": c.model_dump()}


@router.delete("/v1/aip/smart-router/candidates/{model_id}")
def unregister_candidate(
    model_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#71 · 注销候选模型。"""
    _ = principal
    ok = get_smart_router().unregister(model_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"候选 {model_id} 不存在", status_code=404)
    return {"id": model_id, "deleted": True}


@router.post("/v1/aip/smart-router/choose")
def choose_model(
    body: RoutingRequestIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#71 · 评分选模（不调用底层网关）。"""
    _ = principal
    try:
        return get_smart_router().choose(RoutingRequest(**body.model_dump()))
    except RoutingError as exc:
        raise _map_routing_error(exc) from exc


@router.post("/v1/aip/smart-router/route-and-call")
def smart_route_and_call(
    body: RoutingRequestIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#71 · 选模并调用底层网关（端到端）。"""
    _ = principal
    try:
        return get_llm_routing_facade().smart_route_and_call(
            RoutingRequest(**body.model_dump()),
        )
    except RoutingError as exc:
        raise _map_routing_error(exc) from exc


# ════════════════════ #72 场景化路由 ════════════════════

class RouteRuleIn(BaseModel):
    id: str = Field(min_length=1)
    task: str
    task_type: str
    primary: str = "—"
    fallback: str = ""
    egress: str = "继承"
    span: bool = False
    enabled: bool = True


class BlockRouteIn(BaseModel):
    block_id: str = Field(min_length=1)
    logic_id: str = ""
    model_id: str = Field(min_length=1)
    task_type: str = ""
    inherit: bool = False


class ResolveIn(BaseModel):
    task_type: str
    block_id: str | None = None


class ScenarioRouteCallIn(BaseModel):
    task_type: str
    query: str
    block_id: str | None = None


class ImportRulesIn(BaseModel):
    items: list[dict[str, Any]]


@router.get("/v1/aip/scenario-router/rules")
def list_rules(
    task_type: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 列出场景化路由规则。"""
    _ = principal
    items = get_scenario_router().list_rules(task_type=task_type)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.get("/v1/aip/scenario-router/rules/{rule_id}")
def get_rule(
    rule_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 单条路由规则。"""
    _ = principal
    try:
        return {"item": get_scenario_router().get_rule(rule_id).model_dump()}
    except RoutingError as exc:
        raise _map_routing_error(exc) from exc


@router.post("/v1/aip/scenario-router/rules")
def upsert_rule(
    body: RouteRuleIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 新增/更新路由规则。"""
    _ = principal
    try:
        r = get_scenario_router().upsert_rule(RouteRule(**body.model_dump()))
    except RoutingError as exc:
        raise _map_routing_error(exc) from exc
    return {"item": r.model_dump()}


@router.delete("/v1/aip/scenario-router/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 删除路由规则。"""
    _ = principal
    ok = get_scenario_router().delete_rule(rule_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"规则 {rule_id} 不存在", status_code=404)
    return {"id": rule_id, "deleted": True}


@router.post("/v1/aip/scenario-router/resolve")
def resolve_route(
    body: ResolveIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 解析任务类型 → primary/fallback。"""
    _ = principal
    return get_scenario_router().resolve(body.task_type, block_id=body.block_id)


@router.post("/v1/aip/scenario-router/rules/import")
def import_rules(
    body: ImportRulesIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 批量导入规则（与 81 §2.1 PUT /v1/aip/model-routes 对齐）。"""
    _ = principal
    try:
        imported = get_scenario_router().import_rules(body.items)
    except RoutingError as exc:
        raise _map_routing_error(exc) from exc
    return {"items": [r.model_dump() for r in imported], "count": len(imported)}


@router.get("/v1/aip/scenario-router/blocks")
def list_blocks(
    logic_id: str | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 列出块级路由绑定。"""
    _ = principal
    items = get_scenario_router().list_blocks(logic_id=logic_id)
    return {"items": [b.model_dump() for b in items], "count": len(items)}


@router.post("/v1/aip/scenario-router/blocks")
def upsert_block(
    body: BlockRouteIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 新增/更新块级路由绑定。"""
    _ = principal
    b = get_scenario_router().upsert_block(BlockRoute(**body.model_dump()))
    return {"item": b.model_dump()}


@router.delete("/v1/aip/scenario-router/blocks/{block_id}")
def delete_block(
    block_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 删除块级路由绑定。"""
    _ = principal
    ok = get_scenario_router().delete_block(block_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"块路由 {block_id} 不存在", status_code=404)
    return {"id": block_id, "deleted": True}


@router.post("/v1/aip/scenario-router/route-and-call")
def scenario_route_and_call(
    body: ScenarioRouteCallIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#72 · 场景路由并调用（端到端）。"""
    _ = principal
    try:
        return get_llm_routing_facade().scenario_route_and_call(
            body.task_type, body.query, block_id=body.block_id,
        )
    except RoutingError as exc:
        raise _map_routing_error(exc) from exc


# ════════════════════ #73 熔断/热切换 ════════════════════

class CircuitConfigIn(BaseModel):
    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    half_open_max_probes: int = 1
    success_threshold: int = 1


class FailoverCallIn(BaseModel):
    query: str
    primary: str
    fallback: str = ""
    route_source: str = "explicit"


class CircuitDrillIn(BaseModel):
    rules: list[dict[str, Any]] | None = None


@router.get("/v1/aip/failover/circuits")
def list_circuits(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#73 · 列出所有模型熔断状态。"""
    _ = principal
    items = get_failover_engine().list_states()
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/aip/failover/circuits/{model_id}")
def get_circuit(
    model_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#73 · 单模型熔断状态。"""
    _ = principal
    return {"item": get_failover_engine().get_state(model_id).model_dump()}


@router.post("/v1/aip/failover/circuits/{model_id}/reset")
def reset_circuit(
    model_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#73 · 强制重置熔断器为 closed。"""
    _ = principal
    st = get_failover_engine().reset(model_id)
    return {"item": st.model_dump()}


@router.put("/v1/aip/failover/circuits/{model_id}/config")
def set_circuit_config(
    model_id: str,
    body: CircuitConfigIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#73 · 更新模型熔断配置。"""
    _ = principal
    cfg = get_failover_engine().set_config(
        model_id, CircuitConfig(**body.model_dump()),
    )
    return {"item": cfg.model_dump()}


@router.post("/v1/aip/failover/call")
def failover_call(
    body: FailoverCallIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#73 · 主备热切换调用。"""
    _ = principal
    try:
        return get_failover_engine().call_with_failover(
            body.query, primary=body.primary,
            fallback=body.fallback, route_source=body.route_source,
        )
    except RoutingError as exc:
        raise _map_routing_error(exc) from exc


@router.get("/v1/aip/failover/call-records")
def list_call_records(
    model_id: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#73 · 最近调用记录。"""
    _ = principal
    items = get_failover_engine().list_records(model_id=model_id, limit=limit)
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.post("/v1/aip/failover/circuit-drill")
def circuit_drill(
    body: CircuitDrillIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#73 · 熔断演练（仅推演，不改生产路由，与 81 §2.1 对齐）."""
    _ = principal
    rules = body.rules or get_scenario_router().export_rules()
    down = next(
        (r for r in rules if r.get("id") == "provider_down" or r.get("span")),
        None,
    )
    target = (down or {}).get("primary") or "—"
    fallback = (down or {}).get("fallback") or ""
    # 检查当前 target 熔断状态
    state = get_failover_engine().get_state(target).state if target != "—" else "closed"
    return {
        "ok": True,
        "scenario": "primary_provider_unavailable",
        "degradedTo": target,
        "fallback": fallback,
        "circuitState": state,
        "message": f"演练通过 · 熔断后降级到 {target}"
        + (f"，回退到 {fallback}" if fallback and fallback != "—" else ""),
    }
