"""W3 Task 1.2 · Stream 创建与管理（220w L182） 测试."""
from __future__ import annotations

import pytest

from aos_api.dc_stream_mgmt import (
    Stream,
    StreamManagementEngine,
    StreamManagementError,
    get_engine,
)


class TestStreamManagementEngine:
    def setup_method(self) -> None:
        self.eng = StreamManagementEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> Stream:
        defaults: dict = {}
        return Stream(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "sm_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "sm_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(StreamManagementError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "sm_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(StreamManagementError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "sm_id"))
        with pytest.raises(StreamManagementError):
            self.eng.get(getattr(item, "sm_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestStreamManagementEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
