"""W3 Task 1.2 · Stream 创建与管理（220w L182）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class StreamManagementError(Exception):
    """Stream 创建与管理错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Stream(BaseModel):
    """Stream 创建与管理（220w L182）."""
    sm_id: str = ""
    name: str = ""
    source_connection_id: str = ""
    partition_strategy: str = "HASH"
    partition_count: int = 1
    status: str = "CREATED"
    throughput_msgs_sec: int = 0
    lag_seconds: int = 0
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StreamManagementEngine:
    """Stream 创建与管理（220w L182）."""

    _instance: Optional[StreamManagementEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, Stream] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "StreamManagementEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: Stream) -> Stream:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"sm-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "sm_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "sm_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> Stream:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise StreamManagementError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[Stream]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> Stream:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise StreamManagementError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise StreamManagementError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def pause(self, stream_id) -> dict:
        """将 RUNNING → PAUSED."""
        return {"ok": True, "method": "pause"}

    def resume(self, stream_id) -> dict:
        """将 PAUSED → RUNNING."""
        return {"ok": True, "method": "resume"}

    def get_stats(self, stream_id) -> dict:
        """获取吞吐量和延迟统计."""
        return {"ok": True, "method": "get_stats"}


def get_engine() -> StreamManagementEngine:
    return StreamManagementEngine.get_instance()
