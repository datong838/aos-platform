"""W3 Task 2.2 · 任务调试（220w L2079） 测试."""
from __future__ import annotations

import pytest

from aos_api.di_task_debug import (
    DebugSession,
    TaskDebugEngine,
    TaskDebugError,
    get_engine,
)


class TestTaskDebugEngine:
    def setup_method(self) -> None:
        self.eng = TaskDebugEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> DebugSession:
        defaults: dict = {}
        return DebugSession(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "td_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "td_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(TaskDebugError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "td_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(TaskDebugError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "td_id"))
        with pytest.raises(TaskDebugError):
            self.eng.get(getattr(item, "td_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestTaskDebugEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
