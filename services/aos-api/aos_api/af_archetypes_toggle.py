"""
W5 — Archetypes 切换
Engine: AfArchetypesToggleEngine (Singleton + threading.Lock)
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AfArchetypesToggle(BaseModel):
    """Archetypes 切换 entity."""
    id: str = Field(default_factory=lambda: f"af_archetypes_toggle-{uuid.uuid4().hex[:12]}")
    name: str
    description: str = ""
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AfArchetypesToggleEngine:
    """Thread-safe singleton engine for Archetypes 切换."""
    _instance: "AfArchetypesToggleEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "AfArchetypesToggleEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._store: dict[str, AfArchetypesToggle] = {}
                    cls._instance._init_lock = threading.Lock()
        return cls._instance

    def register(self, item: AfArchetypesToggle) -> AfArchetypesToggle:
        with self._init_lock:
            self._store[item.id] = item
            return item

    def get(self, item_id: str) -> AfArchetypesToggle | None:
        return self._store.get(item_id)

    def list(self) -> list[AfArchetypesToggle]:
        return list(self._store.values())

    def update(self, item_id: str, patch: dict[str, Any]) -> AfArchetypesToggle | None:
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


engine = AfArchetypesToggleEngine()
