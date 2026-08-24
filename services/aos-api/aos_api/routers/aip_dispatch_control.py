"""Canonical dispatch-intent and Task priority API (W3-08)."""

# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from aos_api.aip_dispatch_control import (
    ConfirmDispatchIntentRequest,
    CreateDispatchIntentRequest,
    DecideTaskPriorityRequest,
    DispatchConfirmationReceipt,
    DispatchControlObservation,
    DispatchIntentRevision,
    TaskPriorityDecisionRevision,
)
from aos_api.aip_dispatch_control_store import (
    AipDispatchControlStore,
    DispatchControlBlocked,
    DispatchControlConflict,
    DispatchControlError,
    DispatchControlNotFound,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/dispatch-control", tags=["aip-dispatch-control"])
_STORE = AipDispatchControlStore()


def get_dispatch_control_store() -> AipDispatchControlStore:
    return _STORE


@router.get("/tasks/{task_id}/observation", response_model=DispatchControlObservation)
def observe_task_dispatch_control(
    task_id: str,
    principal: Principal = Depends(require_principal),
    store: AipDispatchControlStore = Depends(get_dispatch_control_store),
) -> DispatchControlObservation:
    _require_operator(principal)
    try:
        return store.observe_task(_scope(principal), task_id)
    except DispatchControlError as error:
        raise _map(error) from error


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_operator(principal: Principal, *, checker: bool = False) -> None:
    roles = {role.lower() for role in principal.roles}
    allowed = {"admin", "aip_executor", "executor"}
    if checker:
        allowed |= {"reviewer", "approver"}
    if not roles.intersection(allowed):
        raise ApiError(code="AIP_SCOPE_FORBIDDEN", message="trusted dispatch role required", status_code=403)


def _map(error: DispatchControlError) -> ApiError:
    if isinstance(error, DispatchControlNotFound):
        return ApiError(code=error.code, message=str(error), status_code=404)
    if isinstance(error, DispatchControlConflict):
        return ApiError(code=error.code, message=str(error), status_code=409)
    if isinstance(error, DispatchControlBlocked):
        return ApiError(code=error.code, message=str(error), status_code=422)
    return ApiError(code=error.code, message="dispatch control persistence failed", status_code=503)


@router.post("/intents", response_model=DispatchIntentRevision, status_code=201)
def create_dispatch_intent(
    body: CreateDispatchIntentRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    store: AipDispatchControlStore = Depends(get_dispatch_control_store),
) -> DispatchIntentRevision:
    _require_operator(principal)
    try:
        return store.create_intent(_scope(principal), body, actor=principal.subject, idempotency_key=idempotency_key)
    except DispatchControlError as error:
        raise _map(error) from error


@router.post("/intents/{intent_id}/confirmations", response_model=DispatchConfirmationReceipt, status_code=201)
def confirm_dispatch_intent(
    intent_id: str,
    body: ConfirmDispatchIntentRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    store: AipDispatchControlStore = Depends(get_dispatch_control_store),
) -> DispatchConfirmationReceipt:
    _require_operator(principal, checker=True)
    try:
        return store.confirm_intent(_scope(principal), intent_id, body, actor=principal.subject, idempotency_key=idempotency_key)
    except DispatchControlError as error:
        raise _map(error) from error


@router.post("/task-priority-decisions", response_model=TaskPriorityDecisionRevision, status_code=201)
def decide_task_priority(
    body: DecideTaskPriorityRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    store: AipDispatchControlStore = Depends(get_dispatch_control_store),
) -> TaskPriorityDecisionRevision:
    _require_operator(principal)
    try:
        return store.decide_priority(_scope(principal), body, actor=principal.subject, idempotency_key=idempotency_key)
    except DispatchControlError as error:
        raise _map(error) from error
