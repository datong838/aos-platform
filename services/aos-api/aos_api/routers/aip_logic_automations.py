"""Governed Logic automation API backed by canonical Task/Plan/Run authority."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Header, status

from aos_api.aip_contracts import PlanStep
from aos_api.aip_logic_automation_models import (
    CreateLogicAutomationRequest,
    LogicAutomationListResponse,
    LogicAutomationPolicy,
    LogicAutomationRun,
    LogicAutomationRunListResponse,
    UpdateLogicAutomationRequest,
)
from aos_api.aip_logic_automation_store import (
    LogicAutomationConflict,
    LogicAutomationError,
    LogicAutomationGateRejected,
    LogicAutomationNotFound,
    LogicAutomationPersistenceError,
    LogicAutomationStore,
)
from aos_api.aip_task_models import (
    ApprovePlanRevisionRequest,
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
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

router = APIRouter(prefix="/v1/aip/logic/graphs", tags=["aip-logic-automations"])
summary_router = APIRouter(prefix="/v1/aip/logic", tags=["aip-logic-automations"])
_STORE = LogicAutomationStore()
_TASKS = AipTaskStore()


def get_logic_automation_store() -> LogicAutomationStore:
    return _STORE


def get_logic_automation_task_service() -> AipTaskService:
    return AipTaskService(_TASKS)


def _error(exc: LogicAutomationError) -> ApiError:
    if isinstance(exc, LogicAutomationNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, LogicAutomationConflict):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, LogicAutomationGateRejected):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    if isinstance(exc, LogicAutomationPersistenceError):
        return ApiError(code=exc.code, message="logic automation persistence is unavailable", status_code=503)
    return ApiError(code=exc.code, message=str(exc), status_code=500)


def _task_error(exc: AipTaskStoreError) -> ApiError:
    if isinstance(exc, AipTaskNotFound):
        return ApiError(code=exc.code, message=str(exc), status_code=404)
    if isinstance(exc, (AipTaskVersionConflict, AipTaskIdempotencyConflict)):
        return ApiError(code=exc.code, message=str(exc), status_code=409)
    if isinstance(exc, AipTaskTransitionBlocked):
        return ApiError(code=exc.code, message=str(exc), status_code=422)
    return ApiError(code=exc.code, message="task runtime persistence failed", status_code=503)


def _idempotency_key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200:
        raise ApiError(
            code="AIP_INVALID_ARGUMENT",
            message="Idempotency-Key must be 1..200 characters",
            status_code=400,
        )
    return cleaned


def dispatch_logic_automation(
    principal: Principal,
    policy: LogicAutomationPolicy,
    store: LogicAutomationStore,
    tasks: AipTaskService,
    *,
    request_key: str,
    trigger: str,
) -> LogicAutomationRun:
    """Create one idempotent internal Task/Plan/Run and a no-production-write Receipt."""
    if policy.status != "active":
        raise LogicAutomationGateRejected("paused automation cannot be triggered")
    key = hashlib.sha256(
        f"{policy.automation_id}:{policy.revision}:{policy.publication_id}:{request_key}".encode()
    ).hexdigest()[:24]
    task = tasks.create_task(
        principal,
        f"logic-auto-task-{key}",
        CreateTaskRequest(
            type="logic_automation_run",
            title=f"{policy.name} · 受控运行",
            description=f"绑定正式发布 {policy.publication_id}",
            goal={
                "automationId": policy.automation_id,
                "publicationId": policy.publication_id,
                "graphHash": policy.graph_hash,
                "trigger": trigger,
                "productionWritten": False,
            },
        ),
    )
    plan = tasks.create_plan(
        principal,
        task.id,
        f"logic-auto-plan-{key}",
        CreatePlanRevisionRequest(
            expected_task_version=task.version,
            steps=[PlanStep(step_key="dispatch_published_logic", title=f"调度正式发布修订 {policy.graph_revision}")],
            risk={"externalEffectsAllowed": False, "productionWritten": False},
        ),
    )
    planned = tasks.store.get_task(tasks.scope(principal), task.id)
    approved = tasks.approve_plan(
        principal,
        task.id,
        plan.revision,
        ApprovePlanRevisionRequest(
            expected_task_version=planned.version,
            expected_content_hash=plan.content_hash,
        ),
    )
    approved_task = tasks.store.get_task(tasks.scope(principal), task.id)
    run = tasks.create_run(
        principal,
        task.id,
        f"logic-auto-run-{key}",
        CreateTaskRunRequest(
            plan_revision_id=approved.id,
            expected_task_version=approved_task.version,
            logic_graph_id=policy.graph_id,
            logic_revision=policy.graph_revision,
        ),
    )
    return store.record_run(
        principal.org_id,
        principal.project_id,
        policy,
        idempotency_key=request_key,
        task_id=task.id,
        task_run_id=run.id,
        trigger=trigger,
    )


@summary_router.get("/automation-policies", response_model=LogicAutomationListResponse)
def list_tenant_automation_policies(
    principal: Principal = Depends(require_principal),
    store: LogicAutomationStore = Depends(get_logic_automation_store),
) -> LogicAutomationListResponse:
    try:
        items = store.list_all(principal.org_id, principal.project_id)
        return LogicAutomationListResponse(items=items, count=len(items))
    except LogicAutomationError as exc:
        raise _error(exc) from exc


@router.get("/{graph_id}/automations", response_model=LogicAutomationListResponse)
def list_automations(
    graph_id: str,
    principal: Principal = Depends(require_principal),
    store: LogicAutomationStore = Depends(get_logic_automation_store),
) -> LogicAutomationListResponse:
    try:
        items = store.list(principal.org_id, principal.project_id, graph_id)
        return LogicAutomationListResponse(items=items, count=len(items))
    except LogicAutomationError as exc:
        raise _error(exc) from exc


@router.post("/{graph_id}/automations", response_model=LogicAutomationPolicy, status_code=status.HTTP_201_CREATED)
def create_automation(
    graph_id: str,
    body: CreateLogicAutomationRequest,
    principal: Principal = Depends(require_principal),
    store: LogicAutomationStore = Depends(get_logic_automation_store),
) -> LogicAutomationPolicy:
    try:
        return store.create(principal.org_id, principal.project_id, graph_id, principal.subject, body)
    except LogicAutomationError as exc:
        raise _error(exc) from exc


@router.put("/{graph_id}/automations/{automation_id}", response_model=LogicAutomationPolicy)
def update_automation(
    graph_id: str,
    automation_id: str,
    body: UpdateLogicAutomationRequest,
    principal: Principal = Depends(require_principal),
    store: LogicAutomationStore = Depends(get_logic_automation_store),
) -> LogicAutomationPolicy:
    try:
        return store.update(
            principal.org_id, principal.project_id, graph_id, automation_id, principal.subject, body
        )
    except LogicAutomationError as exc:
        raise _error(exc) from exc


@router.post("/{graph_id}/automations/{automation_id}/trigger", response_model=LogicAutomationRun, status_code=status.HTTP_202_ACCEPTED)
def trigger_automation(
    graph_id: str,
    automation_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: LogicAutomationStore = Depends(get_logic_automation_store),
    tasks: AipTaskService = Depends(get_logic_automation_task_service),
) -> LogicAutomationRun:
    try:
        policy = store.get(principal.org_id, principal.project_id, graph_id, automation_id)
        request_key = _idempotency_key(idempotency_key)
        return dispatch_logic_automation(
            principal, policy, store, tasks, request_key=request_key, trigger="manual"
        )
    except LogicAutomationError as exc:
        raise _error(exc) from exc
    except AipTaskStoreError as exc:
        raise _task_error(exc) from exc


@router.get("/{graph_id}/automations/{automation_id}/runs", response_model=LogicAutomationRunListResponse)
def list_automation_runs(
    graph_id: str,
    automation_id: str,
    principal: Principal = Depends(require_principal),
    store: LogicAutomationStore = Depends(get_logic_automation_store),
) -> LogicAutomationRunListResponse:
    try:
        items = store.list_runs(principal.org_id, principal.project_id, graph_id, automation_id)
        return LogicAutomationRunListResponse(items=items, count=len(items))
    except LogicAutomationError as exc:
        raise _error(exc) from exc
