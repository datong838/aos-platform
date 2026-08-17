"""Canonical API for AgentRun execution-attempt authority."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryError,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_agent_run_execution_contracts import (
    AgentRunExecutionAttempt,
    AgentRunExecutionAttemptCommandResponse,
    AgentRunExecutionAttemptListResponse,
    CreateAgentRunExecutionAttemptRequest,
    TransitionAgentRunExecutionAttemptRequest,
)
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_contracts import TenantContext
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope


router = APIRouter(prefix="/v1/aip/agent-runs", tags=["aip-agent-runs"])
_SERVICE = AipAgentRunExecutionService()


def get_agent_run_execution_service() -> AipAgentRunExecutionService:
    return _SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _tenant(principal: Principal) -> TenantContext:
    return TenantContext(org_id=principal.org_id, project_id=principal.project_id)


def _idem(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..200 characters",
            status_code=400,
        )
    return cleaned


def _map_error(exc: AipAgentRegistryError) -> ApiError:
    if isinstance(exc, AipAgentRegistryNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipAgentRegistryConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipAgentRegistryTransitionBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, AipAgentRegistryPersistenceError):
        return ApiError(
            code=exc.code,
            message="agent run execution authority persistence failed",
            status_code=503,
        )
    return ApiError(code=exc.code, message="agent run execution authority failed", status_code=503)


@router.post(
    "/execution-attempts",
    response_model=AgentRunExecutionAttemptCommandResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_execution_attempt(
    body: CreateAgentRunExecutionAttemptRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipAgentRunExecutionService = Depends(get_agent_run_execution_service),
) -> AgentRunExecutionAttemptCommandResponse:
    try:
        attempt, receipt = service.create(
            _scope(principal), body, idempotency_key=_idem(idempotency_key),
            actor=principal.subject, occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return AgentRunExecutionAttemptCommandResponse(
        tenant=_tenant(principal), attempt=attempt, receipt=receipt
    )


@router.get(
    "/execution-attempts", response_model=AgentRunExecutionAttemptListResponse
)
def list_execution_attempts(
    agent_run_id: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    service: AipAgentRunExecutionService = Depends(get_agent_run_execution_service),
) -> AgentRunExecutionAttemptListResponse:
    try:
        items = service.list(_scope(principal), agent_run_id=agent_run_id, limit=limit)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return AgentRunExecutionAttemptListResponse(
        tenant=_tenant(principal), items=items, count=len(items)
    )


@router.get(
    "/execution-attempts/{attempt_id}", response_model=AgentRunExecutionAttempt
)
def get_execution_attempt(
    attempt_id: str,
    principal: Principal = Depends(require_principal),
    service: AipAgentRunExecutionService = Depends(get_agent_run_execution_service),
) -> AgentRunExecutionAttempt:
    try:
        return service.get(_scope(principal), attempt_id)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/execution-attempts/{attempt_id}/transition",
    response_model=AgentRunExecutionAttemptCommandResponse,
)
def transition_execution_attempt(
    attempt_id: str,
    body: TransitionAgentRunExecutionAttemptRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipAgentRunExecutionService = Depends(get_agent_run_execution_service),
) -> AgentRunExecutionAttemptCommandResponse:
    try:
        attempt, receipt = service.transition(
            _scope(principal), attempt_id, body,
            idempotency_key=_idem(idempotency_key), actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
    return AgentRunExecutionAttemptCommandResponse(
        tenant=_tenant(principal), attempt=attempt, receipt=receipt
    )
