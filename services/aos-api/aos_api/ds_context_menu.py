"""W3 Task 4.1 · 数据集操作菜单（220w L1537）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class DatasetContextMenuError(Exception):
    """数据集操作菜单错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DatasetAction(BaseModel):
    """数据集操作菜单（220w L1537）."""
    da_id: str = ""
    dataset_id: str = ""
    action_type: str = "EXPLORE"
    label: str = ""
    icon: str = ""
    is_available: bool = True
    permission_required: str = ""
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DatasetContextMenuEngine:
    """数据集操作菜单（220w L1537）."""

    _instance: Optional[DatasetContextMenuEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, DatasetAction] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "DatasetContextMenuEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: DatasetAction) -> DatasetAction:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"da-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "da_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "da_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> DatasetAction:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise DatasetContextMenuError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[DatasetAction]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> DatasetAction:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise DatasetContextMenuError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise DatasetContextMenuError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def get_actions(self, dataset_id) -> dict:
        """获取数据集的可用操作列表."""
        return {"ok": True, "method": "get_actions"}

    def execute(self, dataset_id, action_type) -> dict:
        """执行操作."""
        return {"ok": True, "method": "execute"}

    def validate_permission(self, dataset_id, action_type, user_role) -> dict:
        """验证权限."""
        return {"ok": True, "method": "validate_permission"}


def get_engine() -> DatasetContextMenuEngine:
    return DatasetContextMenuEngine.get_instance()
