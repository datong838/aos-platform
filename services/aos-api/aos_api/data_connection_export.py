"""W2-AI · Data Connection 推送与导出组（#119 #120 #121）.

- PushIngestionEngine：OAuth2/API Key 认证的推送消息接收 + 速率限制
- FileExportEngine：Dataset → S3/ABFS/HDFS 文件导出任务
- TableExportEngine：full/incremental/snapshot 三模式表导出
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from threading import Lock
from typing import Optional

from pydantic import BaseModel, Field

_MAX_SOURCES = 200
_MAX_MESSAGES_PER_SOURCE = 200
_MAX_FILE_EXPORTS = 200
_MAX_TABLE_EXPORTS = 200
_MAX_RUNS_PER_TASK = 200


# ════════════════════ 错误 ════════════════════

class DataConnectionExportError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #119 Push-based Ingestion ════════════════════

_VALID_AUTH_TYPES = {"oauth2_client_credentials", "api_key", "none"}


class PushIngestionSource(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    target_stream: str = ""
    auth_type: str = "none"
    auth_config: dict = Field(default_factory=dict)
    rate_limit_per_minute: int = 60
    enabled: bool = True
    created_at: float = 0.0
    last_received_at: float = 0.0
    total_messages: int = 0
    error_count: int = 0


class PushIngestionMessage(BaseModel):
    message_id: str = ""
    source_id: str
    payload: dict = Field(default_factory=dict)
    received_at: float = 0.0
    status: str = "accepted"
    error_message: str = ""


class PushIngestionResult(BaseModel):
    accepted: int = 0
    rejected: int = 0
    messages: list[PushIngestionMessage] = Field(default_factory=list)


class PushIngestionEngine:
    def __init__(self) -> None:
        self._sources: dict[str, PushIngestionSource] = {}
        self._messages: dict[str, deque[PushIngestionMessage]] = {}
        self._minute_buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    def register(self, source: PushIngestionSource) -> PushIngestionSource:
        if not source.name:
            raise DataConnectionExportError("MISSING_NAME", "name is required")
        if source.auth_type not in _VALID_AUTH_TYPES:
            raise DataConnectionExportError(
                "INVALID_AUTH_TYPE",
                f"auth_type must be one of {_VALID_AUTH_TYPES}",
            )
        if source.rate_limit_per_minute <= 0:
            raise DataConnectionExportError(
                "INVALID_RATE_LIMIT", "rate_limit_per_minute must be > 0"
            )
        with self._lock:
            source.id = f"pis-{uuid.uuid4().hex[:8]}"
            source.created_at = time.time()
            self._sources[source.id] = source
            self._messages[source.id] = deque(maxlen=_MAX_MESSAGES_PER_SOURCE)
            self._minute_buckets[source.id] = deque()
            if len(self._sources) > _MAX_SOURCES:
                oldest = min(self._sources.values(), key=lambda s: s.created_at)
                self._sources.pop(oldest.id, None)
                self._messages.pop(oldest.id, None)
                self._minute_buckets.pop(oldest.id, None)
            return source.model_copy(deep=True)

    def get(self, source_id: str) -> PushIngestionSource:
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                raise DataConnectionExportError("NOT_FOUND", f"source {source_id} not found")
            return s.model_copy(deep=True)

    def list(
        self,
        name: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> list[PushIngestionSource]:
        with self._lock:
            result = list(self._sources.values())
            if name:
                result = [s for s in result if name in s.name]
            if enabled is not None:
                result = [s for s in result if s.enabled == enabled]
            return [s.model_copy(deep=True) for s in result]

    def update(self, source_id: str, updates: dict) -> PushIngestionSource:
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                raise DataConnectionExportError("NOT_FOUND", f"source {source_id} not found")
            data = s.model_dump()
            data.update({k: v for k, v in updates.items() if k in {
                "name", "description", "target_stream", "auth_type",
                "auth_config", "rate_limit_per_minute", "enabled",
            }})
            if not data["name"]:
                raise DataConnectionExportError("MISSING_NAME", "name is required")
            if data["auth_type"] not in _VALID_AUTH_TYPES:
                raise DataConnectionExportError(
                    "INVALID_AUTH_TYPE", f"auth_type must be one of {_VALID_AUTH_TYPES}"
                )
            if data["rate_limit_per_minute"] <= 0:
                raise DataConnectionExportError(
                    "INVALID_RATE_LIMIT", "rate_limit_per_minute must be > 0"
                )
            updated = PushIngestionSource(**data)
            self._sources[source_id] = updated
            return updated.model_copy(deep=True)

    def delete(self, source_id: str) -> bool:
        with self._lock:
            if source_id in self._sources:
                del self._sources[source_id]
                self._messages.pop(source_id, None)
                self._minute_buckets.pop(source_id, None)
                return True
            return False

    def _check_rate_limit(self, source_id: str, now: float) -> bool:
        bucket = self._minute_buckets.get(source_id, deque())
        cutoff = now - 60.0
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        source = self._sources.get(source_id)
        if not source:
            return False
        if len(bucket) >= source.rate_limit_per_minute:
            return False
        bucket.append(now)
        self._minute_buckets[source_id] = bucket
        return True

    def _validate_token_nolock(self, source_id: str, token: str) -> bool:
        s = self._sources.get(source_id)
        if not s:
            return False
        if s.auth_type == "none":
            return True
        if s.auth_type == "api_key":
            expected = s.auth_config.get("api_key", "")
            return bool(token) and token == expected
        if s.auth_type == "oauth2_client_credentials":
            expected_token = s.auth_config.get("expected_token", "")
            return bool(token) and token == expected_token
        return False

    def validate_token(self, source_id: str, token: str) -> bool:
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                raise DataConnectionExportError("NOT_FOUND", f"source {source_id} not found")
            return self._validate_token_nolock(source_id, token)

    def receive_message(
        self,
        source_id: str,
        payload: dict,
        auth_token: str = "",
    ) -> PushIngestionMessage:
        now = time.time()
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                raise DataConnectionExportError("NOT_FOUND", f"source {source_id} not found")
            if not s.enabled:
                raise DataConnectionExportError("SOURCE_DISABLED", "source is disabled")
            if not payload:
                raise DataConnectionExportError("EMPTY_PAYLOAD", "payload cannot be empty")
            if s.auth_type != "none" and not self._validate_token_nolock(source_id, auth_token):
                s.error_count += 1
                raise DataConnectionExportError("AUTH_FAILED", "authentication failed")
            if not self._check_rate_limit(source_id, now):
                s.error_count += 1
                raise DataConnectionExportError("RATE_LIMIT_EXCEEDED", "rate limit exceeded")
            msg = PushIngestionMessage(
                message_id=f"msg-{uuid.uuid4().hex[:8]}",
                source_id=source_id,
                payload=payload,
                received_at=now,
                status="accepted",
            )
            self._messages[source_id].append(msg)
            s.total_messages += 1
            s.last_received_at = now
            return msg.model_copy(deep=True)

    def receive_batch(
        self,
        source_id: str,
        payloads: list[dict],
        auth_token: str = "",
    ) -> PushIngestionResult:
        accepted = 0
        rejected = 0
        messages: list[PushIngestionMessage] = []
        for payload in payloads:
            try:
                msg = self.receive_message(source_id, payload, auth_token)
                accepted += 1
                messages.append(msg)
            except DataConnectionExportError as e:
                rejected += 1
                messages.append(PushIngestionMessage(
                    message_id=f"msg-{uuid.uuid4().hex[:8]}",
                    source_id=source_id,
                    payload=payload,
                    received_at=time.time(),
                    status="rejected",
                    error_message=e.message,
                ))
        return PushIngestionResult(accepted=accepted, rejected=rejected, messages=messages)

    def list_messages(
        self,
        source_id: str,
        limit: int = 50,
    ) -> list[PushIngestionMessage]:
        with self._lock:
            if source_id not in self._sources:
                raise DataConnectionExportError("NOT_FOUND", f"source {source_id} not found")
            msgs = list(self._messages.get(source_id, []))
            msgs.sort(key=lambda m: m.received_at, reverse=True)
            return [m.model_copy(deep=True) for m in msgs[:limit]]


_push_engine: Optional[PushIngestionEngine] = None
_push_lock = Lock()


def get_push_ingestion_engine() -> PushIngestionEngine:
    global _push_engine
    if _push_engine is None:
        with _push_lock:
            if _push_engine is None:
                _push_engine = PushIngestionEngine()
    return _push_engine


# ════════════════════ #120 File Export ════════════════════

_VALID_TARGET_TYPES = {"s3", "abfs", "hdfs"}
_VALID_FILE_FORMATS = {"csv", "parquet", "json", "avro"}
_VALID_COMPRESSIONS = {"none", "gzip", "snappy", "lz4"}


class FileExportTask(BaseModel):
    id: str = ""
    name: str
    dataset_rid: str = ""
    target_type: str = "s3"
    target_path: str = ""
    file_format: str = "csv"
    compression: str = "none"
    row_limit: int = 0
    filter_expr: str = ""
    status: str = "pending"
    total_rows: int = 0
    exported_rows: int = 0
    file_size_bytes: int = 0
    error_message: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    output_files: list[str] = Field(default_factory=list)


class FileExportEngine:
    def __init__(self) -> None:
        self._tasks: dict[str, FileExportTask] = {}
        self._lock = Lock()

    def register(self, task: FileExportTask) -> FileExportTask:
        if not task.name:
            raise DataConnectionExportError("MISSING_NAME", "name is required")
        if not task.dataset_rid:
            raise DataConnectionExportError("MISSING_DATASET_RID", "dataset_rid is required")
        if task.target_type not in _VALID_TARGET_TYPES:
            raise DataConnectionExportError(
                "INVALID_TARGET_TYPE",
                f"target_type must be one of {_VALID_TARGET_TYPES}",
            )
        if task.file_format not in _VALID_FILE_FORMATS:
            raise DataConnectionExportError(
                "INVALID_FORMAT",
                f"file_format must be one of {_VALID_FILE_FORMATS}",
            )
        if task.compression not in _VALID_COMPRESSIONS:
            raise DataConnectionExportError(
                "INVALID_COMPRESSION",
                f"compression must be one of {_VALID_COMPRESSIONS}",
            )
        with self._lock:
            task.id = f"fex-{uuid.uuid4().hex[:8]}"
            task.created_at = time.time()
            self._tasks[task.id] = task
            if len(self._tasks) > _MAX_FILE_EXPORTS:
                oldest = min(self._tasks.values(), key=lambda t: t.created_at)
                self._tasks.pop(oldest.id, None)
            return task.model_copy(deep=True)

    def get(self, task_id: str) -> FileExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            return t.model_copy(deep=True)

    def list(
        self,
        dataset_rid: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[FileExportTask]:
        with self._lock:
            result = list(self._tasks.values())
            if dataset_rid:
                result = [t for t in result if t.dataset_rid == dataset_rid]
            if status:
                result = [t for t in result if t.status == status]
            return [t.model_copy(deep=True) for t in result]

    def update(self, task_id: str, updates: dict) -> FileExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            if t.status != "pending":
                raise DataConnectionExportError(
                    "TASK_NOT_PENDING", "only pending tasks can be updated"
                )
            data = t.model_dump()
            data.update({k: v for k, v in updates.items() if k in {
                "name", "dataset_rid", "target_type", "target_path",
                "file_format", "compression", "row_limit", "filter_expr",
            }})
            if not data["name"]:
                raise DataConnectionExportError("MISSING_NAME", "name is required")
            if not data["dataset_rid"]:
                raise DataConnectionExportError("MISSING_DATASET_RID", "dataset_rid is required")
            if data["target_type"] not in _VALID_TARGET_TYPES:
                raise DataConnectionExportError(
                    "INVALID_TARGET_TYPE", f"target_type must be one of {_VALID_TARGET_TYPES}"
                )
            if data["file_format"] not in _VALID_FILE_FORMATS:
                raise DataConnectionExportError(
                    "INVALID_FORMAT", f"file_format must be one of {_VALID_FILE_FORMATS}"
                )
            if data["compression"] not in _VALID_COMPRESSIONS:
                raise DataConnectionExportError(
                    "INVALID_COMPRESSION", f"compression must be one of {_VALID_COMPRESSIONS}"
                )
            updated = FileExportTask(**data)
            self._tasks[task_id] = updated
            return updated.model_copy(deep=True)

    def delete(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    def start(self, task_id: str) -> FileExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            if t.status != "pending":
                raise DataConnectionExportError(
                    "TASK_NOT_PENDING", "only pending tasks can be started"
                )
            t.status = "running"
            t.started_at = time.time()
            return t.model_copy(deep=True)

    def cancel(self, task_id: str) -> FileExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            if t.status != "running":
                raise DataConnectionExportError(
                    "TASK_NOT_RUNNING", "only running tasks can be cancelled"
                )
            t.status = "failed"
            t.error_message = "cancelled by user"
            t.completed_at = time.time()
            return t.model_copy(deep=True)

    def complete(
        self,
        task_id: str,
        exported_rows: int,
        file_size: int,
        output_files: list[str],
    ) -> FileExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            if t.status == "completed":
                raise DataConnectionExportError(
                    "ALREADY_COMPLETED", "task is already completed"
                )
            if t.status != "running":
                raise DataConnectionExportError(
                    "TASK_NOT_RUNNING", "only running tasks can be completed"
                )
            t.status = "completed"
            t.exported_rows = exported_rows
            t.file_size_bytes = file_size
            t.output_files = output_files
            t.completed_at = time.time()
            return t.model_copy(deep=True)

    def fail(self, task_id: str, error_message: str) -> FileExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            if t.status == "completed":
                raise DataConnectionExportError(
                    "ALREADY_COMPLETED", "task is already completed"
                )
            t.status = "failed"
            t.error_message = error_message
            t.completed_at = time.time()
            return t.model_copy(deep=True)

    def get_progress(self, task_id: str) -> dict:
        t = self.get(task_id)
        pct = 0.0
        if t.total_rows > 0:
            pct = round(t.exported_rows / t.total_rows * 100, 2)
        return {
            "status": t.status,
            "total_rows": t.total_rows,
            "exported_rows": t.exported_rows,
            "progress_percent": pct,
        }


_file_export_engine: Optional[FileExportEngine] = None
_file_export_lock = Lock()


def get_file_export_engine() -> FileExportEngine:
    global _file_export_engine
    if _file_export_engine is None:
        with _file_export_lock:
            if _file_export_engine is None:
                _file_export_engine = FileExportEngine()
    return _file_export_engine


# ════════════════════ #121 Table Export ════════════════════

_VALID_EXPORT_MODES = {"full", "incremental", "snapshot"}


class TableExportTask(BaseModel):
    id: str = ""
    name: str
    source_dataset_rid: str = ""
    target_table: str = ""
    export_mode: str = "full"
    primary_keys: list[str] = Field(default_factory=list)
    watermark_column: str = ""
    last_watermark: str = ""
    truncate_on_snapshot: bool = True
    status: str = "pending"
    total_rows: int = 0
    processed_rows: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0
    deleted_rows: int = 0
    error_message: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0


class TableExportRun(BaseModel):
    run_id: str = ""
    task_id: str
    mode: str = "full"
    status: str = "running"
    started_at: float = 0.0
    completed_at: float = 0.0
    rows_processed: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_deleted: int = 0
    error_message: str = ""
    watermark_before: str = ""
    watermark_after: str = ""
    truncated: bool = False


class TableExportEngine:
    def __init__(self) -> None:
        self._tasks: dict[str, TableExportTask] = {}
        self._runs: dict[str, deque[TableExportRun]] = {}
        self._lock = Lock()

    def register(self, task: TableExportTask) -> TableExportTask:
        if not task.name:
            raise DataConnectionExportError("MISSING_NAME", "name is required")
        if not task.source_dataset_rid:
            raise DataConnectionExportError("MISSING_DATASET", "source_dataset_rid is required")
        if task.export_mode not in _VALID_EXPORT_MODES:
            raise DataConnectionExportError(
                "INVALID_MODE",
                f"export_mode must be one of {_VALID_EXPORT_MODES}",
            )
        if task.export_mode == "incremental" and not task.watermark_column:
            raise DataConnectionExportError(
                "INCREMENTAL_REQUIRES_WATERMARK",
                "incremental mode requires watermark_column",
            )
        with self._lock:
            task.id = f"tex-{uuid.uuid4().hex[:8]}"
            task.created_at = time.time()
            self._tasks[task.id] = task
            self._runs[task.id] = deque(maxlen=_MAX_RUNS_PER_TASK)
            if len(self._tasks) > _MAX_TABLE_EXPORTS:
                oldest = min(self._tasks.values(), key=lambda t: t.created_at)
                self._tasks.pop(oldest.id, None)
                self._runs.pop(oldest.id, None)
            return task.model_copy(deep=True)

    def get(self, task_id: str) -> TableExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            return t.model_copy(deep=True)

    def list(
        self,
        dataset_rid: Optional[str] = None,
        status: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> list[TableExportTask]:
        with self._lock:
            result = list(self._tasks.values())
            if dataset_rid:
                result = [t for t in result if t.source_dataset_rid == dataset_rid]
            if status:
                result = [t for t in result if t.status == status]
            if mode:
                result = [t for t in result if t.export_mode == mode]
            return [t.model_copy(deep=True) for t in result]

    def update(self, task_id: str, updates: dict) -> TableExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            data = t.model_dump()
            data.update({k: v for k, v in updates.items() if k in {
                "name", "source_dataset_rid", "target_table", "export_mode",
                "primary_keys", "watermark_column", "truncate_on_snapshot",
            }})
            if not data["name"]:
                raise DataConnectionExportError("MISSING_NAME", "name is required")
            if not data["source_dataset_rid"]:
                raise DataConnectionExportError("MISSING_DATASET", "source_dataset_rid is required")
            if data["export_mode"] not in _VALID_EXPORT_MODES:
                raise DataConnectionExportError(
                    "INVALID_MODE", f"export_mode must be one of {_VALID_EXPORT_MODES}"
                )
            if data["export_mode"] == "incremental" and not data["watermark_column"]:
                raise DataConnectionExportError(
                    "INCREMENTAL_REQUIRES_WATERMARK",
                    "incremental mode requires watermark_column",
                )
            updated = TableExportTask(**data)
            self._tasks[task_id] = updated
            return updated.model_copy(deep=True)

    def delete(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                self._runs.pop(task_id, None)
                return True
            return False

    def start_run(self, task_id: str) -> TableExportRun:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            run = TableExportRun(
                run_id=f"ter-{uuid.uuid4().hex[:8]}",
                task_id=task_id,
                mode=t.export_mode,
                status="running",
                started_at=time.time(),
                watermark_before=t.last_watermark,
                truncated=(t.export_mode == "snapshot" and t.truncate_on_snapshot),
            )
            self._runs[task_id].append(run)
            t.status = "running"
            t.started_at = run.started_at
            return run.model_copy(deep=True)

    def complete_run(self, run_id: str, stats: dict) -> TableExportRun:
        with self._lock:
            for task_id, runs in self._runs.items():
                for run in runs:
                    if run.run_id == run_id:
                        if run.status == "completed":
                            raise DataConnectionExportError(
                                "ALREADY_COMPLETED", "run is already completed"
                            )
                        if run.status != "running":
                            raise DataConnectionExportError(
                                "RUN_NOT_RUNNING", "only running runs can be completed"
                            )
                        run.status = "completed"
                        run.completed_at = time.time()
                        run.rows_processed = stats.get("rows_processed", 0)
                        run.rows_inserted = stats.get("rows_inserted", 0)
                        run.rows_updated = stats.get("rows_updated", 0)
                        run.rows_deleted = stats.get("rows_deleted", 0)
                        new_watermark = stats.get("watermark", "")
                        if new_watermark:
                            run.watermark_after = new_watermark
                            task = self._tasks.get(task_id)
                            if task:
                                task.last_watermark = new_watermark
                                task.processed_rows += run.rows_processed
                                task.inserted_rows += run.rows_inserted
                                task.updated_rows += run.rows_updated
                                task.deleted_rows += run.rows_deleted
                                task.status = "pending"
                                task.completed_at = run.completed_at
                        else:
                            task = self._tasks.get(task_id)
                            if task:
                                task.processed_rows += run.rows_processed
                                task.inserted_rows += run.rows_inserted
                                task.updated_rows += run.rows_updated
                                task.deleted_rows += run.rows_deleted
                                task.status = "pending"
                                task.completed_at = run.completed_at
                        return run.model_copy(deep=True)
            raise DataConnectionExportError("RUN_NOT_FOUND", f"run {run_id} not found")

    def fail_run(self, run_id: str, error_message: str) -> TableExportRun:
        with self._lock:
            for task_id, runs in self._runs.items():
                for run in runs:
                    if run.run_id == run_id:
                        if run.status == "completed":
                            raise DataConnectionExportError(
                                "ALREADY_COMPLETED", "run is already completed"
                            )
                        run.status = "failed"
                        run.error_message = error_message
                        run.completed_at = time.time()
                        task = self._tasks.get(task_id)
                        if task:
                            task.status = "failed"
                            task.error_message = error_message
                            task.completed_at = run.completed_at
                        return run.model_copy(deep=True)
            raise DataConnectionExportError("RUN_NOT_FOUND", f"run {run_id} not found")

    def list_runs(
        self,
        task_id: str,
        limit: int = 20,
    ) -> list[TableExportRun]:
        with self._lock:
            if task_id not in self._tasks:
                raise DataConnectionExportError("NOT_FOUND", f"task {task_id} not found")
            runs = list(self._runs.get(task_id, []))
            runs.sort(key=lambda r: r.started_at, reverse=True)
            return [r.model_copy(deep=True) for r in runs[:limit]]

    def get_latest_run(self, task_id: str) -> Optional[TableExportRun]:
        runs = self.list_runs(task_id, limit=1)
        return runs[0] if runs else None


_table_export_engine: Optional[TableExportEngine] = None
_table_export_lock = Lock()


def get_table_export_engine() -> TableExportEngine:
    global _table_export_engine
    if _table_export_engine is None:
        with _table_export_lock:
            if _table_export_engine is None:
                _table_export_engine = TableExportEngine()
    return _table_export_engine
