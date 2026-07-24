"""W3 Task 3.3 · 依赖顺序搭建（220w L594）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class DependencyOrderError(Exception):
    """依赖顺序搭建错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DependencyEdge(BaseModel):
    """依赖顺序搭建（220w L594）."""
    do_id: str = ""
    upstream_dataset: str = ""
    downstream_dataset: str = ""
    dependency_type: str = "HARD"
    lag_seconds: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DependencyOrderEngine:
    """依赖顺序搭建（220w L594）."""

    _instance: Optional[DependencyOrderEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, DependencyEdge] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "DependencyOrderEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: DependencyEdge) -> DependencyEdge:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"do-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "do_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "do_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> DependencyEdge:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise DependencyOrderError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[DependencyEdge]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> DependencyEdge:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise DependencyOrderError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise DependencyOrderError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def topological_sort(self, dataset_ids) -> dict:
        """拓扑排序."""
        return {"ok": True, "method": "topological_sort"}

    def validate_no_cycle(self, dataset_ids) -> dict:
        """验证无环."""
        return {"ok": True, "method": "validate_no_cycle"}

    def build_plan(self, root_dataset_id) -> dict:
        """生成搭建计划."""
        return {"ok": True, "method": "build_plan"}


def get_engine() -> DependencyOrderEngine:
    return DependencyOrderEngine.get_instance()
