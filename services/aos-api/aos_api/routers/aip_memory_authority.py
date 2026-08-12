"""Canonical tenant-scoped API for governed AIP memory authority."""

# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_memory_contracts import (
    GovernanceApprovalRef,
    KnowledgeQuery,
    KnowledgeQueryResult,
    MemoryCandidate,
    MemoryCandidateEvent,
    MemoryCandidateStatus,
    MemoryItem,
    MemoryItemRevision,
    MemoryItemStatus,
)
from aos_api.aip_memory_governance import (
    AipMemoryGovernanceBlocked,
    AipMemoryGovernanceService,
)
from aos_api.aip_memory_retrieval import AipMemoryRetrieval
from aos_api.aip_memory_store import (
    AipMemoryConflict,
    AipMemoryNotFound,
    AipMemoryPersistenceError,
    AipMemoryStore,
    AipMemoryStoreError,
    AipMemoryTransitionBlocked,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(
    prefix="/v1/aip/memory-authority",
    tags=["aip-memory-authority"],
)
_STORE = AipMemoryStore()


class ApproveCandidateRequest(AipContractModel):
    expected_version: int = Field(ge=1)
    governance: GovernanceApprovalRef
    required_applicability: list[str] = Field(min_length=1, max_length=64)


class PromoteCandidateRequest(AipContractModel):
    memory_item_id: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=1)
    required_applicability: list[str] = Field(min_length=1, max_length=64)
    expires_at: datetime | None = None


class MemoryAuthorityItem(AipContractModel):
    item: MemoryItem
    revision: MemoryItemRevision


def get_aip_memory_store() -> AipMemoryStore:
    return _STORE


def get_aip_memory_governance_service() -> AipMemoryGovernanceService | None:
    return None


def get_aip_memory_retrieval_service() -> AipMemoryRetrieval | None:
    return None


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _require_role(principal: Principal, allowed: set[str]) -> None:
    if not {role.lower() for role in principal.roles}.intersection(allowed):
        raise ApiError(
            code="AIP_SCOPE_FORBIDDEN",
            message="trusted memory authority role required",
            status_code=403,
        )


def _map_error(exc: Exception) -> ApiError:
    if isinstance(exc, AipMemoryNotFound):
        return ApiError(code=exc.code, message="memory authority record not found", status_code=404)
    if isinstance(exc, AipMemoryConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, (AipMemoryGovernanceBlocked, AipMemoryTransitionBlocked)):
        details = {"reasons": exc.reasons} if isinstance(exc, AipMemoryGovernanceBlocked) else None
        return ApiError(
            code=exc.code,
            message="memory governance operation blocked",
            status_code=422,
            details=details,
        )
    if isinstance(exc, AipMemoryPersistenceError):
        return ApiError(
            code=exc.code,
            message="memory authority persistence is unavailable",
            status_code=503,
        )
    if isinstance(exc, AipMemoryStoreError):
        return ApiError(code=exc.code, message="memory authority operation failed", status_code=422)
    return ApiError(
        code="AIP_MEMORY_AUTHORITY_FAILED",
        message="memory authority operation failed",
        status_code=500,
    )


@router.get("/candidates", response_model=list[MemoryCandidate])
def list_candidates(
    status: MemoryCandidateStatus | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    store: AipMemoryStore = Depends(get_aip_memory_store),
) -> list[MemoryCandidate]:
    try:
        return store.list_candidates(_scope(principal), status=status, limit=limit)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/candidates/{candidate_id}", response_model=MemoryCandidate)
def get_candidate(
    candidate_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryStore = Depends(get_aip_memory_store),
) -> MemoryCandidate:
    try:
        return store.get_candidate(_scope(principal), candidate_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/candidates/{candidate_id}/events",
    response_model=list[MemoryCandidateEvent],
)
def list_candidate_events(
    candidate_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryStore = Depends(get_aip_memory_store),
) -> list[MemoryCandidateEvent]:
    try:
        store.get_candidate(_scope(principal), candidate_id)
        return store.list_candidate_events(_scope(principal), candidate_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/candidates/{candidate_id}/approve", response_model=MemoryCandidate)
def approve_candidate(
    candidate_id: str,
    body: ApproveCandidateRequest,
    principal: Principal = Depends(require_principal),
    service: AipMemoryGovernanceService | None = Depends(get_aip_memory_governance_service),
) -> MemoryCandidate:
    _require_role(principal, {"admin", "reviewer"})
    if service is None:
        raise ApiError(
            code="AIP_MEMORY_GOVERNANCE_UNAVAILABLE",
            message="trusted memory governance providers are unavailable",
            status_code=503,
        )
    try:
        return service.approve_candidate(
            _scope(principal),
            candidate_id,
            expected_version=body.expected_version,
            governance=body.governance,
            required_applicability=body.required_applicability,
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/candidates/{candidate_id}/promote", response_model=MemoryAuthorityItem)
def promote_candidate(
    candidate_id: str,
    body: PromoteCandidateRequest,
    principal: Principal = Depends(require_principal),
    service: AipMemoryGovernanceService | None = Depends(get_aip_memory_governance_service),
) -> MemoryAuthorityItem:
    _require_role(principal, {"admin", "reviewer"})
    if service is None:
        raise ApiError(
            code="AIP_MEMORY_GOVERNANCE_UNAVAILABLE",
            message="trusted memory governance providers are unavailable",
            status_code=503,
        )
    try:
        _candidate, item, revision = service.promote_candidate(
            _scope(principal),
            candidate_id,
            memory_item_id=body.memory_item_id,
            expected_version=body.expected_version,
            required_applicability=body.required_applicability,
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
            expires_at=body.expires_at,
        )
        return MemoryAuthorityItem(item=item, revision=revision)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/memories", response_model=list[MemoryAuthorityItem])
def list_memories(
    status: MemoryItemStatus | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    store: AipMemoryStore = Depends(get_aip_memory_store),
) -> list[MemoryAuthorityItem]:
    try:
        return [
            MemoryAuthorityItem(item=item, revision=revision)
            for item, revision in store.list_memory_items(
                _scope(principal), status=status, limit=limit
            )
        ]
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/memories/{memory_item_id}", response_model=MemoryAuthorityItem)
def get_memory(
    memory_item_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryStore = Depends(get_aip_memory_store),
) -> MemoryAuthorityItem:
    try:
        item, revision = store.get_memory_item(_scope(principal), memory_item_id)
        return MemoryAuthorityItem(item=item, revision=revision)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/knowledge-queries", response_model=KnowledgeQueryResult)
def query_knowledge(
    body: KnowledgeQuery,
    principal: Principal = Depends(require_principal),
    service: AipMemoryRetrieval | None = Depends(get_aip_memory_retrieval_service),
) -> KnowledgeQueryResult:
    _require_role(
        principal,
        {"admin", "reviewer", "executor", "aip_executor", "developer"},
    )
    if service is None:
        raise ApiError(
            code="AIP_MEMORY_RETRIEVAL_UNAVAILABLE",
            message="trusted memory payload resolver is unavailable",
            status_code=503,
        )
    return service.query(
        _scope(principal),
        body,
        authorized_markings=principal.markings,
        required_applicability=[f"skill:{body.skill_ref.resource_id}"],
    )


__all__ = ["router"]
