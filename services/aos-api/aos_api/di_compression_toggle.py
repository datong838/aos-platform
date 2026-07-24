"""W4 · 数据压缩开关（220w L727）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class CompressionToggleError(Exception):
    """数据压缩开关错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CompressionToggle(BaseModel):
    """数据压缩开关（220w L727）."""
    ct_id: str = ""
    name: str = ""
    config: dict = {"": True}
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CompressionToggleEngine:
    """数据压缩开关引擎（220w L727）."""

    _instance: Optional["CompressionToggleEngine"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, CompressionToggle] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls_) -> "CompressionToggleEngine":
        if cls_._instance is None:
            with cls_._instance_lock:
                if cls_._instance is None:
                    cls_._instance = cls_()
        return cls_._instance

    def register(self, item: CompressionToggle) -> CompressionToggle:
        now = _utcnow()
        oid = f"ct-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "ct_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "ct_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> CompressionToggle:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise CompressionToggleError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[CompressionToggle]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> CompressionToggle:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise CompressionToggleError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise CompressionToggleError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]


def get_engine() -> CompressionToggleEngine:
    return CompressionToggleEngine.get_instance()
