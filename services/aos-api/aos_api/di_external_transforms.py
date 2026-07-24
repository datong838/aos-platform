"""W4 · External Transforms（220w L2047）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class ExternalTransformsError(Exception):
    """External Transforms错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ExternalTransforms(BaseModel):
    """External Transforms（220w L2047）."""
    ext_id: str = ""
    name: str = ""
    config: dict = {"": True}
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExternalTransformsEngine:
    """External Transforms引擎（220w L2047）."""

    _instance: Optional["ExternalTransformsEngine"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, ExternalTransforms] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls_) -> "ExternalTransformsEngine":
        if cls_._instance is None:
            with cls_._instance_lock:
                if cls_._instance is None:
                    cls_._instance = cls_()
        return cls_._instance

    def register(self, item: ExternalTransforms) -> ExternalTransforms:
        now = _utcnow()
        oid = f"ext-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "ext_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "ext_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> ExternalTransforms:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise ExternalTransformsError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[ExternalTransforms]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> ExternalTransforms:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise ExternalTransformsError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise ExternalTransformsError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]


def get_engine() -> ExternalTransformsEngine:
    return ExternalTransformsEngine.get_instance()
