"""Canonical tenant-scoped API for E7 memory projections and improvement facts."""
# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import Field

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_memory_improvement import (
    AipMemoryImprovementBlocked,
    AipMemoryImprovementConflict,
    AipMemoryImprovementError,
    AipMemoryImprovementNotFound,
    AipMemoryImprovementService,
)
from aos_api.aip_memory_projection_contracts import (
    ChangeMemoryProjectionStatusRequest,
    CreateMemoryProjectionRequest,
    ImprovementObservation,
    MemoryExposure,
    MemoryProjection,
    MemoryProjectionEvent,
    MemoryProjectionStatus,
)
from aos_api.aip_memory_projection_store import (
    AipMemoryProjectionBlocked,
    AipMemoryProjectionConflict,
    AipMemoryProjectionError,
    AipMemoryProjectionNotFound,
    AipMemoryProjectionStore,
)
from aos_api.aip_memory_retrieval import (
    AgentMemoryContextRequest,
    AgentMemoryContextView,
    AipAgentMemoryRetrieval,
    MemoryRevocationImpact,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/memory-authority", tags=["aip-memory-authority"])
_PROJECTIONS = AipMemoryProjectionStore()
_IMPROVEMENT = AipMemoryImprovementService()
_MEMORY_READER = AipAgentMemoryRetrieval(
    payload_resolver=lambda _scope, _ref: None  # reference-only API never resolves bodies
)


class ProjectionTransitionCommand(AipContractModel):
    expected_version: int = Field(ge=1)
    from_status: MemoryProjectionStatus
    reason_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def get_projection_store() -> AipMemoryProjectionStore:
    return _PROJECTIONS


def get_improvement_service() -> AipMemoryImprovementService:
    return _IMPROVEMENT


def get_memory_reader() -> AipAgentMemoryRetrieval:
    return _MEMORY_READER


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


@router.post("/agent-projections", response_model=MemoryProjection, status_code=status.HTTP_201_CREATED)
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


@router.get("/agent-projections", response_model=list[MemoryProjection])
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


@router.get("/agent-projections/{projection_id}", response_model=MemoryProjection)
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


def _change_projection_status(
    projection_id: str,
    body: ProjectionTransitionCommand,
    *,
    target: MemoryProjectionStatus,
    idempotency_key: str,
    principal: Principal,
    store: AipMemoryProjectionStore,
):
    _require_role(principal, {"admin", "reviewer"})
    try:
        projection, _receipt = store.change_status(
            _scope(principal), projection_id,
            ChangeMemoryProjectionStatusRequest(
                expected_version=body.expected_version,
                from_status=body.from_status,
                to_status=target,
                reason_hash=body.reason_hash,
            ),
            idempotency_key=_key(idempotency_key), actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
        return projection
    except AipMemoryProjectionError as exc:
        raise _projection_error(exc) from exc


@router.post("/agent-projections/{projection_id}/suspend", response_model=MemoryProjection)
def suspend_projection(
    projection_id: str,
    body: ProjectionTransitionCommand,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipMemoryProjectionStore = Depends(get_projection_store),
):
    return _change_projection_status(
        projection_id, body, target=MemoryProjectionStatus.SUSPENDED,
        idempotency_key=idempotency_key, principal=principal, store=store,
    )


@router.post("/agent-projections/{projection_id}/reactivate", response_model=MemoryProjection)
def reactivate_projection(
    projection_id: str,
    body: ProjectionTransitionCommand,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipMemoryProjectionStore = Depends(get_projection_store),
):
    return _change_projection_status(
        projection_id, body, target=MemoryProjectionStatus.ACTIVE,
        idempotency_key=idempotency_key, principal=principal, store=store,
    )


@router.post("/agent-projections/{projection_id}/revoke", response_model=MemoryProjection)
def revoke_projection(
    projection_id: str,
    body: ProjectionTransitionCommand,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipMemoryProjectionStore = Depends(get_projection_store),
):
    return _change_projection_status(
        projection_id, body, target=MemoryProjectionStatus.REVOKED,
        idempotency_key=idempotency_key, principal=principal, store=store,
    )


@router.get("/agent-projections/{projection_id}/events", response_model=list[MemoryProjectionEvent])
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


@router.get("/agent-projections/{projection_id}/impact", response_model=MemoryRevocationImpact)
def get_projection_impact(
    projection_id: str,
    observed_at: datetime = Query(alias="observedAt"),
    principal: Principal = Depends(require_principal),
    reader: AipAgentMemoryRetrieval = Depends(get_memory_reader),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    try:
        return reader.revocation_impact(_scope(principal), projection_id, observed_at=observed_at)
    except ValueError as exc:
        raise ApiError(code="AIP_MEMORY_PROJECTION_NOT_FOUND", message=str(exc), status_code=404) from exc


@router.get(
    "/agent-instances/{instance_id}/memory-context",
    response_model=AgentMemoryContextView,
)
def get_agent_memory_context(
    instance_id: str,
    instance_revision: int = Query(alias="instanceRevision", ge=1),
    instance_hash: str = Query(alias="instanceHash", pattern=r"^[0-9a-f]{64}$"),
    skill_id: str = Query(alias="skillId", min_length=1),
    skill_revision: int = Query(alias="skillRevision", ge=1),
    skill_hash: str = Query(alias="skillHash", pattern=r"^[0-9a-f]{64}$"),
    logic_id: str = Query(alias="logicId", min_length=1),
    logic_revision: int = Query(alias="logicRevision", ge=1),
    logic_hash: str = Query(alias="logicHash", pattern=r"^[0-9a-f]{64}$"),
    purpose: list[str] = Query(min_length=1),
    time_cutoff: datetime = Query(alias="timeCutoff"),
    principal: Principal = Depends(require_principal),
    reader: AipAgentMemoryRetrieval = Depends(get_memory_reader),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    request = AgentMemoryContextRequest(
        agent_instance_ref=VersionedAssetRef(
            asset_type="AgentInstance",
            asset_id=instance_id,
            revision=instance_revision,
            content_hash=instance_hash,
        ),
        skill_ref=VersionedAssetRef(
            asset_type="SkillTemplate",
            asset_id=skill_id,
            revision=skill_revision,
            content_hash=skill_hash,
        ),
        logic_ref=VersionedAssetRef(
            asset_type="LogicRevision",
            asset_id=logic_id,
            revision=logic_revision,
            content_hash=logic_hash,
        ),
        purposes=purpose,
        authorized_markings=principal.markings,
        time_cutoff=time_cutoff,
    )
    return reader.query_context_view(_scope(principal), request)


@router.get("/memory-exposures", response_model=list[MemoryExposure])
def list_memory_exposures(
    instance_id: str | None = Query(default=None, alias="instanceId"),
    projection_id: str | None = Query(default=None, alias="projectionId"),
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    reader: AipAgentMemoryRetrieval = Depends(get_memory_reader),
):
    _require_role(principal, {"admin", "reviewer", "executor", "aip_executor"})
    return reader.list_exposures(
        _scope(principal),
        instance_id=instance_id,
        projection_id=projection_id,
        limit=limit,
    )


@router.get("/improvement-observations", response_model=list[ImprovementObservation])
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


@router.get("/improvement-observations/{observation_id}", response_model=ImprovementObservation)
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
