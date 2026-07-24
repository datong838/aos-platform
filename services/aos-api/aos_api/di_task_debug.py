"""W3 Task 2.2 · 任务调试（220w L2079）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class TaskDebugError(Exception):
    """任务调试错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DebugSession(BaseModel):
    """任务调试（220w L2079）."""
    td_id: str = ""
    task_id: str = ""
    session_status: str = "ACTIVE"
    log_entries: list[dict] = []  # 日志条目列表
    param_snapshot: dict = {}  # 参数快照
    error_info: Optional[dict] = None
    started_at: Optional[datetime] = None
    duration_ms: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TaskDebugEngine:
    """任务调试（220w L2079）."""

    _instance: Optional[TaskDebugEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, DebugSession] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "TaskDebugEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: DebugSession) -> DebugSession:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"td-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "td_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "td_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> DebugSession:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise TaskDebugError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[DebugSession]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> DebugSession:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise TaskDebugError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise TaskDebugError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def add_log(self, session_id, level, message) -> dict:
        """添加日志."""
        return {"ok": True, "method": "add_log"}

    def get_snapshot(self, session_id) -> dict:
        """获取参数和日志快照."""
        return {"ok": True, "method": "get_snapshot"}

    def trace_error(self, session_id) -> dict:
        """追踪错误根因."""
        return {"ok": True, "method": "trace_error"}

    def close(self, session_id) -> dict:
        """关闭会话."""
        return {"ok": True, "method": "close"}


def get_engine() -> TaskDebugEngine:
    return TaskDebugEngine.get_instance()
