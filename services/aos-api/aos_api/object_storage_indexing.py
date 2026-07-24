"""Object Storage Indexing — 三层索引引擎：存储索引、增量索引、流式索引。

- ObjectStorageEngine: 专职 Object 存储后端索引管理
- DeltaIndexEngine: 基于 Diff 的对象增量索引
- StreamIndexEngine: 流式对象索引管道
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

MAX_ENTRIES = 200


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


IndexType = Literal["primary", "secondary", "composite"]
IndexStatus = Literal["active", "building", "rebuilding", "disabled"]
DeltaStatus = Literal["pending", "applied", "reverted"]
SourceType = Literal["kafka", "flink", "cdc"]
PipelineStatus = Literal["running", "stopped", "paused", "error"]


class ObjectIndex(BaseModel):
    index_id: str = Field(default_factory=lambda: "osi-" + uuid.uuid4().hex[:8])
    object_type: str = ""
    index_name: str = ""
    index_type: IndexType = "secondary"
    fields: list[str] = Field(default_factory=list)
    shard_count: int = 1
    replication_factor: int = 1
    status: IndexStatus = "building"
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class StorageStats(BaseModel):
    object_type: str = ""
    total_objects: int = 0
    index_size_bytes: int = 0
    query_count: int = 0
    last_query_at: str | None = None
    created_at: str = Field(default_factory=_now_iso)


class ObjectStorageError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ObjectStorageEngine:
    _instance: "ObjectStorageEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ObjectStorageEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._indices: dict[str, ObjectIndex] = {}
        self._stats: dict[str, StorageStats] = {}
        self._lock = threading.Lock()

    def create_index(self, object_type: str, index_name: str, index_type: IndexType, **kwargs) -> ObjectIndex:
        if not object_type:
            raise ObjectStorageError("MISSING_OBJECT_TYPE", "object_type 不能为空")
        if not index_name:
            raise ObjectStorageError("MISSING_INDEX_NAME", "index_name 不能为空")
        if index_type not in ("primary", "secondary", "composite"):
            raise ObjectStorageError("INVALID_INDEX_TYPE", f"无效的 index_type: {index_type}")

        index = ObjectIndex(
            object_type=object_type,
            index_name=index_name,
            index_type=index_type,
            **kwargs,
        )
        index.created_at = _now_iso()
        index.updated_at = _now_iso()

        with self._lock:
            self._indices[index.index_id] = index
            self._trim_fifo()
            if object_type not in self._stats:
                self._stats[object_type] = StorageStats(object_type=object_type)

        return index

    def get_index(self, index_id: str) -> ObjectIndex | None:
        return self._indices.get(index_id)

    def list_indices(self, object_type: str | None = None, index_type: IndexType | None = None, status: IndexStatus | None = None) -> list[ObjectIndex]:
        result = list(self._indices.values())
        if object_type:
            result = [i for i in result if i.object_type == object_type]
        if index_type:
            result = [i for i in result if i.index_type == index_type]
        if status:
            result = [i for i in result if i.status == status]
        return result

    def update_index(self, index_id: str, **kwargs) -> ObjectIndex:
        with self._lock:
            index = self._indices.get(index_id)
            if index is None:
                raise ObjectStorageError("NOT_FOUND", f"索引 {index_id} 不存在")
            for k, v in kwargs.items():
                if hasattr(index, k):
                    setattr(index, k, v)
            index.updated_at = _now_iso()
            return index

    def delete_index(self, index_id: str) -> bool:
        with self._lock:
            return self._indices.pop(index_id, None) is not None

    def rebuild_index(self, index_id: str) -> ObjectIndex:
        return self.update_index(index_id, status="rebuilding")

    def get_stats(self, object_type: str) -> StorageStats:
        return self._stats.get(object_type, StorageStats(object_type=object_type))

    def _trim_fifo(self) -> None:
        if len(self._indices) > MAX_ENTRIES:
            oldest = sorted(self._indices.values(), key=lambda x: x.created_at)[: len(self._indices) - MAX_ENTRIES]
            for idx in oldest:
                self._indices.pop(idx.index_id)


class DeltaIndex(BaseModel):
    delta_id: str = Field(default_factory=lambda: "di-" + uuid.uuid4().hex[:8])
    object_type: str = ""
    base_version: int = 0
    delta_version: int = 0
    changed_objects: list[dict[str, Any]] = Field(default_factory=list)
    deleted_objects: list[str] = Field(default_factory=list)
    status: DeltaStatus = "pending"
    applied_at: str | None = None
    created_at: str = Field(default_factory=_now_iso)


class DeltaIndexError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class DeltaIndexEngine:
    _instance: "DeltaIndexEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "DeltaIndexEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._deltas: dict[str, DeltaIndex] = {}
        self._lock = threading.Lock()

    def create_delta(self, object_type: str, base_version: int, delta_version: int, **kwargs) -> DeltaIndex:
        if not object_type:
            raise DeltaIndexError("MISSING_OBJECT_TYPE", "object_type 不能为空")
        if delta_version <= base_version:
            raise DeltaIndexError("INVALID_VERSION", "delta_version 必须大于 base_version")

        delta = DeltaIndex(
            object_type=object_type,
            base_version=base_version,
            delta_version=delta_version,
            **kwargs,
        )
        delta.created_at = _now_iso()

        with self._lock:
            self._deltas[delta.delta_id] = delta
            self._trim_fifo()

        return delta

    def get_delta(self, delta_id: str) -> DeltaIndex | None:
        return self._deltas.get(delta_id)

    def list_deltas(self, object_type: str | None = None, status: DeltaStatus | None = None) -> list[DeltaIndex]:
        result = list(self._deltas.values())
        if object_type:
            result = [d for d in result if d.object_type == object_type]
        if status:
            result = [d for d in result if d.status == status]
        return result

    def apply_delta(self, delta_id: str) -> DeltaIndex:
        with self._lock:
            delta = self._deltas.get(delta_id)
            if delta is None:
                raise DeltaIndexError("NOT_FOUND", f"增量 {delta_id} 不存在")
            delta.status = "applied"
            delta.applied_at = _now_iso()
            return delta

    def revert_delta(self, delta_id: str) -> DeltaIndex:
        with self._lock:
            delta = self._deltas.get(delta_id)
            if delta is None:
                raise DeltaIndexError("NOT_FOUND", f"增量 {delta_id} 不存在")
            delta.status = "reverted"
            return delta

    def get_delta_stats(self, object_type: str) -> dict[str, Any]:
        deltas = [d for d in self._deltas.values() if d.object_type == object_type]
        return {
            "object_type": object_type,
            "total_deltas": len(deltas),
            "pending": sum(1 for d in deltas if d.status == "pending"),
            "applied": sum(1 for d in deltas if d.status == "applied"),
            "reverted": sum(1 for d in deltas if d.status == "reverted"),
        }

    def _trim_fifo(self) -> None:
        if len(self._deltas) > MAX_ENTRIES:
            oldest = sorted(self._deltas.values(), key=lambda x: x.created_at)[: len(self._deltas) - MAX_ENTRIES]
            for d in oldest:
                self._deltas.pop(d.delta_id)


class StreamPipeline(BaseModel):
    pipeline_id: str = Field(default_factory=lambda: "sip-" + uuid.uuid4().hex[:8])
    object_type: str = ""
    source_type: SourceType = "kafka"
    source_config: dict[str, Any] = Field(default_factory=dict)
    status: PipelineStatus = "stopped"
    processing_rate: int = 0
    last_processed_at: str | None = None
    error_message: str | None = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class StreamIndexError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class StreamIndexEngine:
    _instance: "StreamIndexEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "StreamIndexEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._pipelines: dict[str, StreamPipeline] = {}
        self._lock = threading.Lock()

    def create_pipeline(self, object_type: str, source_type: SourceType, source_config: dict[str, Any]) -> StreamPipeline:
        if not object_type:
            raise StreamIndexError("MISSING_OBJECT_TYPE", "object_type 不能为空")
        if source_type not in ("kafka", "flink", "cdc"):
            raise StreamIndexError("INVALID_SOURCE_TYPE", f"无效的 source_type: {source_type}")

        pipeline = StreamPipeline(
            object_type=object_type,
            source_type=source_type,
            source_config=source_config,
        )
        pipeline.created_at = _now_iso()
        pipeline.updated_at = _now_iso()

        with self._lock:
            self._pipelines[pipeline.pipeline_id] = pipeline
            self._trim_fifo()

        return pipeline

    def get_pipeline(self, pipeline_id: str) -> StreamPipeline | None:
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self, object_type: str | None = None, source_type: SourceType | None = None, status: PipelineStatus | None = None) -> list[StreamPipeline]:
        result = list(self._pipelines.values())
        if object_type:
            result = [p for p in result if p.object_type == object_type]
        if source_type:
            result = [p for p in result if p.source_type == source_type]
        if status:
            result = [p for p in result if p.status == status]
        return result

    def update_pipeline(self, pipeline_id: str, **kwargs) -> StreamPipeline:
        with self._lock:
            pipeline = self._pipelines.get(pipeline_id)
            if pipeline is None:
                raise StreamIndexError("NOT_FOUND", f"管道 {pipeline_id} 不存在")
            for k, v in kwargs.items():
                if hasattr(pipeline, k):
                    setattr(pipeline, k, v)
            pipeline.updated_at = _now_iso()
            return pipeline

    def delete_pipeline(self, pipeline_id: str) -> bool:
        with self._lock:
            return self._pipelines.pop(pipeline_id, None) is not None

    def start_pipeline(self, pipeline_id: str) -> StreamPipeline:
        return self.update_pipeline(pipeline_id, status="running")

    def stop_pipeline(self, pipeline_id: str) -> StreamPipeline:
        return self.update_pipeline(pipeline_id, status="stopped", error_message=None)

    def pause_pipeline(self, pipeline_id: str) -> StreamPipeline:
        return self.update_pipeline(pipeline_id, status="paused")

    def get_pipeline_stats(self, pipeline_id: str) -> dict[str, Any]:
        pipeline = self._pipelines.get(pipeline_id)
        if pipeline is None:
            raise StreamIndexError("NOT_FOUND", f"管道 {pipeline_id} 不存在")
        return {
            "pipeline_id": pipeline.pipeline_id,
            "object_type": pipeline.object_type,
            "source_type": pipeline.source_type,
            "status": pipeline.status,
            "processing_rate": pipeline.processing_rate,
            "last_processed_at": pipeline.last_processed_at,
            "error_message": pipeline.error_message,
            "created_at": pipeline.created_at,
            "updated_at": pipeline.updated_at,
        }

    def _trim_fifo(self) -> None:
        if len(self._pipelines) > MAX_ENTRIES:
            oldest = sorted(self._pipelines.values(), key=lambda x: x.created_at)[: len(self._pipelines) - MAX_ENTRIES]
            for p in oldest:
                self._pipelines.pop(p.pipeline_id)
