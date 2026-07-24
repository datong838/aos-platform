"""
W5 — Object Table 进阶
Engine: ObjectTableAdvancedEngine (Singleton + threading.Lock)
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ObjectTableAdvanced(BaseModel):
    """Object Table 进阶 entity."""
    id: str = Field(default_factory=lambda: f"object_table_advanced-{uuid.uuid4().hex[:12]}")
    name: str
    description: str = ""
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ObjectTableAdvancedEngine:
    """Thread-safe singleton engine for Object Table 进阶."""
    _instance: "ObjectTableAdvancedEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ObjectTableAdvancedEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._store: dict[str, ObjectTableAdvanced] = {}
                    cls._instance._init_lock = threading.Lock()
        return cls._instance

    def register(self, item: ObjectTableAdvanced) -> ObjectTableAdvanced:
        with self._init_lock:
            self._store[item.id] = item
            return item

    def get(self, item_id: str) -> ObjectTableAdvanced | None:
        return self._store.get(item_id)

    def list(self) -> list[ObjectTableAdvanced]:
        return list(self._store.values())

    def update(self, item_id: str, patch: dict[str, Any]) -> ObjectTableAdvanced | None:
        with self._init_lock:
            item = self._store.get(item_id)
            if item is None:
                return None
            updated = item.model_copy(update={**patch, "updated_at": datetime.now(timezone.utc).isoformat()})
            self._store[item_id] = updated
            return updated

    def delete(self, item_id: str) -> bool:
        with self._init_lock:
            return self._store.pop(item_id, None) is not None

    def reset(self) -> None:
        """Clear all entries (for testing)."""
        with self._init_lock:
            self._store.clear()


engine = ObjectTableAdvancedEngine()
