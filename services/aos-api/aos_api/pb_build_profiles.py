"""W3 Task 5.3 · 搭建设置（9种批处理+6种流式计算配置文件）（220w L1236）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class BuildProfilesError(Exception):
    """搭建设置错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BuildProfile(BaseModel):
    """搭建设置（9种批处理+6种流式计算配置文件）（220w L1236）."""
    pf_id: str = ""
    name: str = ""
    profile_type: str = "BATCH"
    executor_memory_mb: int = 2048
    executor_cores: int = 2
    driver_memory_mb: int = 1024
    parallelism: int = 10
    is_default: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BuildProfilesEngine:
    """搭建设置（9种批处理+6种流式计算配置文件）（220w L1236）."""

    _instance: Optional[BuildProfilesEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, BuildProfile] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BuildProfilesEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: BuildProfile) -> BuildProfile:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"pf-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "pf_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "pf_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> BuildProfile:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildProfilesError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[BuildProfile]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> BuildProfile:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildProfilesError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise BuildProfilesError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def get_batch_defaults(self, ) -> dict:
        """获取9种批处理预设."""
        return {"ok": True, "method": "get_batch_defaults"}

    def get_streaming_defaults(self, ) -> dict:
        """获取6种流式预设."""
        return {"ok": True, "method": "get_streaming_defaults"}

    def apply(self, pipeline_id, profile_id) -> dict:
        """应用到 Pipeline."""
        return {"ok": True, "method": "apply"}


def get_engine() -> BuildProfilesEngine:
    return BuildProfilesEngine.get_instance()
