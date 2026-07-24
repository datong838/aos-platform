"""
W5 — 制品库集成
Engine: ArtifactRegistryEngine (Singleton + threading.Lock)
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ArtifactRegistry(BaseModel):
    """制品库集成 entity."""
    id: str = Field(default_factory=lambda: f"artifact_registry-{uuid.uuid4().hex[:12]}")
    name: str
    description: str = ""
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ArtifactRegistryEngine:
    """Thread-safe singleton engine for 制品库集成."""
    _instance: "ArtifactRegistryEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ArtifactRegistryEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._store: dict[str, ArtifactRegistry] = {}
                    cls._instance._init_lock = threading.Lock()
        return cls._instance

    def register(self, item: ArtifactRegistry) -> ArtifactRegistry:
        with self._init_lock:
            self._store[item.id] = item
            return item

    def get(self, item_id: str) -> ArtifactRegistry | None:
        return self._store.get(item_id)

    def list(self) -> list[ArtifactRegistry]:
        return list(self._store.values())

    def update(self, item_id: str, patch: dict[str, Any]) -> ArtifactRegistry | None:
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


engine = ArtifactRegistryEngine()
