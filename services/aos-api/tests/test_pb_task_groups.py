"""W3 Task 5.4 · 任务组（输出分配/计算配置文件/权限继承）（220w L1242） 测试."""
from __future__ import annotations

import pytest

from aos_api.pb_task_groups import (
    TaskGroup,
    TaskGroupsEngine,
    TaskGroupsError,
    get_engine,
)


class TestTaskGroupsEngine:
    def setup_method(self) -> None:
        self.eng = TaskGroupsEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> TaskGroup:
        defaults: dict = {}
        return TaskGroup(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "tg_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "tg_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(TaskGroupsError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "tg_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(TaskGroupsError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "tg_id"))
        with pytest.raises(TaskGroupsError):
            self.eng.get(getattr(item, "tg_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestTaskGroupsEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
