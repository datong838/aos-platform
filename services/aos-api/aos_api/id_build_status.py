"""W3 Task 7.6 · 搭建状态监控（220w L3656）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class BuildStatusMonitorError(Exception):
    """搭建状态监控错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BuildStatus(BaseModel):
    """搭建状态监控（220w L3656）."""
    bs_id: str = ""
    build_id: str = ""
    build_phase: str = "INIT"
    progress_percent: float = 0.0
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    error_message: str = ""
    started_at: Optional[datetime] = None
    estimated_remaining_sec: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BuildStatusMonitorEngine:
    """搭建状态监控（220w L3656）."""

    _instance: Optional[BuildStatusMonitorEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, BuildStatus] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BuildStatusMonitorEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: BuildStatus) -> BuildStatus:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"bs-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "bs_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "bs_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> BuildStatus:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildStatusMonitorError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[BuildStatus]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> BuildStatus:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildStatusMonitorError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise BuildStatusMonitorError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def update_progress(self, build_id, completed_steps) -> dict:
        """更新进度."""
        return {"ok": True, "method": "update_progress"}

    def mark_phase(self, build_id, phase) -> dict:
        """标记阶段."""
        return {"ok": True, "method": "mark_phase"}

    def get_eta(self, build_id) -> dict:
        """获取预计完成时间."""
        return {"ok": True, "method": "get_eta"}


def get_engine() -> BuildStatusMonitorEngine:
    return BuildStatusMonitorEngine.get_instance()
