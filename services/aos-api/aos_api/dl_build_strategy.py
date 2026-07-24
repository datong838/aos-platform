"""W3 Task 3.1 · 三种搭建策略（220w L591）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class BuildStrategyError(Exception):
    """三种搭建策略错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BuildStrategy(BaseModel):
    """三种搭建策略（220w L591）."""
    bs_id: str = ""
    name: str = ""
    strategy_type: str = "FULL"
    target_dataset_ids: list[str] = []  # 目标数据集
    checkpoint_id: str = ""
    resource_profile: str = "standard"
    priority: int = 5
    status: str = "DRAFT"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BuildStrategyEngine:
    """三种搭建策略（220w L591）."""

    _instance: Optional[BuildStrategyEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, BuildStrategy] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BuildStrategyEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: BuildStrategy) -> BuildStrategy:
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

    def get(self, item_id: str) -> BuildStrategy:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildStrategyError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[BuildStrategy]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> BuildStrategy:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildStrategyError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise BuildStrategyError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def preview(self, strategy_id) -> dict:
        """预览搭建影响范围."""
        return {"ok": True, "method": "preview"}

    def execute(self, strategy_id) -> dict:
        """执行搭建."""
        return {"ok": True, "method": "execute"}

    def compare(self, strategy_id_a, strategy_id_b) -> dict:
        """比较两个策略."""
        return {"ok": True, "method": "compare"}


def get_engine() -> BuildStrategyEngine:
    return BuildStrategyEngine.get_instance()
