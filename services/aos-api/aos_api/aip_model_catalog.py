"""221plan · Model Catalog 登记.

引擎 + CRUD + 业务方法。统一模式：Pydantic Model + Singleton Engine + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from aos_api.tenant_scope import TenantScope

_MAX_ITEMS = 200
_LOCK = threading.Lock()


class ModelCatalogItem(BaseModel):
    """Model Catalog 登记 数据模型。"""
    id: str = Field(default_factory=lambda: "aip-model-catalog-" + uuid.uuid4().hex[:8])
    name: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class ModelCatalogEngine:
    """Model Catalog 登记 引擎。Singleton + threading.Lock。"""

    _instance: "ModelCatalogEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ModelCatalogEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._items: dict[tuple[str, str, str], ModelCatalogItem] = {}
        return cls._instance

    @staticmethod
    def _key(scope: TenantScope, item_id: str) -> tuple[str, str, str]:
        return scope.org_id, scope.project_id, item_id

    def create(
        self,
        scope: TenantScope,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> ModelCatalogItem:
        with _LOCK:
            scope_size = sum(1 for key in self._items if key[:2] == scope.key)
            if scope_size >= _MAX_ITEMS:
                raise ValueError(f"已达容量上限 {_MAX_ITEMS}")
            item = ModelCatalogItem(name=name, config=config or {})
            self._items[self._key(scope, item.id)] = item
            return item

    def get(self, scope: TenantScope, item_id: str) -> ModelCatalogItem | None:
        return self._items.get(self._key(scope, item_id))

    def list(self, scope: TenantScope) -> list[ModelCatalogItem]:
        return [item for key, item in self._items.items() if key[:2] == scope.key]

    def update(
        self, scope: TenantScope, item_id: str, **kwargs: Any
    ) -> ModelCatalogItem:
        with _LOCK:
            item = self._items.get(self._key(scope, item_id))
            if item is None:
                raise KeyError(f"不存在 {item_id}")
            for k, v in kwargs.items():
                if hasattr(item, k):
                    setattr(item, k, v)
            item.updated_at = time.time()
            return item

    def delete(self, scope: TenantScope, item_id: str) -> bool:
        with _LOCK:
            return self._items.pop(self._key(scope, item_id), None) is not None

    def reset(self, scope: TenantScope) -> None:
        """只清空指定租户的目录实例。"""
        with _LOCK:
            for key in [key for key in self._items if key[:2] == scope.key]:
                self._items.pop(key)

    def reset_all_for_tests(self) -> None:
        """测试基础设施专用；生产路由不得调用。"""
        with _LOCK:
            self._items.clear()


def get_engine() -> ModelCatalogEngine:
    return ModelCatalogEngine()
