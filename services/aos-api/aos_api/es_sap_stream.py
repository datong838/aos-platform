"""W3 Task 7.3 · SAP 实时流（220w L2188）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class SapStreamError(Exception):
    """SAP 实时流错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SapStreamConfig(BaseModel):
    """SAP 实时流（220w L2188）."""
    ss_id: str = ""
    name: str = ""
    sap_system_id: str = ""
    connection_type: str = "RFC"
    table_names: list[str] = []  # 监听表
    poll_interval_sec: int = 30
    status: str = "STOPPED"
    messages_per_sec: float = 0.0
    last_message_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SapStreamEngine:
    """SAP 实时流（220w L2188）."""

    _instance: Optional[SapStreamEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, SapStreamConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "SapStreamEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: SapStreamConfig) -> SapStreamConfig:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"ss-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "ss_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "ss_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> SapStreamConfig:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise SapStreamError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[SapStreamConfig]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> SapStreamConfig:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise SapStreamError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise SapStreamError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def start(self, config_id) -> dict:
        """启动监听."""
        return {"ok": True, "method": "start"}

    def stop(self, config_id) -> dict:
        """停止监听."""
        return {"ok": True, "method": "stop"}

    def get_stats(self, config_id) -> dict:
        """获取统计."""
        return {"ok": True, "method": "get_stats"}


def get_engine() -> SapStreamEngine:
    return SapStreamEngine.get_instance()
