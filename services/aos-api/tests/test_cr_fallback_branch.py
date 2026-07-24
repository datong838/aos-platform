"W4 · 回退分支配置（220w L1810） 测试."""
from __future__ import annotations

import pytest

from aos_api.cr_fallback_branch import (
    FallbackBranch,
    FallbackBranchEngine,
    FallbackBranchError,
    get_engine,
)


class TestFallbackBranchEngine:
    def setup_method(self) -> None:
        self.eng = FallbackBranchEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> FallbackBranch:
        return FallbackBranch(**kw)

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "fbr_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "fbr_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(FallbackBranchError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "fbr_id"), {"name": "updated"})
        assert updated.name == "updated"

    def test_update_not_found(self) -> None:
        with pytest.raises(FallbackBranchError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "fbr_id"))
        with pytest.raises(FallbackBranchError):
            self.eng.get(getattr(item, "fbr_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestFallbackBranchSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
