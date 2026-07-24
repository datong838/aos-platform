"""W2-AH · Data Connection 文件处理组路由：#116 FileFilter + #117 FileTransform + #118 StreamingSync."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.file_processing import (
    FileEntry,
    FileFilterRule,
    FileProcessingError,
    FileTransform,
    StreamEvent,
    StreamingSync,
    get_filter_engine,
    get_streaming_engine,
    get_transform_engine,
)
from aos_api.logging_facade import get_logger

router = APIRouter(tags=["file-processing"])
log = get_logger("aos-api.file-processing")


def _map_err(err: FileProcessingError, status: int = 400) -> ApiError:
    if err.code == "NOT_FOUND":
        status = 404
    return ApiError(code=err.code, message=err.message, status_code=status)


# ════════════════════ #116 FileFilter ════════════════════

class FileFilterIn(BaseModel):
    name: str = Field(min_length=1)
    path_pattern: str = ""
    min_size_bytes: int = 0
    max_size_bytes: int = 0
    modified_after: float = 0.0
    modified_before: float = 0.0
    exclude_synced: bool = False


class FileFilterUpdateIn(BaseModel):
    name: str | None = None
    path_pattern: str | None = None
    min_size_bytes: int | None = None
    max_size_bytes: int | None = None
    modified_after: float | None = None
    modified_before: float | None = None
    exclude_synced: bool | None = None


class ApplyFilterIn(BaseModel):
    files: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/v1/file-filters")
def register_filter(
    body: FileFilterIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#116 · 注册文件筛选规则。"""
    _ = principal
    try:
        rule = get_filter_engine().register(FileFilterRule(**body.model_dump()))
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": rule.model_dump()}


