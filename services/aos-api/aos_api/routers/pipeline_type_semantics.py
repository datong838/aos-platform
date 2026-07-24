"""W2-Z · Pipeline 类型语义组路由：#94 Pipeline Types + #95 Incremental + #96 Streaming + #97 Compute Profile + #98 Streaming Performance."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.pipeline_type_semantics import (
    ChangeRecord,
    PipelineTypeError,
    PipelineTypeSpec,
    StreamEvent,
    WindowSpec,
    get_incremental_engine,
    get_pipeline_type_engine,
    get_streaming_engine,
    get_compute_profile_engine,
    get_streaming_perf_engine,
)

router = APIRouter(tags=["pipeline-type-semantics"])
log = get_logger("aos-api.pipeline-type-semantics")


def _map_err(err: PipelineTypeError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    elif err.code == "WATERMARK_REGRESS":
        status = 409
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #94 Pipeline Types ════════════════════

class PipelineTypeIn(BaseModel):
    type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    trigger_semantics: str = Field(min_length=1)
    state_machine: list[str] = Field(default_factory=list)
    fault_strategy: str = Field(min_length=1)
    default_write_mode: str = "append"
    supports_checkpoint: bool = False
    supports_windowing: bool = False
    enabled: bool = True


class PipelineTypeUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_semantics: str | None = None
    state_machine: list[str] | None = None
    fault_strategy: str | None = None
    default_write_mode: str | None = None
    supports_checkpoint: bool | None = None
    supports_windowing: bool | None = None
    enabled: bool | None = None


class ValidateRunIn(BaseModel):
    write_mode: str = Field(min_length=1)


@router.post("/v1/pipeline-types")
def register_pipeline_type(
    req: PipelineTypeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#94 · 注册管道类型。"""
    _ = principal
    try:
        spec = PipelineTypeSpec(**req.model_dump())
        out = get_pipeline_type_engine().register(spec)
        return out.model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.get("/v1/pipeline-types")
