"""
W5 — 规则顺序冲突检测
Engine: RuleOrderConflictEngine (Singleton + threading.Lock)
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class RuleOrderConflict(BaseModel):
    """规则顺序冲突检测 entity."""
    id: str = Field(default_factory=lambda: f"rule_order_conflict-{uuid.uuid4().hex[:12]}")
    name: str
    description: str = ""
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RuleOrderConflictEngine:
    """Thread-safe singleton engine for 规则顺序冲突检测."""
    _instance: "RuleOrderConflictEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "RuleOrderConflictEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._store: dict[str, RuleOrderConflict] = {}
                    cls._instance._init_lock = threading.Lock()
        return cls._instance

    def register(self, item: RuleOrderConflict) -> RuleOrderConflict:
        with self._init_lock:
            self._store[item.id] = item
            return item

    def get(self, item_id: str) -> RuleOrderConflict | None:
        return self._store.get(item_id)

    def list(self) -> list[RuleOrderConflict]:
        return list(self._store.values())

    def update(self, item_id: str, patch: dict[str, Any]) -> RuleOrderConflict | None:
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


engine = RuleOrderConflictEngine()
