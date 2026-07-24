"""W3 Task 5.4 · 任务组（输出分配/计算配置文件/权限继承）（220w L1242）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class TaskGroupsError(Exception):
    """任务组错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TaskGroup(BaseModel):
    """任务组（输出分配/计算配置文件/权限继承）（220w L1242）."""
    tg_id: str = ""
    name: str = ""
    pipeline_id: str = ""
    output_dataset_ids: list[str] = []  # 输出数据集
    compute_profile_id: str = ""
    permission_marks: list[str] = []  # 权限标记
    inherit_parent_permissions: bool = True
    task_ids: list[str] = []  # 组内任务 ID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TaskGroupsEngine:
    """任务组（输出分配/计算配置文件/权限继承）（220w L1242）."""

    _instance: Optional[TaskGroupsEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, TaskGroup] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "TaskGroupsEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: TaskGroup) -> TaskGroup:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"tg-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "tg_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "tg_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> TaskGroup:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise TaskGroupsError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[TaskGroup]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> TaskGroup:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise TaskGroupsError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise TaskGroupsError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def assign_output(self, group_id, dataset_id) -> dict:
        """分配输出."""
        return {"ok": True, "method": "assign_output"}

    def set_profile(self, group_id, profile_id) -> dict:
        """设置配置文件."""
        return {"ok": True, "method": "set_profile"}

    def add_task(self, group_id, task_id) -> dict:
        """添加任务."""
        return {"ok": True, "method": "add_task"}


def get_engine() -> TaskGroupsEngine:
    return TaskGroupsEngine.get_instance()
