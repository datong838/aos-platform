"""Scheduling Rules & Lint API 路由."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.scheduling_rules_lint import (
    SchedulingRulesLintError,
    get_smart_func_engine,
    get_validation_engine,
    get_okf_lint_engine,
)

router = APIRouter(prefix="/scheduling-rules-lint", tags=["scheduling-rules-lint"])


def _map_error(err: SchedulingRulesLintError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class CreateSmartFunctionRequest(BaseModel):
    name: str
    function_type: str
    description: str = ""
    enabled: bool = True


class SmartFunctionSearchRequest(BaseModel):
    entity_id: str
    query: str


class CreateValidationRuleRequest(BaseModel):
    name: str
    rule_type: str
    constraint_expression: str
    description: str = ""
    severity: str = "warning"
    enabled: bool = True


class ValidateRequest(BaseModel):
    entity_id: str


class CreateLintRuleRequest(BaseModel):
    name: str
    rule_type: str
    severity: str = "warning"
    enabled: bool = True


class LintRequest(BaseModel):
    dataset_rid: str


# ════════════════════ Smart Functions API ════════════════════

@router.post("/smart-functions")
def create_smart_function(
    req: CreateSmartFunctionRequest, _principal: Principal = Depends(require_principal),
):
    try:
        return get_smart_func_engine().create_function(
            name=req.name,
            function_type=req.function_type,
            description=req.description,
            enabled=req.enabled,
        )
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.get("/smart-functions/{function_id}")
def get_smart_function(
    function_id: str, _principal: Principal = Depends(require_principal),
):
    try:
        return get_smart_func_engine().get_function(function_id)
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.get("/smart-functions")
def list_smart_functions(
    function_type: str | None = None,
    enabled: bool | None = None,
    _principal: Principal = Depends(require_principal),
):
    return {
        "items": get_smart_func_engine().list_functions(
            function_type=function_type,
            enabled=enabled,
        ),
    }


@router.put("/smart-functions/{function_id}")
def update_smart_function(
    function_id: str,
    updates: dict[str, Any],
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_smart_func_engine().update_function(function_id, **updates)
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.delete("/smart-functions/{function_id}")
def delete_smart_function(
    function_id: str, _principal: Principal = Depends(require_principal),
):
    ok = get_smart_func_engine().delete_function(function_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"函数 {function_id} 不存在", status_code=404)
    return {"deleted": True, "id": function_id}


@router.post("/smart-functions/{function_id}/suggest")
def suggest_entity(
    function_id: str,
    req: dict[str, str],
    _principal: Principal = Depends(require_principal),
):
    entity_id = req.get("entity_id", "")
    if not entity_id:
        raise ApiError(code="MISSING_ENTITY_ID", message="entity_id 必填", status_code=400)
    try:
        return get_smart_func_engine().suggest(entity_id, function_id)
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.post("/smart-functions/search")
def search_entities(
    req: SmartFunctionSearchRequest, _principal: Principal = Depends(require_principal),
):
    return {"items": get_smart_func_engine().search(req.entity_id, req.query)}


# ════════════════════ Validation Rules API ════════════════════

@router.post("/validation-rules")
def create_validation_rule(
    req: CreateValidationRuleRequest, _principal: Principal = Depends(require_principal),
):
    try:
        return get_validation_engine().create_rule(
            name=req.name,
            rule_type=req.rule_type,
            constraint_expression=req.constraint_expression,
            description=req.description,
            severity=req.severity,
            enabled=req.enabled,
        )
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.get("/validation-rules/{rule_id}")
def get_validation_rule(
    rule_id: str, _principal: Principal = Depends(require_principal),
):
    try:
        return get_validation_engine().get_rule(rule_id)
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.get("/validation-rules")
def list_validation_rules(
    rule_type: str | None = None,
    severity: str | None = None,
    enabled: bool | None = None,
    _principal: Principal = Depends(require_principal),
):
    return {
        "items": get_validation_engine().list_rules(
            rule_type=rule_type,
            severity=severity,
            enabled=enabled,
        ),
    }


@router.put("/validation-rules/{rule_id}")
def update_validation_rule(
    rule_id: str,
    updates: dict[str, Any],
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_validation_engine().update_rule(rule_id, **updates)
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.delete("/validation-rules/{rule_id}")
def delete_validation_rule(
    rule_id: str, _principal: Principal = Depends(require_principal),
):
    ok = get_validation_engine().delete_rule(rule_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"规则 {rule_id} 不存在", status_code=404)
    return {"deleted": True, "id": rule_id}


@router.post("/validation-rules/{rule_id}/validate")
def validate_entity(
    rule_id: str,
    req: ValidateRequest,
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_validation_engine().validate(req.entity_id, rule_id)
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.post("/validation-rules/validate-all")
def validate_all_rules(
    req: ValidateRequest, _principal: Principal = Depends(require_principal),
):
    return {"items": get_validation_engine().validate_all(req.entity_id)}


# ════════════════════ OKF Lint API ════════════════════

@router.post("/okf-lint-rules")
def create_okf_lint_rule(
    req: CreateLintRuleRequest, _principal: Principal = Depends(require_principal),
):
    try:
        return get_okf_lint_engine().create_rule(
            name=req.name,
            rule_type=req.rule_type,
            severity=req.severity,
            enabled=req.enabled,
        )
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.get("/okf-lint-rules/{rule_id}")
def get_okf_lint_rule(
    rule_id: str, _principal: Principal = Depends(require_principal),
):
    try:
        return get_okf_lint_engine().get_rule(rule_id)
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.get("/okf-lint-rules")
def list_okf_lint_rules(
    rule_type: str | None = None,
    severity: str | None = None,
    enabled: bool | None = None,
    _principal: Principal = Depends(require_principal),
):
    return {
        "items": get_okf_lint_engine().list_rules(
            rule_type=rule_type,
            severity=severity,
            enabled=enabled,
        ),
    }


@router.put("/okf-lint-rules/{rule_id}")
def update_okf_lint_rule(
    rule_id: str,
    updates: dict[str, Any],
    _principal: Principal = Depends(require_principal),
):
    try:
        return get_okf_lint_engine().update_rule(rule_id, **updates)
    except SchedulingRulesLintError as err:
        raise _map_error(err) from err


@router.delete("/okf-lint-rules/{rule_id}")
def delete_okf_lint_rule(
    rule_id: str, _principal: Principal = Depends(require_principal),
):
    ok = get_okf_lint_engine().delete_rule(rule_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"规则 {rule_id} 不存在", status_code=404)
    return {"deleted": True, "id": rule_id}


@router.post("/okf-lint/lint")
def lint_dataset(
    req: LintRequest, _principal: Principal = Depends(require_principal),
):
    return {"items": get_okf_lint_engine().lint(req.dataset_rid)}


@router.get("/okf-lint/drift-report/{dataset_rid}")
def get_drift_report(
    dataset_rid: str, _principal: Principal = Depends(require_principal),
):
    return get_okf_lint_engine().get_drift_report(dataset_rid)