"""W2-8/9 · Dynamic Scheduling API 路由。"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from aos_api.errors import ApiError
from aos_api.scheduling_engine import (
    Schedule,
    ScheduledResource,
    SchedulingEngine,
    SchedulingError,
    get_engine,
)

router = APIRouter(tags=["scheduling"])


def _map_error(err: SchedulingError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class CreateScheduleRequest(BaseModel):
    name: str
    cron: str
    target_type: str = "pipeline"
    target_id: str = ""
    enabled: bool = True
    scope: str = "project"
    max_retries: int = 3


class AssignResourceRequest(BaseModel):
    resource_type: str = "dataset"
    resource_id: str = ""
    allocation: str = "exclusive"


@router.post("/v1/scheduling/schedules")
def create_schedule(req: CreateScheduleRequest):
    sched = Schedule(
        name=req.name, cron=req.cron, target_type=req.target_type,
        target_id=req.target_id, enabled=req.enabled,
        scope=req.scope, max_retries=req.max_retries,
    )
    try:
        return get_engine().create_schedule(sched)
    except SchedulingError as err:
        raise _map_error(err) from err


@router.get("/v1/scheduling/schedules")
def list_schedules(enabled_only: bool = False):
    return {"items": get_engine().list_schedules(enabled_only=enabled_only)}


@router.get("/v1/scheduling/schedules/{sched_id}")
def get_schedule(sched_id: str):
    sched = get_engine().get_schedule(sched_id)
    if sched is None:
        raise ApiError(code="NOT_FOUND", message=f"调度 {sched_id} 不存在", status_code=404)
    return sched


@router.delete("/v1/scheduling/schedules/{sched_id}")
def delete_schedule(sched_id: str):
    ok = get_engine().delete_schedule(sched_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"调度 {sched_id} 不存在", status_code=404)
    return {"deleted": True, "id": sched_id}


@router.get("/v1/scheduling/schedules/{sched_id}/next-run")
def get_next_run(sched_id: str):
    try:
        nr = get_engine().get_next_run(sched_id)
        return {"next_run_at": nr.isoformat()}
    except SchedulingError as err:
        raise _map_error(err) from err


@router.post("/v1/scheduling/schedules/{sched_id}/trigger")
def trigger_schedule(sched_id: str):
    try:
        return get_engine().trigger(sched_id)
    except SchedulingError as err:
        raise _map_error(err) from err


@router.post("/v1/scheduling/schedules/{sched_id}/resources")
def assign_resource(sched_id: str, req: AssignResourceRequest):
    res = ScheduledResource(
        schedule_id=sched_id,
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        allocation=req.allocation,
    )
    return get_engine().assign_resource(res)


@router.get("/v1/scheduling/schedules/{sched_id}/resources")
def get_resources(sched_id: str):
    return {"items": get_engine().get_resources(sched_id)}


@router.get("/v1/scheduling/history")
def get_history(sched_id: str | None = None):
    return {"items": get_engine().history(sched_id)}
