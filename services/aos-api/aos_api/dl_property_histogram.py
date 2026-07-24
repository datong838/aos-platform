"""W4 · 属性和直方图面板（220w L530）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class PropertyHistogramError(Exception):
    """属性和直方图面板错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PropertyHistogram(BaseModel):
    """属性和直方图面板（220w L530）."""
    ph_id: str = ""
    name: str = ""
    config: dict = {"": True}
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PropertyHistogramEngine:
    """属性和直方图面板引擎（220w L530）."""

    _instance: Optional["PropertyHistogramEngine"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, PropertyHistogram] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls_) -> "PropertyHistogramEngine":
        if cls_._instance is None:
            with cls_._instance_lock:
                if cls_._instance is None:
                    cls_._instance = cls_()
        return cls_._instance

    def register(self, item: PropertyHistogram) -> PropertyHistogram:
        now = _utcnow()
        oid = f"ph-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "ph_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "ph_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> PropertyHistogram:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise PropertyHistogramError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[PropertyHistogram]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> PropertyHistogram:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise PropertyHistogramError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise PropertyHistogramError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]


def get_engine() -> PropertyHistogramEngine:
    return PropertyHistogramEngine.get_instance()
