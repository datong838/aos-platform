"""W3 Task 7.5 · Build 面板（3种启动方式）（220w L3655）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class BuildPanelError(Exception):
    """Build 面板错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BuildPanelConfig(BaseModel):
    """Build 面板（3种启动方式）（220w L3655）."""
    ib_id: str = ""
    repo_id: str = ""
    launch_mode: str = "MANUAL"
    branch_name: str = "main"
    target_files: list[str] = []  # 目标文件
    build_command: str = ""
    build_status: str = "IDLE"
    build_log_url: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BuildPanelEngine:
    """Build 面板（3种启动方式）（220w L3655）."""

    _instance: Optional[BuildPanelEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, BuildPanelConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BuildPanelEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: BuildPanelConfig) -> BuildPanelConfig:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"ib-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "ib_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "ib_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> BuildPanelConfig:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildPanelError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[BuildPanelConfig]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> BuildPanelConfig:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildPanelError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise BuildPanelError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def start_build(self, panel_id) -> dict:
        """开始构建."""
        return {"ok": True, "method": "start_build"}

    def cancel_build(self, panel_id) -> dict:
        """取消构建."""
        return {"ok": True, "method": "cancel_build"}

    def get_log(self, panel_id) -> dict:
        """获取日志."""
        return {"ok": True, "method": "get_log"}


def get_engine() -> BuildPanelEngine:
    return BuildPanelEngine.get_instance()
