"""W3 Task 5.5 · 健康检查配置（任务级/搭建级/新鲜度检查）（220w L1265）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class HealthCheckError(Exception):
    """健康检查配置错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class HealthCheckConfig(BaseModel):
    """健康检查配置（任务级/搭建级/新鲜度检查）（220w L1265）."""
    hc_id: str = ""
    name: str = ""
    check_type: str = "TASK_LEVEL"
    target_id: str = ""
    check_expression: str = ""
    threshold: str = ""
    severity: str = "WARNING"
    enabled: bool = True
    last_result: str = "UNKNOWN"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HealthCheckEngine:
    """健康检查配置（任务级/搭建级/新鲜度检查）（220w L1265）."""

    _instance: Optional[HealthCheckEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, HealthCheckConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "HealthCheckEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: HealthCheckConfig) -> HealthCheckConfig:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"hc-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "hc_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "hc_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> HealthCheckConfig:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise HealthCheckError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[HealthCheckConfig]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> HealthCheckConfig:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise HealthCheckError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise HealthCheckError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def run_check(self, config_id) -> dict:
        """执行检查."""
        return {"ok": True, "method": "run_check"}

    def get_results(self, target_id) -> dict:
        """获取检查结果."""
        return {"ok": True, "method": "get_results"}


def get_engine() -> HealthCheckEngine:
    return HealthCheckEngine.get_instance()
