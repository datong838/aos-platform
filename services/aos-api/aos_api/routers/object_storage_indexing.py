"""Object Storage Indexing API 路由 — 三层索引引擎：存储索引、增量索引、流式索引。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.object_storage_indexing import (
    DeltaIndex,
    DeltaIndexEngine,
    DeltaIndexError,
    DeltaStatus,
    IndexStatus,
    IndexType,
    ObjectIndex,
    ObjectStorageEngine,
    ObjectStorageError,
    PipelineStatus,
    SourceType,
    StreamIndexEngine,
    StreamIndexError,
    StreamPipeline,
)

router = APIRouter(prefix="/object-storage-indexing", tags=["object-storage-indexing"])


def _map_storage_error(err: ObjectStorageError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_delta_error(err: DeltaIndexError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


def _map_stream_error(err: StreamIndexError) -> ApiError:
    status = 404 if err.code == "NOT_FOUND" else 400
    return ApiError(code=err.code, message=err.message, status_code=status)


class CreateIndexRequest(BaseModel):
    object_type: str = Field(min_length=1)
    index_name: str = Field(min_length=1)
    index_type: IndexType = "secondary"
    fields: list[str] = Field(default_factory=list)
    shard_count: int = 1
    replication_factor: int = 1


class UpdateIndexRequest(BaseModel):
    index_name: str | None = None
    fields: list[str] | None = None
    shard_count: int | None = None
    replication_factor: int | None = None
    status: IndexStatus | None = None


@router.post("/v1/indices")
def create_index(
    body: CreateIndexRequest,
    principal: Principal = Depends(require_principal),
) -> ObjectIndex:
    engine = ObjectStorageEngine()
    try:
        return engine.create_index(
            object_type=body.object_type,
            index_name=body.index_name,
            index_type=body.index_type,
            fields=body.fields,
            shard_count=body.shard_count,
            replication_factor=body.replication_factor,
        )
    except ObjectStorageError as err:
        raise _map_storage_error(err) from err


@router.get("/v1/indices")
def list_indices(
    object_type: str | None = Query(None),
    index_type: IndexType | None = Query(None),
    status: IndexStatus | None = Query(None),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    engine = ObjectStorageEngine()
    items = engine.list_indices(
        object_type=object_type,
        index_type=index_type,
        status=status,
    )
    return {"items": items}


@router.get("/v1/indices/{index_id}")
def get_index(
    index_id: str,
    principal: Principal = Depends(require_principal),
) -> ObjectIndex:
    engine = ObjectStorageEngine()
    index = engine.get_index(index_id)
    if index is None:
        raise ApiError(code="NOT_FOUND", message=f"索引 {index_id} 不存在", status_code=404)
    return index


@router.put("/v1/indices/{index_id}")
def update_index(
    index_id: str,
    body: UpdateIndexRequest,
    principal: Principal = Depends(require_principal),
) -> ObjectIndex:
    engine = ObjectStorageEngine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return engine.update_index(index_id, **updates)
    except ObjectStorageError as err:
        raise _map_storage_error(err) from err


@router.delete("/v1/indices/{index_id}")
def delete_index(
    index_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    engine = ObjectStorageEngine()
    deleted = engine.delete_index(index_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message=f"索引 {index_id} 不存在", status_code=404)
    return {"deleted": True, "index_id": index_id}


@router.post("/v1/indices/{index_id}/rebuild")
def rebuild_index(
    index_id: str,
    principal: Principal = Depends(require_principal),
) -> ObjectIndex:
    engine = ObjectStorageEngine()
    try:
        return engine.rebuild_index(index_id)
    except ObjectStorageError as err:
        raise _map_storage_error(err) from err


@router.get("/v1/indices/stats/{object_type}")
def get_storage_stats(
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    engine = ObjectStorageEngine()
    stats = engine.get_stats(object_type)
    return stats.model_dump()


class CreateDeltaRequest(BaseModel):
    object_type: str = Field(min_length=1)
    base_version: int = Field(ge=0)
    delta_version: int = Field(ge=1)
    changed_objects: list[dict[str, Any]] = Field(default_factory=list)
    deleted_objects: list[str] = Field(default_factory=list)


@router.post("/v1/deltas")
def create_delta(
    body: CreateDeltaRequest,
    principal: Principal = Depends(require_principal),
) -> DeltaIndex:
    engine = DeltaIndexEngine()
    try:
        return engine.create_delta(
            object_type=body.object_type,
            base_version=body.base_version,
            delta_version=body.delta_version,
            changed_objects=body.changed_objects,
            deleted_objects=body.deleted_objects,
        )
    except DeltaIndexError as err:
        raise _map_delta_error(err) from err


@router.get("/v1/deltas")
def list_deltas(
    object_type: str | None = Query(None),
    status: DeltaStatus | None = Query(None),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    engine = DeltaIndexEngine()
    items = engine.list_deltas(object_type=object_type, status=status)
    return {"items": items}


@router.get("/v1/deltas/{delta_id}")
def get_delta(
    delta_id: str,
    principal: Principal = Depends(require_principal),
) -> DeltaIndex:
    engine = DeltaIndexEngine()
    delta = engine.get_delta(delta_id)
    if delta is None:
        raise ApiError(code="NOT_FOUND", message=f"增量 {delta_id} 不存在", status_code=404)
    return delta


@router.post("/v1/deltas/{delta_id}/apply")
def apply_delta(
    delta_id: str,
    principal: Principal = Depends(require_principal),
) -> DeltaIndex:
    engine = DeltaIndexEngine()
    try:
        return engine.apply_delta(delta_id)
    except DeltaIndexError as err:
        raise _map_delta_error(err) from err


@router.post("/v1/deltas/{delta_id}/revert")
def revert_delta(
    delta_id: str,
    principal: Principal = Depends(require_principal),
) -> DeltaIndex:
    engine = DeltaIndexEngine()
    try:
        return engine.revert_delta(delta_id)
    except DeltaIndexError as err:
        raise _map_delta_error(err) from err


@router.get("/v1/deltas/stats/{object_type}")
def get_delta_stats(
    object_type: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    engine = DeltaIndexEngine()
    return engine.get_delta_stats(object_type)


class CreatePipelineRequest(BaseModel):
    object_type: str = Field(min_length=1)
    source_type: SourceType = "kafka"
    source_config: dict[str, Any] = Field(default_factory=dict)


class UpdatePipelineRequest(BaseModel):
    source_config: dict[str, Any] | None = None
    status: PipelineStatus | None = None
    processing_rate: int | None = None


@router.post("/v1/pipelines")
def create_pipeline(
    body: CreatePipelineRequest,
    principal: Principal = Depends(require_principal),
) -> StreamPipeline:
    engine = StreamIndexEngine()
    try:
        return engine.create_pipeline(
            object_type=body.object_type,
            source_type=body.source_type,
            source_config=body.source_config,
        )
    except StreamIndexError as err:
        raise _map_stream_error(err) from err


@router.get("/v1/pipelines")
def list_pipelines(
    object_type: str | None = Query(None),
    source_type: SourceType | None = Query(None),
    status: PipelineStatus | None = Query(None),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    engine = StreamIndexEngine()
    items = engine.list_pipelines(
        object_type=object_type,
        source_type=source_type,
        status=status,
    )
    return {"items": items}


@router.get("/v1/pipelines/{pipeline_id}")
def get_pipeline(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> StreamPipeline:
    engine = StreamIndexEngine()
    pipeline = engine.get_pipeline(pipeline_id)
    if pipeline is None:
        raise ApiError(code="NOT_FOUND", message=f"管道 {pipeline_id} 不存在", status_code=404)
    return pipeline


@router.put("/v1/pipelines/{pipeline_id}")
def update_pipeline(
    pipeline_id: str,
    body: UpdatePipelineRequest,
    principal: Principal = Depends(require_principal),
) -> StreamPipeline:
    engine = StreamIndexEngine()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return engine.update_pipeline(pipeline_id, **updates)
    except StreamIndexError as err:
        raise _map_stream_error(err) from err


@router.delete("/v1/pipelines/{pipeline_id}")
def delete_pipeline(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    engine = StreamIndexEngine()
    deleted = engine.delete_pipeline(pipeline_id)
    if not deleted:
        raise ApiError(code="NOT_FOUND", message=f"管道 {pipeline_id} 不存在", status_code=404)
    return {"deleted": True, "pipeline_id": pipeline_id}


@router.post("/v1/pipelines/{pipeline_id}/start")
def start_pipeline(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> StreamPipeline:
    engine = StreamIndexEngine()
    try:
        return engine.start_pipeline(pipeline_id)
    except StreamIndexError as err:
        raise _map_stream_error(err) from err


@router.post("/v1/pipelines/{pipeline_id}/stop")
def stop_pipeline(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> StreamPipeline:
    engine = StreamIndexEngine()
    try:
        return engine.stop_pipeline(pipeline_id)
    except StreamIndexError as err:
        raise _map_stream_error(err) from err


@router.post("/v1/pipelines/{pipeline_id}/pause")
def pause_pipeline(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> StreamPipeline:
    engine = StreamIndexEngine()
    try:
        return engine.pause_pipeline(pipeline_id)
    except StreamIndexError as err:
        raise _map_stream_error(err) from err


@router.get("/v1/pipelines/{pipeline_id}/stats")
def get_pipeline_stats(
    pipeline_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    engine = StreamIndexEngine()
    try:
        return engine.get_pipeline_stats(pipeline_id)
    except StreamIndexError as err:
        raise _map_stream_error(err) from err
