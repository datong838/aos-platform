"""W3 Task 3.3 · 依赖顺序搭建（220w L594） 测试."""
from __future__ import annotations

import pytest

from aos_api.dl_dep_order import (
    DependencyEdge,
    DependencyOrderEngine,
    DependencyOrderError,
    get_engine,
)


class TestDependencyOrderEngine:
    def setup_method(self) -> None:
        self.eng = DependencyOrderEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> DependencyEdge:
        defaults: dict = {}
        return DependencyEdge(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "do_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "do_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(DependencyOrderError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "do_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(DependencyOrderError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "do_id"))
        with pytest.raises(DependencyOrderError):
            self.eng.get(getattr(item, "do_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestDependencyOrderEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
