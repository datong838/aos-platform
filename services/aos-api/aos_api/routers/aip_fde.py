"""FDE S1-S3 preview, session planning and canonical execution routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, status

from aos_api.aip_fde_contracts import (
    ExecuteFdeRunRequest,
    ExecuteFdeRunResponse,
    FdeIntakeRequest,
    FdeSessionCreated,
    FdeSessionPreview,
)
from aos_api.aip_fde_orchestrator import FdeS1S3Adapter, FdeS1S3Orchestrator
from aos_api.aip_task_store import AipTaskStore, AipTaskStoreError, AipTaskTransitionBlocked
from aos_api.aip_taor_loop import CanonicalTaorRunner
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.routers.aip_tasks import get_aip_task_store
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/fde", tags=["aip-fde"])


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _idem(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 160:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="Idempotency-Key must be 1..160 characters", status_code=400)
    return cleaned


def _store_error(exc: AipTaskStoreError) -> ApiError:
    status_code = 422 if isinstance(exc, AipTaskTransitionBlocked) else 409 if exc.code in {"AIP_VERSION_CONFLICT", "AIP_IDEMPOTENCY_CONFLICT"} else 503
    return ApiError(code=exc.code, message=str(exc), status_code=status_code)


@router.post("/sessions/preview", response_model=FdeSessionPreview)
def preview_fde_session(
    body: FdeIntakeRequest,
    principal: Principal = Depends(require_principal),
) -> FdeSessionPreview:
    return FdeS1S3Orchestrator().preview(_scope(principal), body)


@router.post("/sessions", response_model=FdeSessionCreated, status_code=status.HTTP_201_CREATED)
def create_fde_session(
    body: FdeIntakeRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
    store: AipTaskStore = Depends(get_aip_task_store),
) -> FdeSessionCreated:
    try:
        return FdeS1S3Orchestrator().create_session(store, _scope(principal), principal.subject, _idem(idempotency_key), body)
    except AipTaskStoreError as exc:
        raise _store_error(exc) from exc


@router.post("/task-runs/{run_id}/execute", response_model=ExecuteFdeRunResponse)
def execute_fde_run(
    run_id: str,
    body: ExecuteFdeRunRequest,
    principal: Principal = Depends(require_principal),
    store: AipTaskStore = Depends(get_aip_task_store),
) -> ExecuteFdeRunResponse:
    scope = _scope(principal)
    try:
        timeline = store.timeline(scope, run_id)
        if timeline.task.type != "fde_platform_onboarding":
            raise AipTaskTransitionBlocked("run is not an FDE onboarding task")
        expected = ["fde.s1.requirement", "fde.s2.auth-draft", "fde.s3.capability-probe"]
        if [step.step_key for step in timeline.plan.steps] != expected:
            raise AipTaskTransitionBlocked("run plan is not the exact FDE S1-S3 plan")
        adapter = FdeS1S3Adapter()

        class _ContextAdapter:
            def __init__(self) -> None:
                self._context: dict[str, object] = {}

            def think(self, step, context):
                self._context = context
                return adapter.think(step, context)

            def act(self, step, thought):
                del thought
                return adapter.act_with_context(step, self._context)

            def verify(self, step, action):
                return adapter.verify(step, action)

            def observe(self, step, action, verification):
                return adapter.observe(step, action, verification)

        result = CanonicalTaorRunner(store).run(
            scope,
            run_id,
            actor=principal.subject,
            worker_id=body.worker_id,
            adapter=_ContextAdapter(),
            lease_seconds=body.lease_seconds,
        )
        return ExecuteFdeRunResponse(result=result, timeline_ref=f"/v1/aip/task-runs/{run_id}/timeline")
    except AipTaskStoreError as exc:
        raise _store_error(exc) from exc
