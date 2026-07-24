"W4 · Force Build（220w L1351） 测试."""
from __future__ import annotations

import pytest

from aos_api.bd_force_build import (
    BdForceBuild,
    BdForceBuildEngine,
    BdForceBuildError,
    get_engine,
)


class TestBdForceBuildEngine:
    def setup_method(self) -> None:
        self.eng = BdForceBuildEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> BdForceBuild:
        return BdForceBuild(**kw)

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "bfb_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "bfb_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(BdForceBuildError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "bfb_id"), {"name": "updated"})
        assert updated.name == "updated"

    def test_update_not_found(self) -> None:
        with pytest.raises(BdForceBuildError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "bfb_id"))
        with pytest.raises(BdForceBuildError):
            self.eng.get(getattr(item, "bfb_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestBdForceBuildSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
