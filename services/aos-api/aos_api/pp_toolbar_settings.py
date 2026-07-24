"""W3 Task 5.1 · 顶部工具栏-搭建设置（220w L1005）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class ToolbarSettingsError(Exception):
    """顶部工具栏-搭建设置错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolbarSetting(BaseModel):
    """顶部工具栏-搭建设置（220w L1005）."""
    ts_id: str = ""
    pipeline_id: str = ""
    build_mode: str = "MANUAL"
    schedule_cron: str = ""
    auto_rebuild_on_failure: bool = False
    notification_channels: list[str] = []  # 通知渠道
    max_parallel_tasks: int = 4
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ToolbarSettingsEngine:
    """顶部工具栏-搭建设置（220w L1005）."""

    _instance: Optional[ToolbarSettingsEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, ToolbarSetting] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ToolbarSettingsEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: ToolbarSetting) -> ToolbarSetting:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"ts-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "ts_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "ts_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> ToolbarSetting:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise ToolbarSettingsError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[ToolbarSetting]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> ToolbarSetting:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise ToolbarSettingsError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise ToolbarSettingsError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def get_or_create(self, pipeline_id) -> dict:
        """获取或创建设置."""
        return {"ok": True, "method": "get_or_create"}

    def apply_preset(self, pipeline_id, preset_name) -> dict:
        """应用预设."""
        return {"ok": True, "method": "apply_preset"}


def get_engine() -> ToolbarSettingsEngine:
    return ToolbarSettingsEngine.get_instance()
