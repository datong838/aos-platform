"W4 · 反引号数据集搜索（220w L1583） 测试."""
from __future__ import annotations

import pytest

from aos_api.ds_backtick_search import (
    BacktickSearch,
    BacktickSearchEngine,
    BacktickSearchError,
    get_engine,
)


class TestBacktickSearchEngine:
    def setup_method(self) -> None:
        self.eng = BacktickSearchEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> BacktickSearch:
        return BacktickSearch(**kw)

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "bs_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "bs_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(BacktickSearchError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "bs_id"), {"name": "updated"})
        assert updated.name == "updated"

    def test_update_not_found(self) -> None:
        with pytest.raises(BacktickSearchError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "bs_id"))
        with pytest.raises(BacktickSearchError):
            self.eng.get(getattr(item, "bs_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestBacktickSearchSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
