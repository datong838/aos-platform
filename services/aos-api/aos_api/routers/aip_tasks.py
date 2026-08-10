"""Canonical AIP-1 Task, PlanRevision and TaskRun API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status

from aos_api.aip_task_models import (
    ApprovePlanRevisionRequest,
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
    PlanRevisionSnapshot,
    TaskListResponse,
    TaskRunSnapshot,
    TaskSnapshot,
    TaskTimeline,
)
from aos_api.aip_task_service import AipTaskService
from aos_api.aip_task_store import (
    AipTaskIdempotencyConflict,
    AipTaskNotFound,
    AipTaskStore,
    AipTaskStoreError,
    AipTaskTransitionBlocked,
    AipTaskVersionConflict,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.public_contracts import TaskStatus
from aos_api.routers.phase3_aip_logic import router as _legacy_logic_router
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip", tags=["aip-tasks"])
_STORE = AipTaskStore()


def get_aip_task_store() -> AipTaskStore:
    return _STORE


def get_aip_task_service(
    store: AipTaskStore = Depends(get_aip_task_store),
) -> AipTaskService:
    return AipTaskService(store)


def _idem(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..200 characters",
            status_code=400,
        )
    return cleaned


def _map_store_error(exc: AipTaskStoreError) -> ApiError:
    if isinstance(exc, AipTaskNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (AipTaskVersionConflict, AipTaskIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipTaskTransitionBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(
        code=exc.code,
        message="task runtime persistence failed",
        status_code=503,
    )


@router.post("/tasks", response_model=TaskSnapshot, status_code=status.HTTP_201_CREATED)
def create_task(
    body: CreateTaskRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipTaskService = Depends(get_aip_task_service),
) -> TaskSnapshot:
    try:
        return service.create_task(principal, _idem(idempotency_key), body)
    except AipTaskStoreError as exc:
        raise _map_store_error(exc) from exc


@router.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    principal: Principal = Depends(require_principal),
    service: AipTaskService = Depends(get_aip_task_service),
) -> TaskListResponse:
    try:
        items = service.list_tasks(principal, task_status, limit)
    except AipTaskStoreError as exc:
        raise _map_store_error(exc) from exc
    return TaskListResponse(items=items, count=len(items))


@router.get("/tasks/{task_id}", response_model=TaskSnapshot)
def get_task(
    task_id: str,
    principal: Principal = Depends(require_principal),
    store: AipTaskStore = Depends(get_aip_task_store),
) -> TaskSnapshot:
    try:
        return store.get_task(TenantScope(principal.org_id, principal.project_id), task_id)
    except AipTaskStoreError as exc:
        raise _map_store_error(exc) from exc


@router.post(
    "/tasks/{task_id}/plans",
    response_model=PlanRevisionSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def create_plan_revision(
    task_id: str,
    body: CreatePlanRevisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipTaskService = Depends(get_aip_task_service),
) -> PlanRevisionSnapshot:
    try:
        return service.create_plan(
            principal, task_id, _idem(idempotency_key), body
        )
    except AipTaskStoreError as exc:
        raise _map_store_error(exc) from exc


@router.post(
    "/tasks/{task_id}/plans/{revision}/approve",
    response_model=PlanRevisionSnapshot,
)
def approve_plan_revision(
    task_id: str,
    revision: int,
    body: ApprovePlanRevisionRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipTaskService = Depends(get_aip_task_service),
) -> PlanRevisionSnapshot:
    _idem(idempotency_key)
    try:
        return service.approve_plan(principal, task_id, revision, body)
    except AipTaskStoreError as exc:
        raise _map_store_error(exc) from exc


@router.post(
    "/tasks/{task_id}/runs",
    response_model=TaskRunSnapshot,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_task_run(
    task_id: str,
    body: CreateTaskRunRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    service: AipTaskService = Depends(get_aip_task_service),
) -> TaskRunSnapshot:
    try:
        return service.create_run(principal, task_id, _idem(idempotency_key), body)
    except AipTaskStoreError as exc:
        raise _map_store_error(exc) from exc


@router.get("/task-runs/{run_id}", response_model=TaskRunSnapshot)
def get_task_run(
    run_id: str,
    principal: Principal = Depends(require_principal),
    store: AipTaskStore = Depends(get_aip_task_store),
) -> TaskRunSnapshot:
    try:
        return store.get_run(TenantScope(principal.org_id, principal.project_id), run_id)
    except AipTaskStoreError as exc:
        raise _map_store_error(exc) from exc


@router.get("/task-runs/{run_id}/timeline", response_model=TaskTimeline)
def get_task_run_timeline(
    run_id: str,
    principal: Principal = Depends(require_principal),
    store: AipTaskStore = Depends(get_aip_task_store),
) -> TaskTimeline:
    try:
        return store.timeline(TenantScope(principal.org_id, principal.project_id), run_id)
    except AipTaskStoreError as exc:
        raise _map_store_error(exc) from exc


# AIP-1 makes this module the single manifest owner for the canonical Task API.
# The two legacy Logic/Automation routes remain nested here only until AIP-2.
_task_router = router
router = APIRouter()
router.include_router(_legacy_logic_router)
router.include_router(_task_router)
