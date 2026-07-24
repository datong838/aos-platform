"""W2-AH · Data Connection 文件处理组（#116 / #117 / #118）.

- #116 FileFilterEngine：文件筛选（路径正则/大小/修改时间/排除已同步）
- #117 FileTransformEngine：文件变换（Gzip/合并/重命名/PGP解密/附加时间戳）
- #118 StreamingSyncEngine：流同步（Kafka/Kinesis/PubSub → Stream）

详见 docs/palantier/20_tech/220tech_w2-ah-file-processing.md。
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_VALID_TRANSFORM_TYPES = {"gzip", "merge", "rename", "pgp_decrypt", "add_timestamp"}
_VALID_SOURCE_TYPES = {"kafka", "kinesis", "pubsub"}
_VALID_SYNC_STATUSES = {"running", "stopped", "error"}
_VALID_RECORD_STATUSES = {"synced", "failed", "retry"}

_MAX_FILTERS = 200
_MAX_TRANSFORMS = 200
_MAX_SYNCS = 200
_MAX_RECORDS = 200


# ════════════════════ 数据模型 ════════════════════

# ─── #116 FileFilter ───

class FileEntry(BaseModel):
    """文件条目。"""
    path: str
    size_bytes: int = 0
    modified_at: float = 0.0
    is_synced: bool = False


class FileFilterRule(BaseModel):
    """文件筛选规则。"""
    id: str = Field(default_factory=lambda: "ffr-" + uuid.uuid4().hex[:10])
    name: str
    path_pattern: str = ""
    min_size_bytes: int = 0
    max_size_bytes: int = 0
    modified_after: float = 0.0
    modified_before: float = 0.0
    exclude_synced: bool = False
    created_at: float = Field(default_factory=lambda: time.time())


class FilterResult(BaseModel):
    """筛选结果。"""
    filter_id: str
    total_files: int = 0
    matched_files: int = 0
    files: list[FileEntry] = Field(default_factory=list)
    applied_at: float = Field(default_factory=lambda: time.time())


# ─── #117 FileTransform ───

class FileTransform(BaseModel):
    """文件变换配置。"""
    id: str = Field(default_factory=lambda: "ftr-" + uuid.uuid4().hex[:10])
    name: str
    transform_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())


class TransformResult(BaseModel):
    """变换结果。"""
    transform_id: str
    input_files: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    status: str = "success"
    error_message: str = ""
    transformed_at: float = Field(default_factory=lambda: time.time())


# ─── #118 StreamingSync ───

class StreamEvent(BaseModel):
    """流事件。"""
    key: str
    value: str
    timestamp: float = Field(default_factory=lambda: time.time())
    partition: int = 0
    offset: int = 0


class StreamingSync(BaseModel):
    """Streaming Sync 配置。"""
    id: str = Field(default_factory=lambda: "ssy-" + uuid.uuid4().hex[:10])
    name: str
    source_type: str
    source_config: dict[str, Any] = Field(default_factory=dict)
    target_stream: str = ""
    status: str = "stopped"
    offset: int = 0
    last_consumed_at: float = 0.0
    created_at: float = Field(default_factory=lambda: time.time())


class SyncRecord(BaseModel):
    """同步记录。"""
    sync_id: str
    event_key: str
    status: str = "synced"
    error_message: str = ""
    synced_at: float = Field(default_factory=lambda: time.time())


# ════════════════════ 错误 ════════════════════

class FileProcessingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ #116 FileFilterEngine ════════════════════

class FileFilterEngine:
    def __init__(self) -> None:
        self._filters: dict[str, FileFilterRule] = {}
        self._lock = threading.Lock()

    def register(self, rule: FileFilterRule) -> FileFilterRule:
        if not rule.name:
            raise FileProcessingError("MISSING_NAME", "名称不能为空")
        with self._lock:
            if len(self._filters) >= _MAX_FILTERS:
                oldest_id = next(iter(self._filters))
                self._filters.pop(oldest_id, None)
            self._filters[rule.id] = rule
        return rule

    def get(self, filter_id: str) -> FileFilterRule:
        r = self._filters.get(filter_id)
        if r is None:
            raise FileProcessingError("NOT_FOUND", f"筛选规则 {filter_id} 不存在")
        return r

    def list(self) -> list[FileFilterRule]:
        return list(self._filters.values())

    def update(self, filter_id: str, updates: dict[str, Any]) -> FileFilterRule:
        r = self.get(filter_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if hasattr(r, k):
                setattr(r, k, v)
        return r

    def delete(self, filter_id: str) -> bool:
        return self._filters.pop(filter_id, None) is not None

    def apply_filter(
        self, filter_id: str, files: list[FileEntry],
    ) -> FilterResult:
        rule = self.get(filter_id)
        matched: list[FileEntry] = []
        pattern = re.compile(rule.path_pattern) if rule.path_pattern else None

        for f in files:
            # 路径正则
            if pattern and not pattern.search(f.path):
                continue
            # 大小下限
            if rule.min_size_bytes > 0 and f.size_bytes < rule.min_size_bytes:
                continue
            # 大小上限（0 表示不限）
            if rule.max_size_bytes > 0 and f.size_bytes > rule.max_size_bytes:
                continue
            # 修改时间下限（0 表示不限）
            if rule.modified_after > 0 and f.modified_at < rule.modified_after:
                continue
            # 修改时间上限（0 表示不限）
            if rule.modified_before > 0 and f.modified_at > rule.modified_before:
                continue
            # 排除已同步
            if rule.exclude_synced and f.is_synced:
                continue
            matched.append(f)

        return FilterResult(
            filter_id=filter_id,
            total_files=len(files),
            matched_files=len(matched),
            files=matched,
        )


# ════════════════════ #117 FileTransformEngine ════════════════════

class FileTransformEngine:
    def __init__(self) -> None:
        self._transforms: dict[str, FileTransform] = {}
        self._lock = threading.Lock()

    def register(self, transform: FileTransform) -> FileTransform:
        if not transform.name:
            raise FileProcessingError("MISSING_NAME", "名称不能为空")
        if transform.transform_type not in _VALID_TRANSFORM_TYPES:
            raise FileProcessingError(
                "INVALID_TRANSFORM_TYPE",
                f"未知变换类型：{transform.transform_type}",
            )
        with self._lock:
            if len(self._transforms) >= _MAX_TRANSFORMS:
                oldest_id = next(iter(self._transforms))
                self._transforms.pop(oldest_id, None)
            self._transforms[transform.id] = transform
        return transform

    def get(self, transform_id: str) -> FileTransform:
        t = self._transforms.get(transform_id)
        if t is None:
            raise FileProcessingError("NOT_FOUND", f"变换 {transform_id} 不存在")
        return t

    def list(self) -> list[FileTransform]:
        return list(self._transforms.values())

    def update(
        self, transform_id: str, updates: dict[str, Any],
    ) -> FileTransform:
        t = self.get(transform_id)
        if "transform_type" in updates:
            if updates["transform_type"] not in _VALID_TRANSFORM_TYPES:
                raise FileProcessingError(
                    "INVALID_TRANSFORM_TYPE",
                    f"未知变换类型：{updates['transform_type']}",
                )
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if hasattr(t, k):
                setattr(t, k, v)
        return t

    def delete(self, transform_id: str) -> bool:
        return self._transforms.pop(transform_id, None) is not None

    def apply_transform(
        self, transform_id: str, input_files: list[str],
    ) -> TransformResult:
        t = self.get(transform_id)
        output_files: list[str] = []

        if not input_files:
            return TransformResult(
                transform_id=transform_id,
                input_files=[], output_files=[],
                status="skipped",
            )

        ttype = t.transform_type
        if ttype == "gzip":
            output_files = [f + ".gz" for f in input_files]
        elif ttype == "merge":
            output_files = [f"merged_{transform_id[:8]}.dat"]
        elif ttype == "rename":
            pattern = t.config.get("pattern", "renamed_{name}")
            for f in input_files:
                base = f.rsplit("/", 1)[-1]
                output_files.append(pattern.replace("{name}", base))
        elif ttype == "pgp_decrypt":
            output_files = [f + ".decrypted" for f in input_files]
        elif ttype == "add_timestamp":
            ts = str(int(time.time()))
            output_files = [f"{ts}_{f}" for f in input_files]

        return TransformResult(
            transform_id=transform_id,
            input_files=list(input_files),
            output_files=output_files,
            status="success",
        )


# ════════════════════ #118 StreamingSyncEngine ════════════════════

class StreamingSyncEngine:
    def __init__(self) -> None:
        self._syncs: dict[str, StreamingSync] = {}
        self._records: dict[str, list[SyncRecord]] = {}
        self._lock = threading.Lock()

    def register(self, sync: StreamingSync) -> StreamingSync:
        if not sync.name:
            raise FileProcessingError("MISSING_NAME", "名称不能为空")
        if sync.source_type not in _VALID_SOURCE_TYPES:
            raise FileProcessingError(
                "INVALID_SOURCE_TYPE",
                f"未知源类型：{sync.source_type}",
            )
        with self._lock:
            if len(self._syncs) >= _MAX_SYNCS:
                oldest_id = next(iter(self._syncs))
                self._syncs.pop(oldest_id, None)
                self._records.pop(oldest_id, None)
            self._syncs[sync.id] = sync
            self._records[sync.id] = []
        return sync

    def get(self, sync_id: str) -> StreamingSync:
        s = self._syncs.get(sync_id)
        if s is None:
            raise FileProcessingError("NOT_FOUND", f"同步 {sync_id} 不存在")
        return s

    def list(self) -> list[StreamingSync]:
        return list(self._syncs.values())

    def update(
        self, sync_id: str, updates: dict[str, Any],
    ) -> StreamingSync:
        s = self.get(sync_id)
        if "source_type" in updates:
            if updates["source_type"] not in _VALID_SOURCE_TYPES:
                raise FileProcessingError(
                    "INVALID_SOURCE_TYPE",
                    f"未知源类型：{updates['source_type']}",
                )
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if hasattr(s, k):
                setattr(s, k, v)
        return s

    def delete(self, sync_id: str) -> bool:
        existed = self._syncs.pop(sync_id, None) is not None
        self._records.pop(sync_id, None)
        return existed

    def start(self, sync_id: str) -> StreamingSync:
        s = self.get(sync_id)
        s.status = "running"
        return s

    def stop(self, sync_id: str) -> StreamingSync:
        s = self.get(sync_id)
        s.status = "stopped"
        return s

    def consume(
        self, sync_id: str, events: list[StreamEvent],
    ) -> list[SyncRecord]:
        s = self.get(sync_id)
        if s.status != "running":
            raise FileProcessingError(
                "NOT_RUNNING", f"同步 {sync_id} 未在运行（当前状态：{s.status}）",
            )
        records: list[SyncRecord] = []
        max_offset = s.offset
        for ev in events:
            rec = SyncRecord(sync_id=sync_id, event_key=ev.key, status="synced")
            records.append(rec)
            if ev.offset > max_offset:
                max_offset = ev.offset

        with self._lock:
            rec_list = self._records.get(sync_id, [])
            for rec in records:
                if len(rec_list) >= _MAX_RECORDS:
                    rec_list.pop(0)
                rec_list.append(rec)
            self._records[sync_id] = rec_list

        s.offset = max_offset
        s.last_consumed_at = time.time()
        return records

    def list_records(
        self, sync_id: str, limit: int = 50,
    ) -> list[SyncRecord]:
        self.get(sync_id)  # 校验存在
        rec_list = self._records.get(sync_id, [])
        items = list(reversed(rec_list))
        if limit > 0:
            items = items[:limit]
        return items


# ════════════════════ 单例 ════════════════════

_filter_engine: FileFilterEngine | None = None
_transform_engine: FileTransformEngine | None = None
_streaming_engine: StreamingSyncEngine | None = None
_singleton_lock = threading.Lock()


def get_filter_engine() -> FileFilterEngine:
    global _filter_engine
    if _filter_engine is None:
        with _singleton_lock:
            if _filter_engine is None:
                _filter_engine = FileFilterEngine()
    return _filter_engine


def get_transform_engine() -> FileTransformEngine:
    global _transform_engine
    if _transform_engine is None:
        with _singleton_lock:
            if _transform_engine is None:
                _transform_engine = FileTransformEngine()
    return _transform_engine


def get_streaming_engine() -> StreamingSyncEngine:
    global _streaming_engine
    if _streaming_engine is None:
        with _singleton_lock:
            if _streaming_engine is None:
                _streaming_engine = StreamingSyncEngine()
    return _streaming_engine