@router.get("/v1/file-filters")
def list_filters(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#116 · 筛选规则列表。"""
    _ = principal
    items = get_filter_engine().list()
    return {"items": [r.model_dump() for r in items], "count": len(items)}


@router.get("/v1/file-filters/{filter_id}")
def get_filter(
    filter_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#116 · 单条筛选规则。"""
    _ = principal
    try:
        return {"item": get_filter_engine().get(filter_id).model_dump()}
    except FileProcessingError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/file-filters/{filter_id}")
def update_filter(
    filter_id: str, body: FileFilterUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#116 · 更新筛选规则。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        r = get_filter_engine().update(filter_id, updates)
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": r.model_dump()}


@router.delete("/v1/file-filters/{filter_id}")
def delete_filter(
    filter_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#116 · 删除筛选规则。"""
    _ = principal
    ok = get_filter_engine().delete(filter_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"筛选规则 {filter_id} 不存在", status_code=404)
    return {"id": filter_id, "deleted": True}


@router.post("/v1/file-filters/{filter_id}/apply")
def apply_filter(
    filter_id: str, body: ApplyFilterIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#116 · 应用筛选规则。"""
    _ = principal
    try:
        files = [FileEntry(**f) for f in body.files]
        result = get_filter_engine().apply_filter(filter_id, files)
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": result.model_dump()}


# ════════════════════ #117 FileTransform ════════════════════

class FileTransformIn(BaseModel):
    name: str = Field(min_length=1)
    transform_type: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class FileTransformUpdateIn(BaseModel):
    name: str | None = None
    transform_type: str | None = None
    config: dict[str, Any] | None = None


class ApplyTransformIn(BaseModel):
    input_files: list[str] = Field(default_factory=list)


@router.post("/v1/file-transforms")
def register_transform(
    body: FileTransformIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#117 · 注册文件变换。"""
    _ = principal
    try:
        t = get_transform_engine().register(FileTransform(**body.model_dump()))
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": t.model_dump()}


@router.get("/v1/file-transforms")
def list_transforms(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#117 · 变换列表。"""
    _ = principal
    items = get_transform_engine().list()
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.get("/v1/file-transforms/{transform_id}")
def get_transform(
    transform_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#117 · 单条变换。"""
    _ = principal
    try:
        return {"item": get_transform_engine().get(transform_id).model_dump()}
    except FileProcessingError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/file-transforms/{transform_id}")
def update_transform(
    transform_id: str, body: FileTransformUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#117 · 更新变换。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        t = get_transform_engine().update(transform_id, updates)
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": t.model_dump()}


@router.delete("/v1/file-transforms/{transform_id}")
def delete_transform(
    transform_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#117 · 删除变换。"""
    _ = principal
    ok = get_transform_engine().delete(transform_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"变换 {transform_id} 不存在", status_code=404)
    return {"id": transform_id, "deleted": True}


@router.post("/v1/file-transforms/{transform_id}/apply")
def apply_transform(
    transform_id: str, body: ApplyTransformIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#117 · 应用文件变换。"""
    _ = principal
    try:
        result = get_transform_engine().apply_transform(
            transform_id, body.input_files,
        )
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": result.model_dump()}


# ════════════════════ #118 StreamingSync ════════════════════

class StreamingSyncIn(BaseModel):
    name: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_config: dict[str, Any] = Field(default_factory=dict)
    target_stream: str = ""


class StreamingSyncUpdateIn(BaseModel):
    name: str | None = None
    source_type: str | None = None
    source_config: dict[str, Any] | None = None
    target_stream: str | None = None
    status: str | None = None


class ConsumeEventsIn(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/v1/streaming-syncs")
def register_sync(
    body: StreamingSyncIn, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#118 · 注册流同步。"""
    _ = principal
    try:
        s = get_streaming_engine().register(StreamingSync(**body.model_dump()))
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.get("/v1/streaming-syncs")
def list_syncs(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#118 · 流同步列表。"""
    _ = principal
    items = get_streaming_engine().list()
    return {"items": [s.model_dump() for s in items], "count": len(items)}


@router.get("/v1/streaming-syncs/{sync_id}")
def get_sync(
    sync_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#118 · 单条流同步。"""
    _ = principal
    try:
        return {"item": get_streaming_engine().get(sync_id).model_dump()}
    except FileProcessingError as exc:
        raise _map_err(exc) from exc


@router.put("/v1/streaming-syncs/{sync_id}")
def update_sync(
    sync_id: str, body: StreamingSyncUpdateIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#118 · 更新流同步。"""
    _ = principal
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        s = get_streaming_engine().update(sync_id, updates)
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.delete("/v1/streaming-syncs/{sync_id}")
def delete_sync(
    sync_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#118 · 删除流同步。"""
    _ = principal
    ok = get_streaming_engine().delete(sync_id)
    if not ok:
        raise ApiError(code="NOT_FOUND", message=f"同步 {sync_id} 不存在", status_code=404)
    return {"id": sync_id, "deleted": True}


@router.post("/v1/streaming-syncs/{sync_id}/start")
def start_sync(
    sync_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#118 · 启动同步。"""
    _ = principal
    try:
        s = get_streaming_engine().start(sync_id)
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.post("/v1/streaming-syncs/{sync_id}/stop")
def stop_sync(
    sync_id: str, principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#118 · 停止同步。"""
    _ = principal
    try:
        s = get_streaming_engine().stop(sync_id)
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"item": s.model_dump()}


@router.post("/v1/streaming-syncs/{sync_id}/consume")
def consume_events(
    sync_id: str, body: ConsumeEventsIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#118 · 消费流事件。"""
    _ = principal
    try:
        events = [StreamEvent(**e) for e in body.events]
        records = get_streaming_engine().consume(sync_id, events)
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"items": [r.model_dump() for r in records], "count": len(records)}


@router.get("/v1/streaming-syncs/{sync_id}/records")
def list_records(
    sync_id: str, limit: int = 50,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """#118 · 同步记录列表。"""
    _ = principal
    try:
        items = get_streaming_engine().list_records(sync_id, limit=limit)
    except FileProcessingError as exc:
        raise _map_err(exc) from exc
    return {"items": [r.model_dump() for r in items], "count": len(items)}
