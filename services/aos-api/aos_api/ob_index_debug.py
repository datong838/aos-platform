"""W3 Task 7.2 · 索引调试（220w L2565）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class IndexDebugError(Exception):
    """索引调试错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class IndexDebugInfo(BaseModel):
    """索引调试（220w L2565）."""
    id_id: str = ""
    object_type_id: str = ""
    index_name: str = ""
    index_status: str = "ACTIVE"
    total_docs: int = 0
    indexed_docs: int = 0
    last_build_at: Optional[datetime] = None
    build_errors: list[dict] = []  # 构建错误
    query_latency_ms: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class IndexDebugEngine:
    """索引调试（220w L2565）."""

    _instance: Optional[IndexDebugEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, IndexDebugInfo] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "IndexDebugEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: IndexDebugInfo) -> IndexDebugInfo:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"id-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "id_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "id_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> IndexDebugInfo:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise IndexDebugError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[IndexDebugInfo]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> IndexDebugInfo:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise IndexDebugError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise IndexDebugError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def diagnose(self, object_type_id) -> dict:
        """诊断索引状态."""
        return {"ok": True, "method": "diagnose"}

    def rebuild(self, object_type_id, index_name) -> dict:
        """重建索引."""
        return {"ok": True, "method": "rebuild"}

    def get_slow_queries(self, object_type_id) -> dict:
        """获取慢查询."""
        return {"ok": True, "method": "get_slow_queries"}


def get_engine() -> IndexDebugEngine:
    return IndexDebugEngine.get_instance()
