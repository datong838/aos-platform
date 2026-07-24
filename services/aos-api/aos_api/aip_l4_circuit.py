"""221plan · L4 自动化熔断.

引擎 + CRUD + 业务方法。统一模式：Pydantic Model + Singleton Engine + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_MAX_ITEMS = 200
_LOCK = threading.Lock()


class L4CircuitItem(BaseModel):
    """L4 自动化熔断 数据模型。"""
    id: str = Field(default_factory=lambda: "aip-l4-circuit-" + uuid.uuid4().hex[:8])
    name: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class L4CircuitEngine:
    """L4 自动化熔断 引擎。Singleton + threading.Lock。"""

    _instance: "L4CircuitEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "L4CircuitEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._items: dict[str, L4CircuitItem] = {}
        return cls._instance

    def create(self, name: str, config: dict[str, Any] | None = None) -> L4CircuitItem:
        with _LOCK:
            if len(self._items) >= _MAX_ITEMS:
                raise ValueError(f"已达容量上限 {_MAX_ITEMS}")
            item = L4CircuitItem(name=name, config=config or {})
            self._items[item.id] = item
            return item

    def get(self, item_id: str) -> L4CircuitItem | None:
        return self._items.get(item_id)

    def list(self) -> list[L4CircuitItem]:
        return list(self._items.values())

    def update(self, item_id: str, **kwargs: Any) -> L4CircuitItem:
        with _LOCK:
            item = self._items.get(item_id)
            if item is None:
                raise KeyError(f"不存在 {item_id}")
            for k, v in kwargs.items():
                if hasattr(item, k):
                    setattr(item, k, v)
            item.updated_at = time.time()
            return item

    def delete(self, item_id: str) -> bool:
        with _LOCK:
            return self._items.pop(item_id, None) is not None

    def reset(self) -> None:
        """清空引擎（测试隔离用）。"""
        with _LOCK:
            self._items.clear()


def get_engine() -> L4CircuitEngine:
    return L4CircuitEngine()
