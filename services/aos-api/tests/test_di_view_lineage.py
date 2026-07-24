"""W3 Task 2.1 · 视图血缘图（220w L788） 测试."""
from __future__ import annotations

import pytest

from aos_api.di_view_lineage import (
    ViewLineageEdge,
    ViewLineageEngine,
    ViewLineageError,
    get_engine,
)


class TestViewLineageEngine:
    def setup_method(self) -> None:
        self.eng = ViewLineageEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> ViewLineageEdge:
        defaults: dict = {}
        return ViewLineageEdge(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "vl_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "vl_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(ViewLineageError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "vl_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(ViewLineageError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "vl_id"))
        with pytest.raises(ViewLineageError):
            self.eng.get(getattr(item, "vl_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestViewLineageEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
