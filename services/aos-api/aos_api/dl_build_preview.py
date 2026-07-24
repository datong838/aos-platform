"""W3 Task 3.2 · 搭建预览（220w L592）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class BuildPreviewError(Exception):
    """搭建预览错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BuildPreview(BaseModel):
    """搭建预览（220w L592）."""
    bp_id: str = ""
    dataset_id: str = ""
    affected_datasets: list[str] = []  # 受影响数据集
    estimated_duration_min: int = 0
    estimated_cost_usd: float = 0.0
    resource_units: int = 0
    preview_status: str = "PENDING"
    dry_run_results: dict = {}  # Dry-run 结果
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BuildPreviewEngine:
    """搭建预览（220w L592）."""

    _instance: Optional[BuildPreviewEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, BuildPreview] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BuildPreviewEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: BuildPreview) -> BuildPreview:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"bp-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "bp_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "bp_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> BuildPreview:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildPreviewError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[BuildPreview]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> BuildPreview:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise BuildPreviewError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise BuildPreviewError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def estimate(self, dataset_id) -> dict:
        """预估搭建资源."""
        return {"ok": True, "method": "estimate"}

    def dry_run(self, dataset_id) -> dict:
        """空运行搭建."""
        return {"ok": True, "method": "dry_run"}

    def cancel(self, preview_id) -> dict:
        """取消预览."""
        return {"ok": True, "method": "cancel"}


def get_engine() -> BuildPreviewEngine:
    return BuildPreviewEngine.get_instance()
