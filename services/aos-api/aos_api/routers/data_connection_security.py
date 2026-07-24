"""W2-AK · Data Connection 安全治理路由（#125 #126 #127）."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from aos_api.auth import require_principal
from aos_api.data_connection_security import (
    DataConnectionSecurityError,
    EgressEvaluation,
    EgressPolicy,
    ExecutionAttempt,
    ExecutionState,
    ExportableMarkingPolicy,
    MarkingEvaluation,
    WebhookExecutionPolicy,
    get_egress_policy_engine,
    get_exportable_marking_engine,
    get_webhook_execution_policy_engine,
)
from aos_api.errors import ApiError

router = APIRouter(tags=["data_connection_security"])


def _map_err(e: DataConnectionSecurityError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少名称"),
        "MISSING_WEBHOOK": (400, "缺少 webhook_id"),
        "MISSING_CONNECTION": (400, "缺少 connection_id"),
        "INVALID_CONCURRENCY": (400, "并发数无效"),
        "INVALID_RATE_LIMIT": (400, "速率限制无效"),
        "INVALID_TIMEOUT": (400, "超时时间无效"),
        "INVALID_RETRY_COUNT": (400, "重试次数无效"),
        "INVALID_THRESHOLD": (400, "阈值无效"),
        "INVALID_EFFECT": (400, "效果值无效"),
        "EMPTY_RULES": (400, "至少需指定一种规则"),
        "INVALID_CIDR": (400, "CIDR 格式无效"),
        "INVALID_PORT": (400, "端口无效"),
        "INVALID_PROTOCOL": (400, "协议无效"),
        "INVALID_PRIORITY": (400, "优先级无效"),
        "INVALID_MARKING_LEVEL": (400, "标记级别无效"),
        "INVALID_EXPORT_ACTION": (400, "导出动作无效"),
        "NOT_FOUND": (404, "资源不存在"),
        "CONCURRENCY_EXCEEDED": (429, "并发数超限"),
        "RATE_LIMIT_EXCEEDED": (429, "速率超限"),
        "CIRCUIT_OPEN": (503, "熔断器打开"),
        "ATTEMPT_NOT_FOUND": (404, "尝试记录不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


# ════════════════════ #125 Webhook Execution Policy ════════════════════

@router.post("/v1/webhook-execution-policies", response_model=WebhookExecutionPolicy)
def create_webhook_execution_policy(policy: WebhookExecutionPolicy, _=require_principal):
    try:
        return get_webhook_execution_policy_engine().register(policy)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.get("/v1/webhook-execution-policies", response_model=list[WebhookExecutionPolicy])
def list_webhook_execution_policies(
    webhook_id: str | None = None,
    status: str | None = None,
    _=require_principal,
):
    return get_webhook_execution_policy_engine().list(webhook_id=webhook_id, status=status)


@router.get("/v1/webhook-execution-policies/{policy_id}", response_model=WebhookExecutionPolicy)
def get_webhook_execution_policy(policy_id: str, _=require_principal):
    try:
        return get_webhook_execution_policy_engine().get(policy_id)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.patch("/v1/webhook-execution-policies/{policy_id}", response_model=WebhookExecutionPolicy)
def update_webhook_execution_policy(policy_id: str, updates: dict, _=require_principal):
    try:
        return get_webhook_execution_policy_engine().update(policy_id, updates)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.delete("/v1/webhook-execution-policies/{policy_id}")
def delete_webhook_execution_policy(policy_id: str, _=require_principal):
    return {"deleted": get_webhook_execution_policy_engine().delete(policy_id)}


@router.post("/v1/webhook-execution-policies/{policy_id}/acquire", response_model=ExecutionAttempt)
def acquire_execution_slot(policy_id: str, call_id: str = Query(...), _=require_principal):
    try:
        return get_webhook_execution_policy_engine().acquire_slot(policy_id, call_id)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.post("/v1/webhook-execution-policies/{policy_id}/release", response_model=ExecutionAttempt)
def release_execution_slot(
    policy_id: str,
    call_id: str,
    success: bool,
    duration_ms: int,
    http_status: int | None = None,
    error_message: str | None = None,
    _=require_principal,
):
    try:
        return get_webhook_execution_policy_engine().release_slot(
            policy_id, call_id, success, http_status, duration_ms, error_message
        )
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.post("/v1/webhook-execution-policies/{policy_id}/retry", response_model=ExecutionAttempt)
def record_execution_retry(
    policy_id: str,
    call_id: str,
    attempt_number: int,
    next_attempt_at: str,
    error_message: str | None = None,
    _=require_principal,
):
    try:
        return get_webhook_execution_policy_engine().record_retry(
            policy_id, call_id, attempt_number, next_attempt_at, error_message
        )
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.get("/v1/webhook-execution-policies/{policy_id}/state", response_model=ExecutionState)
def get_execution_state(policy_id: str, _=require_principal):
    try:
        return get_webhook_execution_policy_engine().get_execution_state(policy_id)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.post("/v1/webhook-execution-policies/{policy_id}/reset-state", response_model=ExecutionState)
def reset_execution_state(policy_id: str, _=require_principal):
    try:
        return get_webhook_execution_policy_engine().reset_state(policy_id)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.get("/v1/webhook-execution-policies/{policy_id}/attempts", response_model=list[ExecutionAttempt])
def list_execution_attempts(
    policy_id: str,
    limit: int = Query(50, ge=1, le=200),
    _=require_principal,
):
    try:
        return get_webhook_execution_policy_engine().list_attempts(policy_id, limit=limit)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.post("/v1/webhook-execution-policies/{policy_id}/trip-circuit", response_model=ExecutionState)
def trip_circuit_breaker(policy_id: str, _=require_principal):
    try:
        return get_webhook_execution_policy_engine().trip_circuit(policy_id)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.post("/v1/webhook-execution-policies/{policy_id}/reset-circuit", response_model=ExecutionState)
def reset_circuit_breaker(policy_id: str, _=require_principal):
    try:
        return get_webhook_execution_policy_engine().reset_circuit(policy_id)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


# ════════════════════ #126 Egress Policy ════════════════════

@router.post("/v1/egress-policies", response_model=EgressPolicy)
def create_egress_policy(policy: EgressPolicy, _=require_principal):
    try:
        return get_egress_policy_engine().register(policy)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.get("/v1/egress-policies", response_model=list[EgressPolicy])
def list_egress_policies(
    effect: str | None = None,
    status: str | None = None,
    _=require_principal,
):
    return get_egress_policy_engine().list(effect=effect, status=status)


@router.get("/v1/egress-policies/{policy_id}", response_model=EgressPolicy)
def get_egress_policy(policy_id: str, _=require_principal):
    try:
        return get_egress_policy_engine().get(policy_id)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.patch("/v1/egress-policies/{policy_id}", response_model=EgressPolicy)
def update_egress_policy(policy_id: str, updates: dict, _=require_principal):
    try:
        return get_egress_policy_engine().update(policy_id, updates)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.delete("/v1/egress-policies/{policy_id}")
def delete_egress_policy(policy_id: str, _=require_principal):
    return {"deleted": get_egress_policy_engine().delete(policy_id)}


@router.post("/v1/egress-policies/evaluate", response_model=EgressEvaluation)
def evaluate_egress(
    destination: str,
    port: int,
    protocol: str,
    _=require_principal,
):
    return get_egress_policy_engine().evaluate(destination, port, protocol)


@router.post("/v1/egress-policies/evaluate-batch")
def evaluate_egress_batch(requests: list[dict], _=require_principal):
    results = get_egress_policy_engine().evaluate_batch(requests)
    return {"count": len(results), "evaluations": [r.model_dump() for r in results]}


@router.get("/v1/egress-policies/check-allowed")
def check_egress_allowed(
    destination: str,
    port: int,
    protocol: str,
    _=require_principal,
):
    return {"allowed": get_egress_policy_engine().check_allowed(destination, port, protocol)}


@router.get("/v1/egress-policies/evaluations", response_model=list[EgressEvaluation])
def list_egress_evaluations(
    policy_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    _=require_principal,
):
    return get_egress_policy_engine().list_evaluations(policy_id=policy_id, limit=limit)


@router.post("/v1/egress-policies/{policy_id}/cidrs", response_model=EgressPolicy)
def add_egress_cidr(policy_id: str, cidr: str = Query(...), _=require_principal):
    try:
        return get_egress_policy_engine().add_cidr(policy_id, cidr)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.delete("/v1/egress-policies/{policy_id}/cidrs", response_model=EgressPolicy)
def remove_egress_cidr(policy_id: str, cidr: str = Query(...), _=require_principal):
    try:
        return get_egress_policy_engine().remove_cidr(policy_id, cidr)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.post("/v1/egress-policies/{policy_id}/domains", response_model=EgressPolicy)
def add_egress_domain(policy_id: str, domain: str = Query(...), _=require_principal):
    try:
        return get_egress_policy_engine().add_domain(policy_id, domain)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.delete("/v1/egress-policies/{policy_id}/domains", response_model=EgressPolicy)
def remove_egress_domain(policy_id: str, domain: str = Query(...), _=require_principal):
    try:
        return get_egress_policy_engine().remove_domain(policy_id, domain)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


# ════════════════════ #127 Exportable Marking ════════════════════

@router.post("/v1/exportable-markings", response_model=ExportableMarkingPolicy)
def create_exportable_marking_policy(policy: ExportableMarkingPolicy, _=require_principal):
    try:
        return get_exportable_marking_engine().register(policy)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.get("/v1/exportable-markings", response_model=list[ExportableMarkingPolicy])
def list_exportable_marking_policies(
    connection_id: str | None = None,
    status: str | None = None,
    marking_level: str | None = None,
    _=require_principal,
):
    return get_exportable_marking_engine().list(
        connection_id=connection_id, status=status, marking_level=marking_level
    )


@router.get("/v1/exportable-markings/{policy_id}", response_model=ExportableMarkingPolicy)
def get_exportable_marking_policy(policy_id: str, _=require_principal):
    try:
        return get_exportable_marking_engine().get(policy_id)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.patch("/v1/exportable-markings/{policy_id}", response_model=ExportableMarkingPolicy)
def update_exportable_marking_policy(policy_id: str, updates: dict, _=require_principal):
    try:
        return get_exportable_marking_engine().update(policy_id, updates)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.delete("/v1/exportable-markings/{policy_id}")
def delete_exportable_marking_policy(policy_id: str, _=require_principal):
    return {"deleted": get_exportable_marking_engine().delete(policy_id)}


@router.post("/v1/exportable-markings/evaluate", response_model=MarkingEvaluation)
def evaluate_exportable_marking(
    connection_id: str,
    markings: list[str],
    column_name: str | None = None,
    value: str | None = None,
    _=require_principal,
):
    return get_exportable_marking_engine().evaluate(connection_id, column_name, markings, value)


@router.post("/v1/exportable-markings/evaluate-row")
def evaluate_exportable_marking_row(connection_id: str, columns: list[dict], _=require_principal):
    results = get_exportable_marking_engine().evaluate_row(connection_id, columns)
    return {"count": len(results), "evaluations": [r.model_dump() for r in results]}


@router.get("/v1/exportable-markings/can-export")
def can_export_marking(connection_id: str, markings: list[str], _=require_principal):
    return {"can_export": get_exportable_marking_engine().can_export(connection_id, markings)}


@router.get("/v1/exportable-markings/evaluations", response_model=list[MarkingEvaluation])
def list_marking_evaluations(
    policy_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    _=require_principal,
):
    return get_exportable_marking_engine().list_evaluations(policy_id=policy_id, limit=limit)


@router.post("/v1/exportable-markings/{policy_id}/columns", response_model=ExportableMarkingPolicy)
def add_affected_column(policy_id: str, column: str = Query(...), _=require_principal):
    try:
        return get_exportable_marking_engine().add_affected_column(policy_id, column)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.delete("/v1/exportable-markings/{policy_id}/columns", response_model=ExportableMarkingPolicy)
def remove_affected_column(policy_id: str, column: str = Query(...), _=require_principal):
    try:
        return get_exportable_marking_engine().remove_affected_column(policy_id, column)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.post("/v1/exportable-markings/{policy_id}/markings", response_model=ExportableMarkingPolicy)
def add_affected_marking(policy_id: str, marking: str = Query(...), _=require_principal):
    try:
        return get_exportable_marking_engine().add_affected_marking(policy_id, marking)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e


@router.delete("/v1/exportable-markings/{policy_id}/markings", response_model=ExportableMarkingPolicy)
def remove_affected_marking(policy_id: str, marking: str = Query(...), _=require_principal):
    try:
        return get_exportable_marking_engine().remove_affected_marking(policy_id, marking)
    except DataConnectionSecurityError as e:
        raise _map_err(e) from e
