"""Canonical responsibility successor and takeover API (W3-07)."""

# ruff: noqa: B008
from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from aos_api.aip_responsibility_assignment import (
    AssertAssignmentFenceRequest,
    AssignmentFenceObservation,
    CreateResponsibilitySuccessorRequest,
    CreateTakeoverRequest,
    DecideTakeoverRequest,
    ResponsibilitySuccessorReceipt,
    ResponsibilityAssignmentObservation,
    TakeoverDecisionReceipt,
    TakeoverRequestReceipt,
)
from aos_api.aip_responsibility_assignment_store import (
    AipResponsibilityAssignmentStore,
    ResponsibilityAssignmentBlocked,
    ResponsibilityAssignmentConflict,
    ResponsibilityAssignmentNotFound,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/aip/responsibility-assignments",
    tags=["aip-responsibility-assignments"],
)
_STORE = AipResponsibilityAssignmentStore()


def get_responsibility_assignment_store() -> AipResponsibilityAssignmentStore:
    return _STORE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_role(principal: Principal, *, checker: bool = False) -> None:
    roles = {role.lower() for role in principal.roles}
    allowed = {"admin", "aip_executor", "executor"}
    if checker:
        allowed |= {"reviewer", "approver"}
    if not roles.intersection(allowed):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted responsibility assignment role required",
            status_code=403,
        )


def _map(error: Exception) -> ApiError:
    if isinstance(error, ResponsibilityAssignmentNotFound):
        return ApiError(code=error.code, message=str(error), status_code=404)
    if isinstance(error, ResponsibilityAssignmentConflict):
        return ApiError(code=error.code, message=str(error), status_code=409)
    if isinstance(error, ResponsibilityAssignmentBlocked):
        return ApiError(code=error.code, message=str(error), status_code=422)
    return ApiError(code="RESPONSIBILITY_ASSIGNMENT_FAILED", message=str(error), status_code=500)


@router.get(
    "/runs/{run_id}/observation",
    response_model=ResponsibilityAssignmentObservation,
)
def observe_run_assignments(
    run_id: str,
    principal: Principal = Depends(require_principal),
    store: AipResponsibilityAssignmentStore = Depends(get_responsibility_assignment_store),
) -> ResponsibilityAssignmentObservation:
    _require_role(principal)
    try:
        return store.observe_run(_scope(principal), run_id)
    except Exception as error:
        raise _map(error) from error


@router.post("/successors", response_model=ResponsibilitySuccessorReceipt, status_code=201)
def create_responsibility_successor(
    body: CreateResponsibilitySuccessorRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    store: AipResponsibilityAssignmentStore = Depends(get_responsibility_assignment_store),
) -> ResponsibilitySuccessorReceipt:
    _require_role(principal)
    try:
        return store.create_successor(_scope(principal), body, actor=principal.subject, idempotency_key=idempotency_key)
    except Exception as error:
        raise _map(error) from error


@router.post("/takeovers", response_model=TakeoverRequestReceipt, status_code=201)
def create_takeover_request(
    body: CreateTakeoverRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    store: AipResponsibilityAssignmentStore = Depends(get_responsibility_assignment_store),
) -> TakeoverRequestReceipt:
    _require_role(principal)
    try:
        return store.create_takeover_request(_scope(principal), body, actor=principal.subject, idempotency_key=idempotency_key)
    except Exception as error:
        raise _map(error) from error


@router.post("/takeovers/{request_id}/decisions", response_model=TakeoverDecisionReceipt, status_code=201)
def decide_takeover(
    request_id: str,
    body: DecideTakeoverRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=200),
    principal: Principal = Depends(require_principal),
    store: AipResponsibilityAssignmentStore = Depends(get_responsibility_assignment_store),
) -> TakeoverDecisionReceipt:
    _require_role(principal, checker=True)
    try:
        return store.decide_takeover(_scope(principal), request_id, body, actor=principal.subject, idempotency_key=idempotency_key)
    except Exception as error:
        raise _map(error) from error


@router.post("/fence/assert", response_model=AssignmentFenceObservation)
def assert_assignment_fence(
    body: AssertAssignmentFenceRequest,
    principal: Principal = Depends(require_principal),
    store: AipResponsibilityAssignmentStore = Depends(get_responsibility_assignment_store),
) -> AssignmentFenceObservation:
    _require_role(principal)
    return store.assert_fence(_scope(principal), body)
