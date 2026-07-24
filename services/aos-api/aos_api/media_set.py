"""W1-16 · MediaSet 类型化 + 表格行变换。

类型化媒体集合（DICOM/audio/document/image）+ 表格行变换（复用 W1-8 transform_ops）。

详见 docs/palantier/20_tech/220tech_media-set.md。
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .funnel_mapping import SchemaField
from .media_reference import MediaReferenceError, get_store as get_media_store
from .transform_ops import apply_transform


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "ms-" + uuid.uuid4().hex[:12]


MediaSetType = Literal["dicom", "audio", "document", "image"]

_TYPE_ACCEPTS: dict[str, set[str]] = {
    "dicom": {"image"},
    "audio": {"audio"},
    "document": {"document"},
    "image": {"image"},
}

_DEFAULT_SCHEMA: dict[str, list[SchemaField]] = {
    "dicom": [
        SchemaField(name="media_ref_id", type="string", nullable=False),
        SchemaField(name="patient_id", type="string"),
        SchemaField(name="study_uid", type="string"),
        SchemaField(name="size_bytes", type="number"),
    ],
    "audio": [
        SchemaField(name="media_ref_id", type="string", nullable=False),
        SchemaField(name="duration_sec", type="number"),
        SchemaField(name="sample_rate", type="number"),
        SchemaField(name="size_bytes", type="number"),
    ],
    "document": [
        SchemaField(name="media_ref_id", type="string", nullable=False),
        SchemaField(name="title", type="string"),
        SchemaField(name="page_count", type="number"),
        SchemaField(name="size_bytes", type="number"),
    ],
    "image": [
        SchemaField(name="media_ref_id", type="string", nullable=False),
        SchemaField(name="width", type="number"),
        SchemaField(name="height", type="number"),
        SchemaField(name="size_bytes", type="number"),
    ],
}


LoadStrategy = Literal["lazy", "eager", "stream"]
LOAD_STRATEGIES = ("lazy", "eager", "stream")


class MediaSet(BaseModel):
    id: str
    name: str
    type: MediaSetType
    media_ref_ids: list[str] = Field(default_factory=list)
    schema: list[SchemaField] = Field(default_factory=list)
    load_strategy: LoadStrategy = "eager"
    created_at: str = Field(default_factory=_now)


class MediaSetError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class MediaSetStore:
    def __init__(self) -> None:
        self._sets: dict[str, MediaSet] = {}
        self._lock = threading.Lock()

    def create(self, name: str, set_type: str, load_strategy: str = "eager") -> MediaSet:
        if set_type not in _TYPE_ACCEPTS:
            raise MediaSetError("BAD_TYPE", f"未知类型 {set_type!r}，可用：{list(_TYPE_ACCEPTS.keys())}")
        if load_strategy not in LOAD_STRATEGIES:
            raise MediaSetError("BAD_STRATEGY", f"未知加载策略 {load_strategy!r}，可用：{list(LOAD_STRATEGIES)}")
        schema = list(_DEFAULT_SCHEMA[set_type])
        ms = MediaSet(
            id=_new_id(), name=name, type=set_type, schema=schema,
            load_strategy=load_strategy,  # type: ignore[arg-type]
        )
        with self._lock:
            self._sets[ms.id] = ms
        return ms

    def get(self, set_id: str) -> MediaSet:
        if set_id not in self._sets:
            raise MediaSetError("NOT_FOUND", f"MediaSet {set_id!r} 不存在")
        return self._sets[set_id]

    def list_all(self) -> list[MediaSet]:
        return list(self._sets.values())

    def delete(self, set_id: str) -> None:
        with self._lock:
            if set_id not in self._sets:
                raise MediaSetError("NOT_FOUND", f"MediaSet {set_id!r} 不存在")
            del self._sets[set_id]

    def add_media(self, set_id: str, ref_id: str) -> MediaSet:
        ms = self.get(set_id)
        try:
            ref = get_media_store().get(ref_id)
        except MediaReferenceError as exc:
            raise MediaSetError("MEDIA_NOT_FOUND", f"MediaReference {ref_id!r} 不存在") from exc
        accepts = _TYPE_ACCEPTS[ms.type]
        if ref.kind not in accepts:
            raise MediaSetError(
                "TYPE_MISMATCH",
                f"MediaSet 类型 {ms.type!r} 不接受 media kind {ref.kind!r}（仅接受 {sorted(accepts)}）",
            )
        if ref_id not in ms.media_ref_ids:
            ms.media_ref_ids.append(ref_id)
        return ms

    def remove_media(self, set_id: str, ref_id: str) -> MediaSet:
        ms = self.get(set_id)
        if ref_id not in ms.media_ref_ids:
            raise MediaSetError("MEDIA_NOT_IN_SET", f"media {ref_id!r} 不在集合中")
        ms.media_ref_ids.remove(ref_id)
        return ms

    def _build_row(self, ref_id: str) -> dict[str, Any]:
        try:
            ref = get_media_store().get(ref_id)
        except MediaReferenceError:
            return {"media_ref_id": ref_id, "size_bytes": 0}
        return {"media_ref_id": ref_id, "size_bytes": ref.size_bytes}

    def get_rows(self, set_id: str, strategy: str | None = None) -> list[dict[str, Any]]:
        ms = self.get(set_id)
        use_strategy = strategy or ms.load_strategy
        if use_strategy not in LOAD_STRATEGIES:
            raise MediaSetError("BAD_STRATEGY", f"未知加载策略 {use_strategy!r}")
        rows: list[dict[str, Any]] = []
        for ref_id in ms.media_ref_ids:
            try:
                ref = get_media_store().get(ref_id)
            except MediaReferenceError:
                continue
            row: dict[str, Any] = {"media_ref_id": ref_id, "size_bytes": ref.size_bytes}
            rows.append(row)
        return rows

    def get_rows_lazy(self, set_id: str, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        ms = self.get(set_id)
        total = len(ms.media_ref_ids)
        start = (page - 1) * page_size
        end = start + page_size
        page_ids = ms.media_ref_ids[start:end]
        rows = [self._build_row(rid) for rid in page_ids]
        return {
            "rows": rows,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_more": end < total,
        }

    def get_rows_stream(self, set_id: str):
        ms = self.get(set_id)
        for ref_id in ms.media_ref_ids:
            yield self._build_row(ref_id)

    def transform(self, set_id: str, op: str, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows = self.get_rows(set_id)
        return apply_transform(op, rows, config or {})


_store = MediaSetStore()


def get_store() -> MediaSetStore:
    return _store
