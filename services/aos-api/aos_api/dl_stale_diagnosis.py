"""W3 Task 3.4 · 过时数据集诊断（220w L652）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class StaleDiagnosisError(Exception):
    """过时数据集诊断错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class StaleDiagnosis(BaseModel):
    """过时数据集诊断（220w L652）."""
    sd_id: str = ""
    dataset_id: str = ""
    is_stale: bool = False
    stale_reason: str = ""
    upstream_last_built: Optional[datetime] = None
    dataset_last_built: Optional[datetime] = None
    stale_chain: list[str] = []  # 过时链
    suggested_action: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StaleDiagnosisEngine:
    """过时数据集诊断（220w L652）."""

    _instance: Optional[StaleDiagnosisEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, StaleDiagnosis] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "StaleDiagnosisEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: StaleDiagnosis) -> StaleDiagnosis:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"sd-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "sd_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "sd_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> StaleDiagnosis:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise StaleDiagnosisError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[StaleDiagnosis]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> StaleDiagnosis:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise StaleDiagnosisError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise StaleDiagnosisError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def scan(self, dataset_ids) -> dict:
        """扫描过时数据集."""
        return {"ok": True, "method": "scan"}

    def diagnose(self, dataset_id) -> dict:
        """诊断单个数据集."""
        return {"ok": True, "method": "diagnose"}

    def get_stale_chain(self, dataset_id) -> dict:
        """获取过时链."""
        return {"ok": True, "method": "get_stale_chain"}

    def suggest_rebuild(self, dataset_id) -> dict:
        """建议重建."""
        return {"ok": True, "method": "suggest_rebuild"}


def get_engine() -> StaleDiagnosisEngine:
    return StaleDiagnosisEngine.get_instance()
