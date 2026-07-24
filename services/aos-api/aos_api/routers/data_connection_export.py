"""W2-AI · Data Connection 推送与导出路由（#119 #120 #121）."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from aos_api.auth import require_principal
from aos_api.data_connection_export import (
    DataConnectionExportError,
    FileExportTask,
    PushIngestionMessage,
    PushIngestionSource,
    TableExportRun,
    TableExportTask,
    get_file_export_engine,
    get_push_ingestion_engine,
    get_table_export_engine,
)
from aos_api.errors import ApiError

router = APIRouter(tags=["data_connection_export"])


def _map_err(e: DataConnectionExportError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少名称"),
        "INVALID_AUTH_TYPE": (400, "不支持的认证类型"),
        "INVALID_RATE_LIMIT": (400, "速率限制无效"),
        "NOT_FOUND": (404, "资源不存在"),
        "SOURCE_DISABLED": (400, "推送源已禁用"),
        "AUTH_FAILED": (401, "认证失败"),
        "RATE_LIMIT_EXCEEDED": (429, "超出速率限制"),
        "EMPTY_PAYLOAD": (400, "消息 payload 为空"),
        "MISSING_DATASET_RID": (400, "缺少 dataset_rid"),
        "INVALID_TARGET_TYPE": (400, "不支持的目标类型"),
        "INVALID_FORMAT": (400, "不支持的文件格式"),
        "INVALID_COMPRESSION": (400, "不支持的压缩方式"),
        "TASK_NOT_PENDING": (400, "任务未处于 pending 状态"),
        "TASK_NOT_RUNNING": (400, "任务未在运行"),
        "ALREADY_COMPLETED": (400, "任务已完成"),
        "MISSING_DATASET": (400, "缺少数据集"),
        "INVALID_MODE": (400, "不支持的导出模式"),
        "INCREMENTAL_REQUIRES_WATERMARK": (400, "增量模式必须指定 watermark 列"),
        "RUN_NOT_FOUND": (404, "执行记录不存在"),
        "RUN_NOT_RUNNING": (400, "执行未在运行"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


# ════════════════════ #119 Push Ingestion ════════════════════

@router.post("/v1/push-ingestion/sources", response_model=PushIngestionSource)
def create_push_source(source: PushIngestionSource, _=require_principal):
    try:
        return get_push_ingestion_engine().register(source)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.get("/v1/push-ingestion/sources", response_model=list[PushIngestionSource])
def list_push_sources(
    name: str | None = None,
    enabled: bool | None = None,
    _=require_principal,
):
    return get_push_ingestion_engine().list(name=name, enabled=enabled)


@router.get("/v1/push-ingestion/sources/{source_id}", response_model=PushIngestionSource)
def get_push_source(source_id: str, _=require_principal):
    try:
        return get_push_ingestion_engine().get(source_id)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.patch("/v1/push-ingestion/sources/{source_id}", response_model=PushIngestionSource)
def update_push_source(source_id: str, updates: dict, _=require_principal):
    try:
        return get_push_ingestion_engine().update(source_id, updates)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.delete("/v1/push-ingestion/sources/{source_id}")
def delete_push_source(source_id: str, _=require_principal):
    return {"deleted": get_push_ingestion_engine().delete(source_id)}


@router.post("/v1/push-ingestion/sources/{source_id}/receive", response_model=PushIngestionMessage)
def receive_message(source_id: str, payload: dict, auth_token: str = Query(""), _=require_principal):
    try:
        return get_push_ingestion_engine().receive_message(source_id, payload, auth_token)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.post("/v1/push-ingestion/sources/{source_id}/receive-batch")
def receive_batch(source_id: str, payloads: list[dict], auth_token: str = Query(""), _=require_principal):
    return get_push_ingestion_engine().receive_batch(source_id, payloads, auth_token).model_dump()


@router.get("/v1/push-ingestion/sources/{source_id}/messages", response_model=list[PushIngestionMessage])
def list_messages(source_id: str, limit: int = Query(50, ge=1, le=200), _=require_principal):
    try:
        return get_push_ingestion_engine().list_messages(source_id, limit=limit)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


# ════════════════════ #120 File Export ════════════════════

@router.post("/v1/file-exports", response_model=FileExportTask)
def create_file_export(task: FileExportTask, _=require_principal):
    try:
        return get_file_export_engine().register(task)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.get("/v1/file-exports", response_model=list[FileExportTask])
def list_file_exports(
    dataset_rid: str | None = None,
    status: str | None = None,
    _=require_principal,
):
    return get_file_export_engine().list(dataset_rid=dataset_rid, status=status)


@router.get("/v1/file-exports/{task_id}", response_model=FileExportTask)
def get_file_export(task_id: str, _=require_principal):
    try:
        return get_file_export_engine().get(task_id)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.patch("/v1/file-exports/{task_id}", response_model=FileExportTask)
def update_file_export(task_id: str, updates: dict, _=require_principal):
    try:
        return get_file_export_engine().update(task_id, updates)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.delete("/v1/file-exports/{task_id}")
def delete_file_export(task_id: str, _=require_principal):
    return {"deleted": get_file_export_engine().delete(task_id)}


@router.post("/v1/file-exports/{task_id}/start", response_model=FileExportTask)
def start_file_export(task_id: str, _=require_principal):
    try:
        return get_file_export_engine().start(task_id)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.post("/v1/file-exports/{task_id}/cancel", response_model=FileExportTask)
def cancel_file_export(task_id: str, _=require_principal):
    try:
        return get_file_export_engine().cancel(task_id)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.get("/v1/file-exports/{task_id}/progress")
def get_file_export_progress(task_id: str, _=require_principal):
    try:
        return get_file_export_engine().get_progress(task_id)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


# ════════════════════ #121 Table Export ════════════════════

@router.post("/v1/table-exports", response_model=TableExportTask)
def create_table_export(task: TableExportTask, _=require_principal):
    try:
        return get_table_export_engine().register(task)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.get("/v1/table-exports", response_model=list[TableExportTask])
def list_table_exports(
    dataset_rid: str | None = None,
    status: str | None = None,
    mode: str | None = None,
    _=require_principal,
):
    return get_table_export_engine().list(dataset_rid=dataset_rid, status=status, mode=mode)


@router.get("/v1/table-exports/{task_id}", response_model=TableExportTask)
def get_table_export(task_id: str, _=require_principal):
    try:
        return get_table_export_engine().get(task_id)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.patch("/v1/table-exports/{task_id}", response_model=TableExportTask)
def update_table_export(task_id: str, updates: dict, _=require_principal):
    try:
        return get_table_export_engine().update(task_id, updates)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.delete("/v1/table-exports/{task_id}")
def delete_table_export(task_id: str, _=require_principal):
    return {"deleted": get_table_export_engine().delete(task_id)}


@router.post("/v1/table-exports/{task_id}/runs", response_model=TableExportRun)
def start_table_export_run(task_id: str, _=require_principal):
    try:
        return get_table_export_engine().start_run(task_id)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.get("/v1/table-exports/{task_id}/runs", response_model=list[TableExportRun])
def list_table_export_runs(task_id: str, limit: int = Query(20, ge=1, le=200), _=require_principal):
    try:
        return get_table_export_engine().list_runs(task_id, limit=limit)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.get("/v1/table-exports/{task_id}/runs/latest", response_model=TableExportRun)
def get_latest_table_export_run(task_id: str, _=require_principal):
    try:
        run = get_table_export_engine().get_latest_run(task_id)
        if not run:
            raise HTTPException(status_code=404, detail=ApiError(code="NOT_FOUND", message="无执行记录").model_dump())
        return run
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.post("/v1/table-exports/runs/{run_id}/complete", response_model=TableExportRun)
def complete_table_export_run(run_id: str, stats: dict, _=require_principal):
    try:
        return get_table_export_engine().complete_run(run_id, stats)
    except DataConnectionExportError as e:
        raise _map_err(e) from e


@router.post("/v1/table-exports/runs/{run_id}/fail", response_model=TableExportRun)
def fail_table_export_run(run_id: str, error_message: str = Query(""), _=require_principal):
    try:
        return get_table_export_engine().fail_run(run_id, error_message)
    except DataConnectionExportError as e:
        raise _map_err(e) from e
