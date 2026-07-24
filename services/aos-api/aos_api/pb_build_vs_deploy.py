"""W3 Task 5.2 · 部署 vs 搭建分离（220w L1213）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class BuildDeploySeparationError(Exception):
    """部署 vs 搭建分离错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BuildDeployConfig(BaseModel):
    """部署 vs 搭建分离（220w L1213）."""
    bd_id: str = ""
    pipeline_id: str = ""
    build_mode: str = "BUILD"
    target_environment: str = "dev"
    build_timeout_min: int = 60
    deploy_strategy: str = "BLUE_GREEN"
    health_check_required: bool = True
    status: str = "IDLE"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BuildDeploySeparationEngine:
    """部署 vs 搭建分离（220w L1213）."""

    _instance: Optional[BuildDeploySeparationEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, BuildDeployConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BuildDeploySeparationEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: BuildDeployConfig) -> BuildDeployConfig:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"bd-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "bd_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "bd_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> BuildDeployConfig:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildDeploySeparationError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[BuildDeployConfig]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> BuildDeployConfig:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildDeploySeparationError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise BuildDeploySeparationError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def start_build(self, config_id) -> dict:
        """开始搭建."""
        return {"ok": True, "method": "start_build"}

    def start_deploy(self, config_id) -> dict:
        """开始部署."""
        return {"ok": True, "method": "start_deploy"}

    def get_status(self, config_id) -> dict:
        """获取状态."""
        return {"ok": True, "method": "get_status"}


def get_engine() -> BuildDeploySeparationEngine:
    return BuildDeploySeparationEngine.get_instance()
