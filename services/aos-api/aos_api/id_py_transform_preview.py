"""W3 Task 7.4 · Python Transform 预览（220w L3623）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class PyTransformPreviewError(Exception):
    """Python Transform 预览错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TransformPreview(BaseModel):
    """Python Transform 预览（220w L3623）."""
    tp_id: str = ""
    transform_code: str = ""
    input_dataset_id: str = ""
    preview_row_count: int = 100
    output_schema: dict = {}  # 输出 Schema
    preview_rows: list[dict] = []  # 预览数据
    execution_time_ms: int = 0
    errors: list[str] = []  # 错误信息
    status: str = "PENDING"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PyTransformPreviewEngine:
    """Python Transform 预览（220w L3623）."""

    _instance: Optional[PyTransformPreviewEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, TransformPreview] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "PyTransformPreviewEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: TransformPreview) -> TransformPreview:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"tp-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "tp_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "tp_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> TransformPreview:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise PyTransformPreviewError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[TransformPreview]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> TransformPreview:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise PyTransformPreviewError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise PyTransformPreviewError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def run_preview(self, preview_id) -> dict:
        """运行预览."""
        return {"ok": True, "method": "run_preview"}

    def get_schema(self, preview_id) -> dict:
        """获取输出 Schema."""
        return {"ok": True, "method": "get_schema"}


def get_engine() -> PyTransformPreviewEngine:
    return PyTransformPreviewEngine.get_instance()
