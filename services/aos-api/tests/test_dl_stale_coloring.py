"W4 · 过时着色（220w L549） 测试."""
from __future__ import annotations

import pytest

from aos_api.dl_stale_coloring import (
    StaleColoring,
    StaleColoringEngine,
    StaleColoringError,
    get_engine,
)


class TestStaleColoringEngine:
    def setup_method(self) -> None:
        self.eng = StaleColoringEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> StaleColoring:
        return StaleColoring(**kw)

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "sc_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "sc_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(StaleColoringError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "sc_id"), {"name": "updated"})
        assert updated.name == "updated"

    def test_update_not_found(self) -> None:
        with pytest.raises(StaleColoringError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "sc_id"))
        with pytest.raises(StaleColoringError):
            self.eng.get(getattr(item, "sc_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestStaleColoringSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
