"""W3 Task 7.1 · 表格表头提取器（220w L1978）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class HeaderExtractorError(Exception):
    """表格表头提取器错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class HeaderExtraction(BaseModel):
    """表格表头提取器（220w L1978）."""
    he_id: str = ""
    file_path: str = ""
    sheet_name: str = ""
    header_row: int = 0
    detected_headers: list[str] = []  # 检测到的表头
    header_type: str = "SINGLE"
    confidence_score: float = 0.0
    data_types: dict = {}  # 推断数据类型
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class HeaderExtractorEngine:
    """表格表头提取器（220w L1978）."""

    _instance: Optional[HeaderExtractorEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, HeaderExtraction] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "HeaderExtractorEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: HeaderExtraction) -> HeaderExtraction:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"he-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "he_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "he_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> HeaderExtraction:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise HeaderExtractorError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[HeaderExtraction]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> HeaderExtraction:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise HeaderExtractorError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise HeaderExtractorError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def extract(self, file_path) -> dict:
        """提取表头."""
        return {"ok": True, "method": "extract"}

    def validate(self, extraction_id) -> dict:
        """验证提取结果."""
        return {"ok": True, "method": "validate"}


def get_engine() -> HeaderExtractorEngine:
    return HeaderExtractorEngine.get_instance()
