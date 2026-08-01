"""Phase B · 222plan — Model Router Config REST API.

Endpoints:
  GET    /api/models/router                 — list all route rules (V2)
  GET    /api/models/router/{route_id}      — get single route rule
  POST   /api/models/router                 — create new route rule
  PUT    /api/models/router/{route_id}      — update route rule
  DELETE /api/models/router/{route_id}      — delete route rule
  POST   /api/models/router/{route_id}/test — simulate routing decision
  GET    /api/models/router/circuit-config  — get global circuit config
  PUT    /api/models/router/circuit-config  — update global circuit config
  GET    /api/models/router/strategies      — list available strategies
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aos_api.logging_facade import get_logger
from aos_api.model_router_config import (
    get_router_config_v2,
    get_route_rules_v2,
    get_route_rule_v2,
    create_route_rule_v2,
    update_route_rule_v2,
    delete_route_rule_v2,
    test_route,
    get_global_circuit_config,
    update_global_circuit_config,
    replace_router_config_v2,
    RouterConfigVersionConflict,
    STRATEGIES,
)

log = get_logger("aos-api.router_config")

router = APIRouter(prefix="/api/models/router", tags=["model-router"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class WeightItem(BaseModel):
    model: str
    pct: int = Field(ge=0, le=100)


class RouteRuleUpdate(BaseModel):
    task: str | None = None
    primary: str | None = None
    fallback: str | None = None
    egress: str | None = None
    span: bool | None = None
    enabled: bool | None = None
    strategy: str | None = None
    weights: list[WeightItem] | None = None
    fallback_chain: list[str] | None = None
    circuit_config: dict[str, Any] | None = None


class RouteRuleCreate(RouteRuleUpdate):
    id: str
    task: str = ""


class RouterConfigReplace(BaseModel):
    items: list[RouteRuleCreate]
    expectedVersion: int = Field(ge=1)


class CircuitConfigUpdate(BaseModel):
    error_rate_threshold_pct: int | None = Field(default=None, ge=1, le=50)
    latency_p99_ms: int | None = Field(default=None, ge=100, le=30000)
    cooldown_seconds: int | None = Field(default=None, ge=5, le=600)
    half_open_probes: int | None = Field(default=None, ge=1, le=20)
    failure_threshold: int | None = Field(default=None, ge=1, le=100)
    success_threshold: int | None = Field(default=None, ge=1, le=20)


class RouteTestRequest(BaseModel):
    prompt: str = ""
    context_length: int = 0
    configVersion: int | None = Field(default=None, ge=1)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def list_routes():
    """List all route rules (V2 format)."""
    return get_router_config_v2()


@router.put("")
def replace_routes(body: RouterConfigReplace):
    """Replace all route rules using the caller's confirmed version."""
    try:
        items = [row.model_dump(exclude_none=True) for row in body.items]
        return replace_router_config_v2(items, body.expectedVersion)
    except RouterConfigVersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/strategies")
def list_strategies():
    """List available routing strategies."""
    return {"strategies": STRATEGIES}


@router.get("/circuit-config")
def get_circuit_config():
    """Get global circuit breaker config."""
    return get_global_circuit_config()


@router.put("/circuit-config")
def put_circuit_config(body: CircuitConfigUpdate):
    """Update global circuit breaker config."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    return update_global_circuit_config(updates)


@router.get("/{route_id}")
def get_route(route_id: str):
    """Get a single route rule by ID."""
    rule = get_route_rule_v2(route_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Route not found: {route_id}")
    return rule


@router.post("")
def create_route(body: RouteRuleCreate):
    """Create a new route rule."""
    try:
        data = body.model_dump(exclude_none=True)
        return create_route_rule_v2(data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/{route_id}")
def update_route(route_id: str, body: RouteRuleUpdate):
    """Update a route rule."""
    try:
        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        return update_route_rule_v2(route_id, updates)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{route_id}")
def delete_route(route_id: str):
    """Delete a route rule."""
    deleted = delete_route_rule_v2(route_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Route not found: {route_id}")
    return {"deleted": True, "id": route_id}


@router.post("/{route_id}/test")
def run_route_test(route_id: str, body: RouteTestRequest):
    """Simulate a routing decision for the given route."""
    try:
        return test_route(route_id, body.prompt, body.context_length, body.configVersion)
    except RouterConfigVersionConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
