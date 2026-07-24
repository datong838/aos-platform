"""W2-AL · Data Lineage 可视化路由（#130 #131 #132）."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from aos_api.auth import require_principal
from aos_api.errors import ApiError
from aos_api.lineage_visualization import (
    BuildRun,
    BuildSchedule,
    ColumnIndexEntry,
    ColumnLineageSearchError,
    ColumnTraceResult,
    GanttChart,
    LineageBuildTimelineError,
    LineageGraph,
    LineageView,
    LineageVisualizationError,
    get_column_lineage_search_engine,
    get_lineage_build_timeline_engine,
    get_lineage_visualization_engine,
)

router = APIRouter(prefix="/lineage", tags=["Lineage Visualization"])


def _map_lineage_err(e: LineageVisualizationError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少名称"),
        "MISSING_DATASET": (400, "缺少 root_dataset_rid"),
        "INVALID_GRAPH_MODE": (400, "graph_mode 无效"),
        "INVALID_DIRECTION": (400, "direction 无效"),
        "INVALID_LAYOUT": (400, "layout 无效"),
        "INVALID_DEPTH": (400, "depth 无效"),
        "INVALID_COLOR_BY": (400, "color_by 无效"),
        "NOT_FOUND": (404, "视图不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


def _map_column_err(e: ColumnLineageSearchError) -> HTTPException:
    mapping = {
        "MISSING_DATASET": (400, "缺少 dataset_rid"),
        "MISSING_COLUMN": (400, "缺少 column_name"),
        "INVALID_DIRECTION": (400, "direction 无效"),
        "INVALID_DEPTH": (400, "max_depth 无效"),
        "NOT_FOUND": (404, "列不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


def _map_build_err(e: LineageBuildTimelineError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少名称"),
        "MISSING_PIPELINE": (400, "缺少 pipeline_id"),
        "INVALID_CRON": (400, "cron 表达式无效"),
        "INVALID_TIMEZONE": (400, "timezone 无效"),
        "INVALID_STATUS": (400, "status 无效"),
        "NOT_FOUND": (404, "调度不存在"),
        "SCHEDULE_PAUSED": (400, "调度已暂停"),
        "RUN_NOT_FOUND": (404, "运行记录不存在"),
        "RUN_NOT_RUNNING": (400, "运行未在进行中"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


# ════════════════════ #130 Lineage Views ════════════════════


@router.post("/views", response_model=LineageView)
def create_lineage_view(view: LineageView, _=require_principal):
    try:
        return get_lineage_visualization_engine().register(view)
    except LineageVisualizationError as e:
        raise _map_lineage_err(e) from e


@router.get("/views/{view_id}", response_model=LineageView)
def get_lineage_view(view_id: str, _=require_principal):
    try:
        return get_lineage_visualization_engine().get(view_id)
    except LineageVisualizationError as e:
        raise _map_lineage_err(e) from e


@router.get("/views", response_model=list[LineageView])
def list_lineage_views(
    saved_by: str | None = None,
    graph_mode: str | None = None,
    _=require_principal,
):
    return get_lineage_visualization_engine().list(saved_by=saved_by, graph_mode=graph_mode)


@router.put("/views/{view_id}", response_model=LineageView)
def update_lineage_view(view_id: str, updates: dict, _=require_principal):
    try:
        return get_lineage_visualization_engine().update(view_id, updates)
    except LineageVisualizationError as e:
        raise _map_lineage_err(e) from e


@router.delete("/views/{view_id}")
def delete_lineage_view(view_id: str, _=require_principal):
    return {"deleted": get_lineage_visualization_engine().delete(view_id)}


@router.post("/views/{view_id}/graph", response_model=LineageGraph)
def generate_lineage_graph(view_id: str, _=require_principal):
    try:
        return get_lineage_visualization_engine().generate_graph(view_id)
    except LineageVisualizationError as e:
        raise _map_lineage_err(e) from e


@router.post("/views/{view_id}/nodes/{node_id}/expand", response_model=LineageGraph)
def expand_lineage_node(view_id: str, node_id: str, _=require_principal):
    try:
        return get_lineage_visualization_engine().expand_node(view_id, node_id)
    except LineageVisualizationError as e:
        raise _map_lineage_err(e) from e


@router.post("/views/{view_id}/nodes/{node_id}/collapse", response_model=LineageGraph)
def collapse_lineage_node(view_id: str, node_id: str, _=require_principal):
    try:
        return get_lineage_visualization_engine().collapse_node(view_id, node_id)
    except LineageVisualizationError as e:
        raise _map_lineage_err(e) from e


@router.post("/views/{view_id}/color", response_model=LineageGraph)
def color_lineage_view(view_id: str, body: dict, _=require_principal):
    try:
        color_by = body.get("color_by", "")
        return get_lineage_visualization_engine().color_by(view_id, color_by)
    except LineageVisualizationError as e:
        raise _map_lineage_err(e) from e


@router.post("/views/{view_id}/share", response_model=LineageView)
def share_lineage_view(view_id: str, body: dict, _=require_principal):
    try:
        is_public = body.get("is_public", False)
        return get_lineage_visualization_engine().share_view(view_id, is_public)
    except LineageVisualizationError as e:
        raise _map_lineage_err(e) from e


# ════════════════════ #131 Column Lineage Search ════════════════════


@router.post("/columns/{dataset_rid}/{column_name}", response_model=ColumnIndexEntry)
def register_column(
    dataset_rid: str,
    column_name: str,
    data_type: str = "string",
    description: str = "",
    _=require_principal,
):
    try:
        return get_column_lineage_search_engine().register_column(
            dataset_rid, column_name, data_type, description
        )
    except ColumnLineageSearchError as e:
        raise _map_column_err(e) from e


@router.get("/columns/{dataset_rid}/{column_name}", response_model=ColumnIndexEntry)
def get_column(dataset_rid: str, column_name: str, _=require_principal):
    try:
        return get_column_lineage_search_engine().get_column(dataset_rid, column_name)
    except ColumnLineageSearchError as e:
        raise _map_column_err(e) from e


@router.get("/columns/{dataset_rid}", response_model=list[ColumnIndexEntry])
def list_columns(dataset_rid: str, _=require_principal):
    return get_column_lineage_search_engine().list_columns(dataset_rid)


@router.put("/columns/{dataset_rid}/{column_name}", response_model=ColumnIndexEntry)
def update_column(dataset_rid: str, column_name: str, updates: dict, _=require_principal):
    try:
        return get_column_lineage_search_engine().update_column(dataset_rid, column_name, updates)
    except ColumnLineageSearchError as e:
        raise _map_column_err(e) from e


@router.delete("/columns/{dataset_rid}/{column_name}")
def delete_column(dataset_rid: str, column_name: str, _=require_principal):
    return {"deleted": get_column_lineage_search_engine().delete_column(dataset_rid, column_name)}


@router.get("/columns/search", response_model=list[ColumnIndexEntry])
def search_columns(
    keyword: str = "",
    data_type: str | None = None,
    tag: str | None = None,
    _=require_principal,
):
    return get_column_lineage_search_engine().search_columns(keyword, data_type, tag)


@router.get("/columns/trace", response_model=ColumnTraceResult)
def trace_column(
    dataset_rid: str,
    column_name: str,
    direction: str = "downstream",
    max_depth: int = Query(3, ge=1, le=10),
    _=require_principal,
):
    try:
        return get_column_lineage_search_engine().trace_column(
            dataset_rid, column_name, direction, max_depth
        )
    except ColumnLineageSearchError as e:
        raise _map_column_err(e) from e


@router.post("/columns/index/{dataset_rid}")
def rebuild_column_index(dataset_rid: str, _=require_principal):
    try:
        count = get_column_lineage_search_engine().build_index(dataset_rid)
        return {"dataset_rid": dataset_rid, "indexed_columns": count}
    except ColumnLineageSearchError as e:
        raise _map_column_err(e) from e


# ════════════════════ #132 Build Timeline ════════════════════


@router.post("/build/schedules", response_model=BuildSchedule)
def create_build_schedule(schedule: BuildSchedule, _=require_principal):
    try:
        return get_lineage_build_timeline_engine().register_schedule(schedule)
    except LineageBuildTimelineError as e:
        raise _map_build_err(e) from e


@router.get("/build/schedules/{schedule_id}", response_model=BuildSchedule)
def get_build_schedule(schedule_id: str, _=require_principal):
    try:
        return get_lineage_build_timeline_engine().get_schedule(schedule_id)
    except LineageBuildTimelineError as e:
        raise _map_build_err(e) from e


@router.get("/build/schedules", response_model=list[BuildSchedule])
def list_build_schedules(
    pipeline_id: str | None = None,
    status: str | None = None,
    _=require_principal,
):
    return get_lineage_build_timeline_engine().list_schedules(
        pipeline_id=pipeline_id, status=status
    )


@router.put("/build/schedules/{schedule_id}", response_model=BuildSchedule)
def update_build_schedule(schedule_id: str, updates: dict, _=require_principal):
    try:
        return get_lineage_build_timeline_engine().update_schedule(schedule_id, updates)
    except LineageBuildTimelineError as e:
        raise _map_build_err(e) from e


@router.delete("/build/schedules/{schedule_id}")
def delete_build_schedule(schedule_id: str, _=require_principal):
    return {"deleted": get_lineage_build_timeline_engine().delete_schedule(schedule_id)}


@router.post("/build/schedules/{schedule_id}/next-run")
def compute_next_run(schedule_id: str, _=require_principal):
    try:
        next_run = get_lineage_build_timeline_engine().compute_next_run(schedule_id)
        return {"schedule_id": schedule_id, "next_run_at": next_run}
    except LineageBuildTimelineError as e:
        raise _map_build_err(e) from e


@router.post("/build/schedules/{schedule_id}/trigger", response_model=BuildRun)
def trigger_build_run(schedule_id: str, _=require_principal):
    try:
        return get_lineage_build_timeline_engine().trigger_run(schedule_id)
    except LineageBuildTimelineError as e:
        raise _map_build_err(e) from e


@router.get("/build/runs/{run_id}", response_model=BuildRun)
def get_build_run(run_id: str, _=require_principal):
    try:
        return get_lineage_build_timeline_engine().get_run(run_id)
    except LineageBuildTimelineError as e:
        raise _map_build_err(e) from e


@router.get("/build/runs", response_model=list[BuildRun])
def list_build_runs(
    schedule_id: str,
    limit: int = Query(20, ge=1, le=200),
    _=require_principal,
):
    return get_lineage_build_timeline_engine().list_runs(schedule_id, limit=limit)


@router.post("/build/schedules/{schedule_id}/pause", response_model=BuildSchedule)
def pause_build_schedule(schedule_id: str, _=require_principal):
    try:
        return get_lineage_build_timeline_engine().pause_schedule(schedule_id)
    except LineageBuildTimelineError as e:
        raise _map_build_err(e) from e


@router.post("/build/schedules/{schedule_id}/resume", response_model=BuildSchedule)
def resume_build_schedule(schedule_id: str, _=require_principal):
    try:
        return get_lineage_build_timeline_engine().resume_schedule(schedule_id)
    except LineageBuildTimelineError as e:
        raise _map_build_err(e) from e


@router.get("/build/gantt", response_model=GanttChart)
def get_build_gantt(
    start_date: date,
    end_date: date,
    pipeline_id: str | None = None,
    _=require_principal,
):
    return get_lineage_build_timeline_engine().get_gantt_chart(
        start_date, end_date, pipeline_id
    )
