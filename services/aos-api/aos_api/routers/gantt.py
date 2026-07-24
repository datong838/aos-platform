"""W2-#10 · Dynamic Scheduling 甘特图 API 路由。

详见 docs/palantier/20_tech/220tech_w2-d-gantt-tx.md。
"""
from __future__ import annotations

from fastapi import APIRouter

from aos_api.errors import ApiError
from aos_api.gantt import GanttEngine, GanttError, get_engine, list_allocation_behaviors

router = APIRouter(tags=["gantt"])


def _map_error(err: GanttError) -> ApiError:
    return ApiError(code=err.code, message=err.message, status_code=400)


@router.get("/v1/scheduling/gantt")
def get_gantt_view(
    scope: str = "project",
    horizon_hours: int = 168,
    duration_minutes: int = 60,
    include_disabled: bool = True,
):
    try:
        view = get_engine().build_view(
            scope=scope,
            horizon_hours=horizon_hours,
            duration_minutes=duration_minutes,
            include_disabled=include_disabled,
        )
    except GanttError as err:
        raise _map_error(err) from err
    return view.model_dump()


@router.get("/v1/scheduling/schedules/{sched_id}/gantt")
def get_schedule_gantt(
    sched_id: str,
    horizon_hours: int = 168,
    duration_minutes: int = 60,
):
    try:
        view = get_engine().build_for_schedule(
            sched_id, horizon_hours=horizon_hours, duration_minutes=duration_minutes
        )
    except GanttError as err:
        raise _map_error(err) from err
    return view.model_dump()


@router.get("/v1/scheduling/allocation-behaviors")
def list_behaviors():
    return {"items": list_allocation_behaviors()}
