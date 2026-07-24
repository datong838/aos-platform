"""W2-AQ · Workshop Compute API 路由（#147 #151 #152）."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.workshop_compute_api import (
    AppEntry,
    AppEntryError,
    ComputeJob,
    ComputeJobError,
    VariableEvent,
    WorkshopVariable,
    WorkshopVariableError,
    get_app_entry_convention_engine,
    get_compute_job_polling_engine,
    get_workshop_variable_engine,
)

router = APIRouter(prefix="/workshop-compute-api", tags=["Workshop Compute API"])


def _map_variable_err(e: WorkshopVariableError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少 name"),
        "INVALID_VAR_TYPE": (400, "var_type 无效"),
        "INVALID_DEFINITION_TYPE": (400, "definition_type 无效"),
        "INVALID_RECOMPUTE_STRATEGY": (400, "recompute_strategy 无效"),
        "DEPENDENCY_NOT_FOUND": (400, "依赖变量不存在"),
        "CIRCULAR_DEPENDENCY": (400, "循环依赖"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_job_err(e: ComputeJobError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "MISSING_FUNCTION": (400, "缺少 function_name"),
        "INVALID_TOKEN": (400, "polling token 无效"),
        "JOB_NOT_COMPLETED": (400, "job 未完成"),
        "ALREADY_TERMINAL": (400, "job 已终止"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_entry_err(e: AppEntryError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "MISSING_FUNCTION": (400, "缺少 function_name"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ #147 Workshop Variable ════════════════════

@router.post("/variables", response_model=WorkshopVariable)
def register_variable(
    body: WorkshopVariable,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_variable_engine().register(body)
    except WorkshopVariableError as e:
        raise _map_variable_err(e) from e


@router.get("/variables", response_model=list[WorkshopVariable])
def list_variables(
    var_type: str | None = None,
    definition_type: str | None = None,
    module_id: str | None = None,
    principal: Principal = Depends(require_principal),
):
    return get_workshop_variable_engine().list(
        var_type=var_type,
        definition_type=definition_type,
        module_id=module_id,
    )


@router.get("/variables/{var_id}", response_model=WorkshopVariable)
def get_variable(
    var_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_variable_engine().get(var_id)
    except WorkshopVariableError as e:
        raise _map_variable_err(e) from e


@router.put("/variables/{var_id}", response_model=WorkshopVariable)
def update_variable(
    var_id: str,
    body: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_variable_engine().update(var_id, body)
    except WorkshopVariableError as e:
        raise _map_variable_err(e) from e


@router.delete("/variables/{var_id}")
def delete_variable(
    var_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_workshop_variable_engine().delete(var_id)
        return {"deleted": True}
    except WorkshopVariableError as e:
        raise _map_variable_err(e) from e


@router.post("/variables/{var_id}/evaluate")
def evaluate_variable(
    var_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_variable_engine().evaluate(var_id)
    except WorkshopVariableError as e:
        raise _map_variable_err(e) from e


@router.get("/variables/{var_id}/lineage")
def get_variable_lineage(
    var_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_variable_engine().get_lineage(var_id)
    except WorkshopVariableError as e:
        raise _map_variable_err(e) from e


class RecordEventBody(BaseModel):
    event_type: str
    payload: dict = {}


@router.post("/variables/{var_id}/events", response_model=VariableEvent)
def record_variable_event(
    var_id: str,
    body: RecordEventBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_variable_engine().record_event(
            var_id, body.event_type, body.payload)
    except WorkshopVariableError as e:
        raise _map_variable_err(e) from e


@router.get("/variables/{var_id}/events", response_model=list[VariableEvent])
def list_variable_events(
    var_id: str,
    principal: Principal = Depends(require_principal),
):
    return get_workshop_variable_engine().list_events(var_id=var_id)


# ════════════════════ #151 Compute Job Polling ════════════════════

class SubmitJobBody(BaseModel):
    module_id: str
    function_name: str
    payload: dict = {}


@router.post("/jobs", response_model=ComputeJob)
def submit_job(
    body: SubmitJobBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_compute_job_polling_engine().submit(
            body.module_id, body.function_name, body.payload)
    except ComputeJobError as e:
        raise _map_job_err(e) from e


@router.get("/jobs", response_model=list[ComputeJob])
def list_jobs(
    module_id: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_principal),
):
    return get_compute_job_polling_engine().list(
        module_id=module_id, status=status)


# 静态路径须注册在参数路由 /jobs/{job_id} 之前
@router.post("/jobs/timeouts/check", response_model=list[ComputeJob])
def check_job_timeouts(
    principal: Principal = Depends(require_principal),
):
    return get_compute_job_polling_engine().check_timeouts()


@router.get("/jobs/{job_id}", response_model=ComputeJob)
def get_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_compute_job_polling_engine().get(job_id)
    except ComputeJobError as e:
        raise _map_job_err(e) from e


class PollJobBody(BaseModel):
    polling_token: str


@router.post("/jobs/{job_id}/poll", response_model=ComputeJob)
def poll_job(
    job_id: str,
    body: PollJobBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_compute_job_polling_engine().poll(job_id, body.polling_token)
    except ComputeJobError as e:
        raise _map_job_err(e) from e


@router.get("/jobs/{job_id}/result")
def get_job_result(
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_compute_job_polling_engine().get_result(job_id)
    except ComputeJobError as e:
        raise _map_job_err(e) from e


@router.post("/jobs/{job_id}/cancel", response_model=ComputeJob)
def cancel_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_compute_job_polling_engine().cancel(job_id)
    except ComputeJobError as e:
        raise _map_job_err(e) from e


# ════════════════════ #152 App Entry Convention ════════════════════

@router.post("/app-entries", response_model=AppEntry)
def register_app_entry(
    body: AppEntry,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_app_entry_convention_engine().register(body)
    except AppEntryError as e:
        raise _map_entry_err(e) from e


@router.get("/app-entries", response_model=list[AppEntry])
def list_app_entries(
    module_id: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_principal),
):
    return get_app_entry_convention_engine().list(
        module_id=module_id, status=status)


# 静态路径须注册在参数路由 /app-entries/{entry_id} 之前
@router.get("/app-entries/invalid", response_model=list[AppEntry])
def list_invalid_app_entries(
    principal: Principal = Depends(require_principal),
):
    return get_app_entry_convention_engine().list_invalid()


@router.get("/app-entries/{entry_id}", response_model=AppEntry)
def get_app_entry(
    entry_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_app_entry_convention_engine().get(entry_id)
    except AppEntryError as e:
        raise _map_entry_err(e) from e


@router.post("/app-entries/{entry_id}/validate", response_model=AppEntry)
def validate_app_entry(
    entry_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_app_entry_convention_engine().validate(entry_id)
    except AppEntryError as e:
        raise _map_entry_err(e) from e


@router.put("/app-entries/{entry_id}", response_model=AppEntry)
def update_app_entry(
    entry_id: str,
    body: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_app_entry_convention_engine().update(entry_id, body)
    except AppEntryError as e:
        raise _map_entry_err(e) from e


@router.delete("/app-entries/{entry_id}")
def delete_app_entry(
    entry_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_app_entry_convention_engine().delete(entry_id)
        return {"deleted": True}
    except AppEntryError as e:
        raise _map_entry_err(e) from e


@router.get("/app-entries/{entry_id}/endpoint")
def get_app_entry_endpoint(
    entry_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_app_entry_convention_engine().get_endpoint(entry_id)
    except AppEntryError as e:
        raise _map_entry_err(e) from e
