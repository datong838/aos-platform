"""W2-#14/#15 · Action 规则 + 函数规则 API 路由。

详见 docs/palantier/20_tech/220tech_w2-c-ontology-manager.md §2.3/§2.4。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.action_rules import (
    ActionRule,
    ActionRuleError,
    FunctionRule,
    get_function_rule_store,
    get_rule_store,
)
from aos_api.errors import ApiError

router = APIRouter(tags=["action-rules"])


def _map_error(err: ActionRuleError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


class CreateRuleRequest(BaseModel):
    name: str
    action_type_id: str
    kind: str
    condition: str = ""
    target_otd_id: str = ""
    enabled: bool = True
    priority: int = 0


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    condition: str | None = None
    target_otd_id: str | None = None
    enabled: bool | None = None
    priority: int | None = None


class EvaluateRuleRequest(BaseModel):
    context: dict[str, Any]


class CreateFunctionRuleRequest(BaseModel):
    name: str
    action_type_id: str
    function_id: str
    trigger: str = "before"
    condition: str = ""
    enabled: bool = True


class ExecuteFunctionRuleRequest(BaseModel):
    payload: Any = None


# ---------- Action 规则 (#14) ----------


@router.get("/v1/action-rules")
def list_rules(action_type_id: str | None = None):
    store = get_rule_store()
    rules = store.list_by_action(action_type_id) if action_type_id else store.list_all()
    return {"items": [r.model_dump() for r in rules]}


@router.post("/v1/action-rules")
def create_rule(req: CreateRuleRequest):
    rule = ActionRule(
        name=req.name,
        action_type_id=req.action_type_id,
        kind=req.kind,  # type: ignore[arg-type]
        condition=req.condition,
        target_otd_id=req.target_otd_id,
        enabled=req.enabled,
        priority=req.priority,
    )
    try:
        created = get_rule_store().create(rule)
    except ActionRuleError as err:
        raise _map_error(err) from err
    return created.model_dump()


@router.get("/v1/action-rules/{rule_id}")
def get_rule(rule_id: str):
    rule = get_rule_store().get(rule_id)
    if rule is None:
        raise ApiError(code="NOT_FOUND", message=f"规则 {rule_id} 不存在", status_code=404)
    return rule.model_dump()


@router.put("/v1/action-rules/{rule_id}")
def update_rule(rule_id: str, req: UpdateRuleRequest):
    fields: dict[str, Any] = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        rule = get_rule_store().update(rule_id, **fields)
    except ActionRuleError as err:
        raise _map_error(err) from err
    return rule.model_dump()


@router.post("/v1/action-rules/{rule_id}/evaluate")
def evaluate_rule(rule_id: str, req: EvaluateRuleRequest):
    try:
        result = get_rule_store().evaluate(rule_id, req.context)
    except ActionRuleError as err:
        raise _map_error(err) from err
    return {"rule_id": rule_id, "passed": result}


@router.delete("/v1/action-rules/{rule_id}")
def delete_rule(rule_id: str):
    ok = get_rule_store().delete(rule_id)
    return {"rule_id": rule_id, "deleted": ok}


# ---------- 函数规则 (#15) ----------


@router.get("/v1/action-function-rules")
def list_function_rules(action_type_id: str | None = None):
    store = get_function_rule_store()
    rules = store.list_by_action(action_type_id) if action_type_id else store.list_all()
    return {"items": [r.model_dump() for r in rules]}


@router.post("/v1/action-function-rules")
def create_function_rule(req: CreateFunctionRuleRequest):
    rule = FunctionRule(
        name=req.name,
        action_type_id=req.action_type_id,
        function_id=req.function_id,
        trigger=req.trigger,  # type: ignore[arg-type]
        condition=req.condition,
        enabled=req.enabled,
    )
    try:
        created = get_function_rule_store().create(rule)
    except ActionRuleError as err:
        raise _map_error(err) from err
    return created.model_dump()


@router.get("/v1/action-function-rules/{rule_id}")
def get_function_rule(rule_id: str):
    rule = get_function_rule_store().get(rule_id)
    if rule is None:
        raise ApiError(code="NOT_FOUND", message=f"函数规则 {rule_id} 不存在", status_code=404)
    return rule.model_dump()


@router.post("/v1/action-function-rules/{rule_id}/execute")
def execute_function_rule(rule_id: str, req: ExecuteFunctionRuleRequest):
    try:
        result = get_function_rule_store().execute(rule_id, req.payload)
    except ActionRuleError as err:
        raise _map_error(err) from err
    return {"rule_id": rule_id, "result": result}


@router.delete("/v1/action-function-rules/{rule_id}")
def delete_function_rule(rule_id: str):
    ok = get_function_rule_store().delete(rule_id)
    return {"rule_id": rule_id, "deleted": ok}
