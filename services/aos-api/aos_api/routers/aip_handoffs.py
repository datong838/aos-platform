"""Canonical HTTP for one-time HandoffEnvelope authority (issue → get → consume)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, status

from aos_api.aip_agent_registry_contracts import (
    ConsumeHandoffRequest,
    CreateHandoffDecisionRequest,
    DecidedHandoff,
    HandoffDecisionListResponse,
    HandoffDecisionRevision,
    HandoffEnvelope,
    IssueHandoffRequest,
    IssuedHandoff,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryError,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_handoff_service import AipHandoffService
from aos_api.aip_handoff_reference_authority import AipHandoffReferenceAuthority
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/handoffs", tags=["aip-handoffs"])
_REFERENCE_AUTHORITY = AipHandoffReferenceAuthority()
_SERVICE = AipHandoffService(
    ref_authorizer=_REFERENCE_AUTHORITY,
    envelope_authorizer=_REFERENCE_AUTHORITY.authorize_receiver,
)


def get_handoff_service() -> AipHandoffService:
    return _SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


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
            message="handoff authority persistence failed",
            status_code=503,
        )
    return ApiError(code=exc.code, message="handoff authority failed", status_code=503)


@router.post("", response_model=IssuedHandoff, status_code=status.HTTP_201_CREATED)
def issue_handoff(
    body: IssueHandoffRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipHandoffService = Depends(get_handoff_service),
) -> IssuedHandoff:
    try:
        return service.issue(
            _scope(principal),
            body,
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.get("/{handoff_id}", response_model=HandoffEnvelope)
def get_handoff(
    handoff_id: str,
    principal: Principal = Depends(require_principal),
    service: AipHandoffService = Depends(get_handoff_service),
) -> HandoffEnvelope:
    try:
        return service.get(_scope(principal), handoff_id)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post("/{handoff_id}/consume", response_model=HandoffEnvelope)
def consume_handoff(
    handoff_id: str,
    body: ConsumeHandoffRequest,
    principal: Principal = Depends(require_principal),
    service: AipHandoffService = Depends(get_handoff_service),
) -> HandoffEnvelope:
    try:
        return service.consume(
            _scope(principal),
            handoff_id,
            bearer_token=body.bearer_token,
            receiver_instance=body.receiver_instance,
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.post(
    "/{handoff_id}/decisions",
    response_model=DecidedHandoff,
    status_code=status.HTTP_201_CREATED,
)
def create_handoff_decision(
    handoff_id: str,
    body: CreateHandoffDecisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipHandoffService = Depends(get_handoff_service),
) -> DecidedHandoff:
    try:
        return service.decide(
            _scope(principal),
            handoff_id,
            body,
            idempotency_key=_idem(idempotency_key),
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.get("/{handoff_id}/decisions", response_model=HandoffDecisionListResponse)
def list_handoff_decisions(
    handoff_id: str,
    principal: Principal = Depends(require_principal),
    service: AipHandoffService = Depends(get_handoff_service),
) -> HandoffDecisionListResponse:
    try:
        return service.list_decisions(_scope(principal), handoff_id)
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc


@router.get(
    "/{handoff_id}/decisions/{decision_id}",
    response_model=HandoffDecisionRevision,
)
def get_handoff_decision(
    handoff_id: str,
    decision_id: str,
    principal: Principal = Depends(require_principal),
    service: AipHandoffService = Depends(get_handoff_service),
) -> HandoffDecisionRevision:
    try:
        decision = service.get_decision(_scope(principal), decision_id)
        if decision.handoff_id != handoff_id:
            raise AipAgentRegistryNotFound("handoff decision not found")
        return decision
    except AipAgentRegistryError as exc:
        raise _map_error(exc) from exc
