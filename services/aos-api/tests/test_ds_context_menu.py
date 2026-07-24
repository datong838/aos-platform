"""W3 Task 4.1 · 数据集操作菜单（220w L1537） 测试."""
from __future__ import annotations

import pytest

from aos_api.ds_context_menu import (
    DatasetAction,
    DatasetContextMenuEngine,
    DatasetContextMenuError,
    get_engine,
)


class TestDatasetContextMenuEngine:
    def setup_method(self) -> None:
        self.eng = DatasetContextMenuEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> DatasetAction:
        defaults: dict = {}
        return DatasetAction(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "da_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "da_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(DatasetContextMenuError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "da_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(DatasetContextMenuError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "da_id"))
        with pytest.raises(DatasetContextMenuError):
            self.eng.get(getattr(item, "da_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestDatasetContextMenuEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
