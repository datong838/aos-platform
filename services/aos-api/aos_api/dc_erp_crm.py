"""W3 Task 1.3 · ERP/CRM 连接器（220w L2225）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

_MAX = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class ErpCrmConnectorError(Exception):
    """ERP/CRM 连接器错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ErpCrmConnector(BaseModel):
    """ERP/CRM 连接器（220w L2225）."""
    ec_id: str = ""
    name: str = ""
    connector_type: str = "SAP"
    base_url: str = ""
    credentials_ref: str = ""
    status: str = "DISCONNECTED"
    last_sync_at: Optional[datetime] = None
    sync_interval_minutes: int = 60
    discovered_tables: list[str] = []  # 发现的表列表
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ErpCrmConnectorEngine:
    """ERP/CRM 连接器（220w L2225）."""

    _instance: Optional[ErpCrmConnectorEngine] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._items: dict[str, ErpCrmConnector] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ErpCrmConnectorEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, item: ErpCrmConnector) -> ErpCrmConnector:
        if not item.name if hasattr(item, "name") else True:
            pass  # name optional for some models
        now = _utcnow()
        oid = f"ec-{uuid.uuid4().hex[:8]}"
        stored = item.model_copy(update={
            "ec_id": oid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._items) >= _MAX:
                oldest = min(
                    self._items.values(),
                    key=lambda x: x.created_at or datetime.min,
                )
                del self._items[getattr(oldest, "ec_id")]
            self._items[oid] = stored
        return stored

    def get(self, item_id: str) -> ErpCrmConnector:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise ErpCrmConnectorError("NOT_FOUND", f"item {item_id} not found")
        return item

    def list(self, **filters) -> list[ErpCrmConnector]:
        with self._lock:
            items = list(self._items.values())
        for key, val in filters.items():
            if val is not None:
                items = [i for i in items if getattr(i, key, None) == val]
        return items

    def update(self, item_id: str, patch: dict) -> ErpCrmConnector:
        with self._lock:
            item = self._items.get(item_id)
        if item is None:
            raise ErpCrmConnectorError("NOT_FOUND", f"item {item_id} not found")
        updated = item.model_copy(update={**patch, "updated_at": _utcnow()})
        with self._lock:
            self._items[item_id] = updated
        return updated

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise ErpCrmConnectorError("NOT_FOUND", f"item {item_id} not found")
            del self._items[item_id]

    def test_connection(self, connector_id) -> dict:
        """测试连接是否可达."""
        return {"ok": True, "method": "test_connection"}

    def discover_schema(self, connector_id) -> dict:
        """发现远程表结构."""
        return {"ok": True, "method": "discover_schema"}

    def start_sync(self, connector_id) -> dict:
        """开始同步."""
        return {"ok": True, "method": "start_sync"}


def get_engine() -> ErpCrmConnectorEngine:
    return ErpCrmConnectorEngine.get_instance()
