"""Canonical tenant-scoped API for E7 memory projections and improvement facts."""
# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_memory_improvement import (
    AipMemoryImprovementBlocked,
    AipMemoryImprovementConflict,
    AipMemoryImprovementError,
    AipMemoryImprovementNotFound,
    AipMemoryImprovementService,
    ImprovementEvaluationRequest,
)
from aos_api.aip_memory_projection_contracts import (
    ChangeMemoryProjectionStatusRequest,
    CreateMemoryProjectionRequest,
    ImprovementObservation,
    MemoryProjection,
    MemoryProjectionEvent,
)
from aos_api.aip_memory_projection_store import (
    AipMemoryProjectionBlocked,
    AipMemoryProjectionConflict,
    AipMemoryProjectionError,
    AipMemoryProjectionNotFound,
    AipMemoryProjectionStore,
)
from aos_api.aip_memory_retrieval import AipMemoryRetrieval, MemoryRevocationImpact
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/memory-governance", tags=["aip-memory-governance"])
_PROJECTIONS = AipMemoryProjectionStore()
_IMPROVEMENT = AipMemoryImprovementService()


def get_projection_store() -> AipMemoryProjectionStore:
    return _PROJECTIONS


def get_improvement_service() -> AipMemoryImprovementService:
    return _IMPROVEMENT


def get_impact_reader() -> AipMemoryRetrieval:
    # Revocation impact reads references only; the resolver is never invoked.
    return AipMemoryRetrieval(payload_resolver=lambda _scope, _ref: None)  # type: ignore[arg-type]


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_role(principal: Principal, allowed: set[str]) -> None:
    if not {role.lower() for role in principal.roles}.intersection(allowed):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted memory governance role required",
            status_code=403,
        )


def _key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..120 characters",
            status_code=400,
        )
    return cleaned


def _projection_error(exc: AipMemoryProjectionError) -> ApiError:
    if isinstance(exc, AipMemoryProjectionNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipMemoryProjectionConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipMemoryProjectionBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="memory projection persistence failed", status_code=503)


def _improvement_error(exc: AipMemoryImprovementError) -> ApiError:
    if isinstance(exc, AipMemoryImprovementNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, AipMemoryImprovementConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipMemoryImprovementBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="memory improvement persistence failed", status_code=503)


@router.post("/projections", response_model=MemoryProjection, status_code=status.HTTP_201_CREATED)
def create_projection(
    body: CreateMemoryProjectionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipMemoryProjectionStore = Depends(get_projection_store),
):
    _require_role(principal, {"admin", "reviewer"})
    try:
        projection, _receipt = store.create_projection(
            _scope(principal), body, idempotency_key=_key(idempotency_key),
            actor=principal.subject, occurred_at=datetime.now(UTC),
        )
        return projection
    except AipMemoryProjectionError as exc:
        raise _projection_error(exc) from exc


@router.get("/projections", response_model=list[MemoryProjection])
def list_projections(
    owner_instance_id: str | None = Query(default=None, alias="ownerInstanceId"),
    recipient_instance_id: str | None = Query(default=None, alias="recipientInstanceId"),
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    store: AipMemoryProjectionStore = Depends(get_projection_store),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    try:
        return store.list_projections(
            _scope(principal), owner_instance_id=owner_instance_id,
            recipient_instance_id=recipient_instance_id, limit=limit,
        )
    except AipMemoryProjectionError as exc:
        raise _projection_error(exc) from exc


@router.get("/projections/{projection_id}", response_model=MemoryProjection)
def get_projection(
    projection_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryProjectionStore = Depends(get_projection_store),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    try:
        return store.get_projection(_scope(principal), projection_id)
    except AipMemoryProjectionError as exc:
        raise _projection_error(exc) from exc


@router.post("/projections/{projection_id}/status", response_model=MemoryProjection)
def change_projection_status(
    projection_id: str,
    body: ChangeMemoryProjectionStatusRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipMemoryProjectionStore = Depends(get_projection_store),
):
    _require_role(principal, {"admin", "reviewer"})
    try:
        projection, _receipt = store.change_status(
            _scope(principal), projection_id, body,
            idempotency_key=_key(idempotency_key), actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
        return projection
    except AipMemoryProjectionError as exc:
        raise _projection_error(exc) from exc


@router.get("/projections/{projection_id}/events", response_model=list[MemoryProjectionEvent])
def list_projection_events(
    projection_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryProjectionStore = Depends(get_projection_store),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    try:
        return store.list_events(_scope(principal), projection_id)
    except AipMemoryProjectionError as exc:
        raise _projection_error(exc) from exc


@router.get("/projections/{projection_id}/impact", response_model=MemoryRevocationImpact)
def get_projection_impact(
    projection_id: str,
    observed_at: datetime = Query(alias="observedAt"),
    principal: Principal = Depends(require_principal),
    reader: AipMemoryRetrieval = Depends(get_impact_reader),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    try:
        return reader.revocation_impact(_scope(principal), projection_id, observed_at=observed_at)
    except ValueError as exc:
        raise ApiError(code="AIP_MEMORY_PROJECTION_NOT_FOUND", message=str(exc), status_code=404) from exc


@router.post(
    "/observations/evaluate",
    response_model=ImprovementObservation,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_improvement(
    body: ImprovementEvaluationRequest,
    principal: Principal = Depends(require_principal),
    service: AipMemoryImprovementService = Depends(get_improvement_service),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    try:
        return service.evaluate(_scope(principal), body)
    except AipMemoryImprovementError as exc:
        raise _improvement_error(exc) from exc


@router.get("/observations", response_model=list[ImprovementObservation])
def list_observations(
    instance_id: str | None = Query(default=None, alias="instanceId"),
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    service: AipMemoryImprovementService = Depends(get_improvement_service),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    try:
        return service.list_observations(_scope(principal), instance_id=instance_id, limit=limit)
    except AipMemoryImprovementError as exc:
        raise _improvement_error(exc) from exc


@router.get("/observations/{observation_id}", response_model=ImprovementObservation)
def get_observation(
    observation_id: str,
    principal: Principal = Depends(require_principal),
    service: AipMemoryImprovementService = Depends(get_improvement_service),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    try:
        return service.get_observation(_scope(principal), observation_id)
    except AipMemoryImprovementError as exc:
        raise _improvement_error(exc) from exc
