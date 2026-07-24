"""
W5 — 转录文本后续处理
Engine: TranscriptPostprocEngine (Singleton + threading.Lock)
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class TranscriptPostproc(BaseModel):
    """转录文本后续处理 entity."""
    id: str = Field(default_factory=lambda: f"transcript_postproc-{uuid.uuid4().hex[:12]}")
    name: str
    description: str = ""
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TranscriptPostprocEngine:
    """Thread-safe singleton engine for 转录文本后续处理."""
    _instance: "TranscriptPostprocEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "TranscriptPostprocEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._store: dict[str, TranscriptPostproc] = {}
                    cls._instance._init_lock = threading.Lock()
        return cls._instance

    def register(self, item: TranscriptPostproc) -> TranscriptPostproc:
        with self._init_lock:
            self._store[item.id] = item
            return item

    def get(self, item_id: str) -> TranscriptPostproc | None:
        return self._store.get(item_id)

    def list(self) -> list[TranscriptPostproc]:
        return list(self._store.values())

    def update(self, item_id: str, patch: dict[str, Any]) -> TranscriptPostproc | None:
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


engine = TranscriptPostprocEngine()
