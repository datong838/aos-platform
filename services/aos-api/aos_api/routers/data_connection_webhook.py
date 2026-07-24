"""W2-AJ · Data Connection 流导出与 Webhook 路由（#122 #123 #124）."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from aos_api.auth import require_principal
from aos_api.data_connection_webhook import (
    DataConnectionWebhookError,
    OutputFieldMapping,
    OutputExtractionResult,
    PipelineRun,
    StreamExportEvent,
    StreamExportTask,
    WebhookOutputConfig,
    WebhookPipeline,
    WebhookPipelineStep,
    get_stream_export_engine,
    get_webhook_output_engine,
    get_webhook_pipeline_engine,
)
from aos_api.errors import ApiError

router = APIRouter(tags=["data_connection_webhook"])


def _map_err(e: DataConnectionWebhookError) -> HTTPException:
    mapping = {
        "MISSING_NAME": (400, "缺少名称"),
        "MISSING_SOURCE_STREAM": (400, "缺少源流"),
        "INVALID_TARGET_TYPE": (400, "不支持的目标类型"),
        "INVALID_PARTITION_STRATEGY": (400, "不支持的分区策略"),
        "INVALID_BATCH_SIZE": (400, "批量大小无效"),
        "NOT_FOUND": (404, "资源不存在"),
        "TASK_NOT_STOPPED": (400, "任务未停止"),
        "TASK_NOT_RUNNING": (400, "任务未在运行"),
        "TASK_DISABLED": (400, "任务已禁用"),
        "EMPTY_STEPS": (400, "步骤不能为空"),
        "DUPLICATE_STEP_ID": (400, "步骤 ID 重复"),
        "INVALID_METHOD": (400, "不支持的 HTTP 方法"),
        "INVALID_AUTH_TYPE": (400, "不支持的认证类型"),
        "INVALID_TIMEOUT": (400, "超时时间无效"),
        "STEP_NOT_FOUND": (404, "步骤不存在"),
        "RUN_NOT_FOUND": (404, "执行记录不存在"),
        "PIPELINE_DISABLED": (400, "管道已禁用"),
        "INVALID_ORDER": (400, "顺序无效"),
        "MISSING_WEBHOOK": (400, "缺少 webhook_id"),
        "DUPLICATE_FIELD_ID": (400, "字段 ID 重复"),
        "INVALID_TARGET_TYPE": (400, "不支持的目标类型"),
        "INVALID_SOURCE_PATH": (400, "源路径无效"),
        "FIELD_NOT_FOUND": (404, "字段不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(status_code=status, detail=ApiError(code=e.code, message=msg).model_dump())


# ════════════════════ #122 Stream Export ════════════════════

@router.post("/v1/stream-exports", response_model=StreamExportTask)
def create_stream_export(task: StreamExportTask, _=require_principal):
    try:
        return get_stream_export_engine().register(task)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.get("/v1/stream-exports", response_model=list[StreamExportTask])
def list_stream_exports(
    source_stream: str | None = None,
    status: str | None = None,
    _=require_principal,
):
    return get_stream_export_engine().list(source_stream=source_stream, status=status)


@router.get("/v1/stream-exports/{task_id}", response_model=StreamExportTask)
def get_stream_export(task_id: str, _=require_principal):
    try:
        return get_stream_export_engine().get(task_id)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.patch("/v1/stream-exports/{task_id}", response_model=StreamExportTask)
def update_stream_export(task_id: str, updates: dict, _=require_principal):
    try:
        return get_stream_export_engine().update(task_id, updates)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.delete("/v1/stream-exports/{task_id}")
def delete_stream_export(task_id: str, _=require_principal):
    return {"deleted": get_stream_export_engine().delete(task_id)}


@router.post("/v1/stream-exports/{task_id}/start", response_model=StreamExportTask)
def start_stream_export(task_id: str, _=require_principal):
    try:
        return get_stream_export_engine().start(task_id)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.post("/v1/stream-exports/{task_id}/stop", response_model=StreamExportTask)
def stop_stream_export(task_id: str, _=require_principal):
    try:
        return get_stream_export_engine().stop(task_id)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.post("/v1/stream-exports/{task_id}/publish", response_model=StreamExportEvent)
def publish_stream_event(task_id: str, payload: dict, key: str = Query(""), _=require_principal):
    try:
        return get_stream_export_engine().publish_event(task_id, payload, key)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.post("/v1/stream-exports/{task_id}/publish-batch")
def publish_stream_batch(task_id: str, events: list[dict], _=require_principal):
    try:
        results = get_stream_export_engine().publish_batch(task_id, events)
        return {"published": len(results), "events": [r.model_dump() for r in results]}
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.get("/v1/stream-exports/{task_id}/events", response_model=list[StreamExportEvent])
def list_stream_events(
    task_id: str,
    limit: int = Query(50, ge=1, le=200),
    _=require_principal,
):
    try:
        return get_stream_export_engine().list_events(task_id, limit=limit)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


# ════════════════════ #123 Webhook Pipeline ════════════════════

@router.post("/v1/webhook-pipelines", response_model=WebhookPipeline)
def create_webhook_pipeline(pipeline: WebhookPipeline, _=require_principal):
    try:
        return get_webhook_pipeline_engine().register(pipeline)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.get("/v1/webhook-pipelines", response_model=list[WebhookPipeline])
def list_webhook_pipelines(
    name: str | None = None,
    status: str | None = None,
    _=require_principal,
):
    return get_webhook_pipeline_engine().list(name=name, status=status)


@router.get("/v1/webhook-pipelines/{pipeline_id}", response_model=WebhookPipeline)
def get_webhook_pipeline(pipeline_id: str, _=require_principal):
    try:
        return get_webhook_pipeline_engine().get(pipeline_id)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.patch("/v1/webhook-pipelines/{pipeline_id}", response_model=WebhookPipeline)
def update_webhook_pipeline(pipeline_id: str, updates: dict, _=require_principal):
    try:
        return get_webhook_pipeline_engine().update(pipeline_id, updates)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.delete("/v1/webhook-pipelines/{pipeline_id}")
def delete_webhook_pipeline(pipeline_id: str, _=require_principal):
    return {"deleted": get_webhook_pipeline_engine().delete(pipeline_id)}


@router.post("/v1/webhook-pipelines/{pipeline_id}/steps", response_model=WebhookPipeline)
def add_pipeline_step(pipeline_id: str, step: WebhookPipelineStep, _=require_principal):
    try:
        return get_webhook_pipeline_engine().add_step(pipeline_id, step)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.delete("/v1/webhook-pipelines/{pipeline_id}/steps/{step_id}", response_model=WebhookPipeline)
def remove_pipeline_step(pipeline_id: str, step_id: str, _=require_principal):
    try:
        return get_webhook_pipeline_engine().remove_step(pipeline_id, step_id)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.post("/v1/webhook-pipelines/{pipeline_id}/steps/reorder", response_model=WebhookPipeline)
def reorder_pipeline_steps(pipeline_id: str, step_order: list[str], _=require_principal):
    try:
        return get_webhook_pipeline_engine().reorder_steps(pipeline_id, step_order)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.post("/v1/webhook-pipelines/{pipeline_id}/run", response_model=PipelineRun)
def run_webhook_pipeline(pipeline_id: str, initial_input: dict, _=require_principal):
    try:
        return get_webhook_pipeline_engine().run(pipeline_id, initial_input)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.get("/v1/webhook-pipelines/{pipeline_id}/runs", response_model=list[PipelineRun])
def list_pipeline_runs(
    pipeline_id: str,
    limit: int = Query(20, ge=1, le=200),
    _=require_principal,
):
    try:
        return get_webhook_pipeline_engine().list_runs(pipeline_id, limit=limit)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.get("/v1/webhook-pipelines/runs/{run_id}", response_model=PipelineRun)
def get_pipeline_run(run_id: str, _=require_principal):
    try:
        return get_webhook_pipeline_engine().get_run(run_id)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


# ════════════════════ #124 Webhook Output ════════════════════

@router.post("/v1/webhook-outputs", response_model=WebhookOutputConfig)
def create_webhook_output(config: WebhookOutputConfig, _=require_principal):
    try:
        return get_webhook_output_engine().register(config)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.get("/v1/webhook-outputs", response_model=list[WebhookOutputConfig])
def list_webhook_outputs(
    webhook_id: str | None = None,
    name: str | None = None,
    _=require_principal,
):
    return get_webhook_output_engine().list(webhook_id=webhook_id, name=name)


@router.get("/v1/webhook-outputs/{config_id}", response_model=WebhookOutputConfig)
def get_webhook_output(config_id: str, _=require_principal):
    try:
        return get_webhook_output_engine().get(config_id)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.patch("/v1/webhook-outputs/{config_id}", response_model=WebhookOutputConfig)
def update_webhook_output(config_id: str, updates: dict, _=require_principal):
    try:
        return get_webhook_output_engine().update(config_id, updates)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.delete("/v1/webhook-outputs/{config_id}")
def delete_webhook_output(config_id: str, _=require_principal):
    return {"deleted": get_webhook_output_engine().delete(config_id)}


@router.post("/v1/webhook-outputs/{config_id}/fields", response_model=WebhookOutputConfig)
def add_output_field(config_id: str, field: OutputFieldMapping, _=require_principal):
    try:
        return get_webhook_output_engine().add_field(config_id, field)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.delete("/v1/webhook-outputs/{config_id}/fields/{field_id}", response_model=WebhookOutputConfig)
def remove_output_field(config_id: str, field_id: str, _=require_principal):
    try:
        return get_webhook_output_engine().remove_field(config_id, field_id)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.post("/v1/webhook-outputs/{config_id}/extract", response_model=OutputExtractionResult)
def extract_output_fields(config_id: str, response: dict, _=require_principal):
    try:
        return get_webhook_output_engine().extract(config_id, response)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e


@router.post("/v1/webhook-outputs/{config_id}/validate")
def validate_webhook_response(config_id: str, response: dict, _=require_principal):
    try:
        return get_webhook_output_engine().validate_response(config_id, response)
    except DataConnectionWebhookError as e:
        raise _map_err(e) from e