def list_pipeline_types(
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#94 · 列出管道类型。"""
    _ = principal
    items = get_pipeline_type_engine().list(enabled_only=enabled_only)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/pipeline-types/{ptype}")
def get_pipeline_type(
    ptype: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#94 · 单条管道类型。"""
    _ = principal
    try:
        return get_pipeline_type_engine().get(ptype).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.put("/v1/pipeline-types/{ptype}")
def update_pipeline_type(
    ptype: str,
    req: PipelineTypeUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#94 · 更新管道类型。"""
    _ = principal
    try:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        return get_pipeline_type_engine().update(ptype, updates).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.delete("/v1/pipeline-types/{ptype}")
def delete_pipeline_type(
    ptype: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#94 · 删除管道类型。"""
    _ = principal
    try:
        get_pipeline_type_engine().delete(ptype)
        return {"deleted": ptype}
    except PipelineTypeError as e:
        raise _map_err(e)


@router.post("/v1/pipeline-types/{ptype}/validate-run")
def validate_run(
    ptype: str,
    req: ValidateRunIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#94 · 校验运行（类型与 write_mode 是否匹配）。"""
    _ = principal
    try:
        return get_pipeline_type_engine().validate_run(ptype, req.write_mode)
    except PipelineTypeError as e:
        raise _map_err(e)


# ════════════════════ #95 Incremental Pipeline ════════════════════

class WatermarkIn(BaseModel):
    field: str = Field(min_length=1)
    value: str = ""


class ChangeIn(BaseModel):
    operation: str = Field(min_length=1)
    pk: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    watermark_value: str = ""


class ProcessIncrementIn(BaseModel):
    changes: list[ChangeIn] | None = None


@router.get("/v1/pipelines/{pipeline_id}/watermark")
def get_watermark(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#95 · 获取水位线。"""
    _ = principal
    return get_incremental_engine().get_watermark(pipeline_id).model_dump()


@router.put("/v1/pipelines/{pipeline_id}/watermark")
def set_watermark(
    pipeline_id: str,
    req: WatermarkIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#95 · 设置水位线。"""
    _ = principal
    try:
        return get_incremental_engine().set_watermark(
            pipeline_id, req.field, req.value,
        ).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.post("/v1/pipelines/{pipeline_id}/changes")
def register_change(
    pipeline_id: str,
    req: ChangeIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#95 · 注册变更捕获记录。"""
    _ = principal
    try:
        rec = ChangeRecord(pipeline_id=pipeline_id, **req.model_dump())
        return get_incremental_engine().register_change(rec).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.get("/v1/pipelines/{pipeline_id}/changes")
def list_changes(
    pipeline_id: str,
    op: str | None = None,
    since_watermark: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#95 · 变更列表。"""
    _ = principal
    items = get_incremental_engine().list_changes(
        pipeline_id, op=op, since_watermark=since_watermark, limit=limit,
    )
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.post("/v1/pipelines/{pipeline_id}/checkpoints")
def create_checkpoint(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#95 · 创建检查点。"""
    _ = principal
    try:
        return get_incremental_engine().create_checkpoint(pipeline_id).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.post("/v1/pipelines/checkpoints/{checkpoint_id}/commit")
def commit_checkpoint(
    checkpoint_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#95 · 提交检查点。"""
    _ = principal
    try:
        return get_incremental_engine().commit_checkpoint(checkpoint_id).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.get("/v1/pipelines/{pipeline_id}/checkpoints")
def list_checkpoints(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#95 · 检查点列表。"""
    _ = principal
    items = get_incremental_engine().list_checkpoints(pipeline_id)
    return {"items": [c.model_dump() for c in items], "count": len(items)}


@router.post("/v1/pipelines/{pipeline_id}/process-increment")
def process_increment(
    pipeline_id: str,
    req: ProcessIncrementIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#95 · 增量执行。"""
    _ = principal
    try:
        changes = None
        if req.changes is not None:
            changes = [
                ChangeRecord(pipeline_id=pipeline_id, **c.model_dump())
                for c in req.changes
            ]
        return get_incremental_engine().process_increment(
            pipeline_id, changes,
        ).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


# ════════════════════ #96 Streaming Pipeline ════════════════════

class WindowSpecIn(BaseModel):
    type: str = Field(min_length=1)
    size_ms: int = 0
    slide_ms: int = 0
    gap_ms: int = 0
    watermark_field: str = "event_ts"


class StreamEventIn(BaseModel):
    key: str = Field(min_length=1)
    event_ts: float = 0.0
    payload: dict[str, Any] = Field(default_factory=dict)


class AdvanceWatermarkIn(BaseModel):
    new_watermark: float


@router.post("/v1/pipelines/{pipeline_id}/windows")
def register_window(
    pipeline_id: str,
    req: WindowSpecIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#96 · 注册窗口规格。"""
    _ = principal
    try:
        spec = WindowSpec(**req.model_dump())
        return get_streaming_engine().register_window(pipeline_id, spec).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.get("/v1/pipelines/{pipeline_id}/windows")
def list_windows(
    pipeline_id: str,
    open_only: bool = False,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#96 · 窗口列表。"""
    _ = principal
    items = get_streaming_engine().list_windows(
        pipeline_id, open_only=open_only, limit=limit,
    )
    return {"items": [w.model_dump() for w in items], "count": len(items)}


@router.post("/v1/pipelines/{pipeline_id}/events")
def ingest_event(
    pipeline_id: str,
    req: StreamEventIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#96 · 摄入流事件。"""
    _ = principal
    try:
        evt = StreamEvent(
            pipeline_id=pipeline_id, key=req.key,
            event_ts=req.event_ts, payload=req.payload,
        )
        return get_streaming_engine().ingest(evt).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.get("/v1/pipelines/{pipeline_id}/events")
def list_events(
    pipeline_id: str,
    processed_only: bool = False,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#96 · 事件列表。"""
    _ = principal
    items = get_streaming_engine().list_events(
        pipeline_id, processed_only=processed_only, limit=limit,
    )
    return {"items": [e.model_dump() for e in items], "count": len(items)}


@router.post("/v1/pipelines/{pipeline_id}/advance-watermark")
def advance_watermark(
    pipeline_id: str,
    req: AdvanceWatermarkIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#96 · 推进水位线（关闭到期窗口）。"""
    _ = principal
    try:
        return get_streaming_engine().advance_watermark(
            pipeline_id, req.new_watermark,
        ).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.post("/v1/pipelines/windows/{window_id}/close")
def close_window(
    window_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#96 · 手动关闭窗口。"""
    _ = principal
    try:
        return get_streaming_engine().close_window(window_id).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


# ════════════════════ #97 Compute Profile ════════════════════

class ComputeProfileIn(BaseModel):
    profile: str = Field(min_length=1)
    description: str = ""
    driver_cores: float = 1.0
    driver_memory_mb: int = 2048
    executor_cores: float = 1.0
    executor_memory_mb: int = 4096
    executor_count: int = 2
    external_endpoint: str = ""
    auto_scale: bool = False
    cost_weight: float = 1.0
    enabled: bool = True


class ComputeProfileUpdateIn(BaseModel):
    description: str | None = None
    driver_cores: float | None = None
    driver_memory_mb: int | None = None
    executor_cores: float | None = None
    executor_memory_mb: int | None = None
    executor_count: int | None = None
    external_endpoint: str | None = None
    auto_scale: bool | None = None
    cost_weight: float | None = None
    enabled: bool | None = None


class AssignProfileIn(BaseModel):
    profile: str = Field(min_length=1)


class EstimateCostIn(BaseModel):
    duration_minutes: float = Field(gt=0)


@router.post("/v1/compute-profiles")
def register_compute_profile(
    req: ComputeProfileIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 注册计算配置。"""
    _ = principal
    try:
        from aos_api.pipeline_type_semantics import ComputeProfileSpec
        spec = ComputeProfileSpec(**req.model_dump())
        return get_compute_profile_engine().register(spec).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.get("/v1/compute-profiles")
def list_compute_profiles(
    enabled_only: bool = False,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 列出计算配置。"""
    _ = principal
    items = get_compute_profile_engine().list(enabled_only=enabled_only)
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/compute-profiles/{profile}")
def get_compute_profile(
    profile: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 单条计算配置。"""
    _ = principal
    try:
        return get_compute_profile_engine().get(profile).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.put("/v1/compute-profiles/{profile}")
def update_compute_profile(
    profile: str,
    req: ComputeProfileUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 更新计算配置。"""
    _ = principal
    try:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        return get_compute_profile_engine().update(profile, updates).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.post("/v1/pipelines/{pipeline_id}/compute-profile")
def assign_compute_profile(
    pipeline_id: str,
    req: AssignProfileIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 给管道分配计算配置。"""
    _ = principal
    try:
        return get_compute_profile_engine().assign(pipeline_id, req.profile)
    except PipelineTypeError as e:
        raise _map_err(e)


@router.get("/v1/pipelines/{pipeline_id}/compute-profile")
def get_assigned_profile(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 查询管道的计算配置。"""
    _ = principal
    return get_compute_profile_engine().get_assignment(pipeline_id)


@router.post("/v1/compute-profiles/{profile}/estimate-cost")
def estimate_cost(
    profile: str,
    req: EstimateCostIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#97 · 成本估算。"""
    _ = principal
    try:
        return get_compute_profile_engine().estimate_cost(profile, req.duration_minutes)
    except PipelineTypeError as e:
        raise _map_err(e)


# ════════════════════ #98 Streaming Performance ════════════════════

class BackpressureIn(BaseModel):
    strategy: str = "buffer"
    buffer_size: int = 10000
    high_watermark_pct: float = 80.0
    low_watermark_pct: float = 50.0


class ResourceIn(BaseModel):
    max_in_flight: int = 1000
    max_parallelism: int = 4
    cpu_limit_cores: float = 2.0
    memory_limit_mb: int = 4096
    network_bandwidth_mbps: int = 0


class FaultIn(BaseModel):
    level: str = "at_least_once"
    checkpoint_interval_ms: int = 30000
    max_retries: int = 3
    retry_backoff_ms: int = 1000
    dead_letter_queue: bool = True
    auto_restart: bool = True
    restart_delay_ms: int = 5000


class StreamingPerfConfigIn(BaseModel):
    backpressure: BackpressureIn = Field(default_factory=BackpressureIn)
    resource: ResourceIn = Field(default_factory=ResourceIn)
    fault: FaultIn = Field(default_factory=FaultIn)
    enabled: bool = True


class CheckBackpressureIn(BaseModel):
    current_buffer_usage: int = Field(ge=0)


class RecordLoadIn(BaseModel):
    delta: int


class SendDlqIn(BaseModel):
    event: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1)


@router.put("/v1/pipelines/{pipeline_id}/streaming-perf")
def set_streaming_perf(
    pipeline_id: str,
    req: StreamingPerfConfigIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 设置流式性能配置。"""
    _ = principal
    try:
        from aos_api.pipeline_type_semantics import StreamingPerfConfig
        cfg = StreamingPerfConfig(
            pipeline_id=pipeline_id, **req.model_dump(),
        )
        return get_streaming_perf_engine().set_config(cfg).model_dump()
    except PipelineTypeError as e:
        raise _map_err(e)


@router.get("/v1/pipelines/{pipeline_id}/streaming-perf")
def get_streaming_perf(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 查询流式性能配置。"""
    _ = principal
    return get_streaming_perf_engine().get_config(pipeline_id).model_dump()


@router.post("/v1/pipelines/{pipeline_id}/streaming-perf/backpressure-check")
def check_backpressure(
    pipeline_id: str,
    req: CheckBackpressureIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 检查背压状态。"""
    _ = principal
    return get_streaming_perf_engine().check_backpressure(
        pipeline_id, req.current_buffer_usage,
    )


@router.post("/v1/pipelines/{pipeline_id}/streaming-perf/load")
def record_load(
    pipeline_id: str,
    req: RecordLoadIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 记录负载变化。"""
    _ = principal
    return get_streaming_perf_engine().record_load(pipeline_id, req.delta)


@router.get("/v1/pipelines/{pipeline_id}/streaming-perf/health")
def get_streaming_health(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 查询管道健康状态。"""
    _ = principal
    return get_streaming_perf_engine().get_health(pipeline_id)


@router.post("/v1/pipelines/{pipeline_id}/streaming-perf/dlq")
def send_to_dlq(
    pipeline_id: str,
    req: SendDlqIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 发送到死信队列。"""
    _ = principal
    return get_streaming_perf_engine().send_to_dlq(
        pipeline_id, req.event, req.reason,
    )


@router.get("/v1/pipelines/{pipeline_id}/streaming-perf/dlq")
def list_dlq(
    pipeline_id: str,
    limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#98 · 查询死信队列。"""
    _ = principal
    items = get_streaming_perf_engine().list_dlq(pipeline_id, limit=limit)
    return {"items": items, "count": len(items)}
