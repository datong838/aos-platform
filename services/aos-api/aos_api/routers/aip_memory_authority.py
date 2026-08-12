"""Canonical tenant-scoped API for governed AIP memory authority."""

# FastAPI dependency injection intentionally evaluates Depends at import time.
# ruff: noqa: B008
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Query
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
from aos_api.aip_memory_pipeline_contracts import (
    CompleteKnowledgePipelineRunRequest,
    CreateKnowledgePipelineScheduleRequest,
    KnowledgePipelineAlert,
    KnowledgePipelineCheckpointRevision,
    KnowledgePipelinePolicy,
    KnowledgePipelineReceipt,
    KnowledgePipelineRun,
    KnowledgePipelineRunEvent,
    KnowledgePipelineSchedule,
    KnowledgePipelineScheduleEvent,
    KnowledgePipelineScheduleStatus,
    KnowledgePipelineTrigger,
    StartKnowledgePipelineRunRequest,
)
from aos_api.aip_memory_contracts import LicensePolicyDecision
from aos_api.aip_memory_pipeline_service import (
    AipMemoryPipelinePolicyBlocked,
    AipMemoryPipelineService,
)
from aos_api.aip_memory_pipeline_store import (
    AipMemoryPipelineConflict,
    AipMemoryPipelineNotFound,
    AipMemoryPipelinePersistenceError,
    AipMemoryPipelineStore,
    AipMemoryPipelineStoreError,
    AipMemoryPipelineTransitionBlocked,
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
_PIPELINE_STORE = AipMemoryPipelineStore()
_PIPELINE_SERVICE = AipMemoryPipelineService(
    pipeline_store=_PIPELINE_STORE,
    memory_store=_STORE,
    dependency_resolver=lambda _scope, _kind: None,
    receipt_resolver=lambda _scope, _ref: None,
    license_resolver=lambda _scope, _receipt: LicensePolicyDecision.UNKNOWN,
)


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


class TransitionPipelineScheduleCommand(AipContractModel):
    expected_version: int = Field(ge=1)
    from_status: KnowledgePipelineScheduleStatus
    to_status: KnowledgePipelineScheduleStatus
    reason_code: str = Field(min_length=1, max_length=120)


class StartPipelineRunCommand(AipContractModel):
    pipeline_run_id: str = Field(min_length=1, max_length=200)
    schedule_id: str = Field(min_length=1, max_length=200)
    task_id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    trigger: KnowledgePipelineTrigger
    expected_checkpoint_version: int = Field(ge=0)
    scheduled_for: datetime
    retry_of_run_id: str | None = Field(default=None, min_length=1, max_length=200)
    authorized_manual: bool = False


class PipelineCheckpointView(AipContractModel):
    checkpoint: KnowledgePipelineCheckpointRevision | None


class PipelineReceiptView(AipContractModel):
    receipt: KnowledgePipelineReceipt | None


def get_aip_memory_store() -> AipMemoryStore:
    return _STORE


def get_aip_memory_governance_service() -> AipMemoryGovernanceService | None:
    return None


def get_aip_memory_retrieval_service() -> AipMemoryRetrieval | None:
    return None


def get_aip_memory_pipeline_store() -> AipMemoryPipelineStore:
    return _PIPELINE_STORE


def get_aip_memory_pipeline_service() -> AipMemoryPipelineService:
    return _PIPELINE_SERVICE


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
    if isinstance(exc, AipMemoryPipelineNotFound):
        return ApiError(code=exc.code, message="knowledge pipeline record not found", status_code=404)
    if isinstance(exc, AipMemoryPipelineConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, (AipMemoryPipelinePolicyBlocked, AipMemoryPipelineTransitionBlocked)):
        details = (
            {"reasons": exc.reasons}
            if isinstance(exc, AipMemoryPipelinePolicyBlocked)
            else None
        )
        return ApiError(
            code=exc.code,
            message="knowledge pipeline operation blocked",
            status_code=422,
            details=details,
        )
    if isinstance(exc, AipMemoryPipelinePersistenceError):
        return ApiError(
            code=exc.code,
            message="knowledge pipeline authority is unavailable",
            status_code=503,
        )
    if isinstance(exc, AipMemoryPipelineStoreError):
        return ApiError(code=exc.code, message="knowledge pipeline operation failed", status_code=422)
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


@router.get("/pipelines/policies", response_model=list[KnowledgePipelinePolicy])
def list_pipeline_policies(
    principal: Principal = Depends(require_principal),
    service: AipMemoryPipelineService = Depends(get_aip_memory_pipeline_service),
) -> list[KnowledgePipelinePolicy]:
    _scope(principal)
    return [service.policy_for(kind) for kind in service.policy_kinds()]


@router.get("/pipelines/schedules", response_model=list[KnowledgePipelineSchedule])
def list_pipeline_schedules(
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> list[KnowledgePipelineSchedule]:
    try:
        return store.list_schedules(_scope(principal), limit=limit)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/pipelines/schedules", response_model=KnowledgePipelineSchedule)
def create_pipeline_schedule(
    body: CreateKnowledgePipelineScheduleRequest,
    idempotency_key: str = Header(min_length=1, max_length=240, alias="X-Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipMemoryPipelineService = Depends(get_aip_memory_pipeline_service),
) -> KnowledgePipelineSchedule:
    _require_role(principal, {"admin", "reviewer"})
    try:
        return service.create_schedule(
            _scope(principal),
            body,
            idempotency_key=idempotency_key,
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/pipelines/schedules/{schedule_id}", response_model=KnowledgePipelineSchedule)
def get_pipeline_schedule(
    schedule_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> KnowledgePipelineSchedule:
    try:
        return store.get_schedule(_scope(principal), schedule_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/pipelines/schedules/{schedule_id}/events",
    response_model=list[KnowledgePipelineScheduleEvent],
)
def list_pipeline_schedule_events(
    schedule_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> list[KnowledgePipelineScheduleEvent]:
    try:
        store.get_schedule(_scope(principal), schedule_id)
        return store.list_schedule_events(_scope(principal), schedule_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/pipelines/schedules/{schedule_id}/transitions",
    response_model=KnowledgePipelineSchedule,
)
def transition_pipeline_schedule(
    schedule_id: str,
    body: TransitionPipelineScheduleCommand,
    principal: Principal = Depends(require_principal),
    service: AipMemoryPipelineService = Depends(get_aip_memory_pipeline_service),
) -> KnowledgePipelineSchedule:
    _require_role(principal, {"admin", "reviewer"})
    try:
        schedule, _event = service.transition_schedule(
            _scope(principal),
            schedule_id,
            expected_version=body.expected_version,
            from_status=body.from_status,
            to_status=body.to_status,
            reason_code=body.reason_code,
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
        return schedule
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/pipelines/schedules/{schedule_id}/checkpoint",
    response_model=PipelineCheckpointView,
)
def get_pipeline_checkpoint(
    schedule_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> PipelineCheckpointView:
    try:
        store.get_schedule(_scope(principal), schedule_id)
        return PipelineCheckpointView(
            checkpoint=store.get_checkpoint(_scope(principal), schedule_id)
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/pipelines/runs", response_model=list[KnowledgePipelineRun])
def list_pipeline_runs(
    schedule_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> list[KnowledgePipelineRun]:
    try:
        return store.list_runs(
            _scope(principal), schedule_id=schedule_id, limit=limit
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post("/pipelines/runs", response_model=KnowledgePipelineRun)
def start_pipeline_run(
    body: StartPipelineRunCommand,
    idempotency_key: str = Header(min_length=1, max_length=240, alias="X-Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipMemoryPipelineService = Depends(get_aip_memory_pipeline_service),
) -> KnowledgePipelineRun:
    _require_role(principal, {"admin", "executor", "aip_executor"})
    request = StartKnowledgePipelineRunRequest(
        pipeline_run_id=body.pipeline_run_id,
        schedule_id=body.schedule_id,
        task_id=body.task_id,
        run_id=body.run_id,
        trigger=body.trigger,
        expected_checkpoint_version=body.expected_checkpoint_version,
        scheduled_for=body.scheduled_for,
        retry_of_run_id=body.retry_of_run_id,
    )
    try:
        return service.start_run(
            _scope(principal),
            request,
            idempotency_key=idempotency_key,
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
            authorized_manual=body.authorized_manual,
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get("/pipelines/runs/{pipeline_run_id}", response_model=KnowledgePipelineRun)
def get_pipeline_run(
    pipeline_run_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> KnowledgePipelineRun:
    try:
        return store.get_run(_scope(principal), pipeline_run_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/pipelines/runs/{pipeline_run_id}/events",
    response_model=list[KnowledgePipelineRunEvent],
)
def list_pipeline_run_events(
    pipeline_run_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> list[KnowledgePipelineRunEvent]:
    try:
        store.get_run(_scope(principal), pipeline_run_id)
        return store.list_run_events(_scope(principal), pipeline_run_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/pipelines/runs/{pipeline_run_id}/receipt",
    response_model=PipelineReceiptView,
)
def get_pipeline_receipt(
    pipeline_run_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> PipelineReceiptView:
    try:
        store.get_run(_scope(principal), pipeline_run_id)
        return PipelineReceiptView(
            receipt=store.get_receipt_for_run(
                _scope(principal), pipeline_run_id, required=False
            )
        )
    except Exception as exc:
        raise _map_error(exc) from exc


@router.get(
    "/pipelines/runs/{pipeline_run_id}/alerts",
    response_model=list[KnowledgePipelineAlert],
)
def list_pipeline_alerts(
    pipeline_run_id: str,
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> list[KnowledgePipelineAlert]:
    try:
        store.get_run(_scope(principal), pipeline_run_id)
        return store.list_alerts(_scope(principal), pipeline_run_id)
    except Exception as exc:
        raise _map_error(exc) from exc


@router.post(
    "/pipelines/runs/{pipeline_run_id}/complete",
    response_model=KnowledgePipelineReceipt,
)
def complete_pipeline_run(
    pipeline_run_id: str,
    body: CompleteKnowledgePipelineRunRequest,
    principal: Principal = Depends(require_principal),
    store: AipMemoryPipelineStore = Depends(get_aip_memory_pipeline_store),
) -> KnowledgePipelineReceipt:
    _require_role(principal, {"executor", "aip_executor"})
    try:
        return store.complete_run(
            _scope(principal),
            pipeline_run_id,
            body,
            actor=principal.subject,
            occurred_at=datetime.now(UTC),
        )
    except Exception as exc:
        raise _map_error(exc) from exc


__all__ = ["router"]
