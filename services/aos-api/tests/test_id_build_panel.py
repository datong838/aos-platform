"""W3 Task 7.5 · Build 面板（3种启动方式）（220w L3655） 测试."""
from __future__ import annotations

import pytest

from aos_api.id_build_panel import (
    BuildPanelConfig,
    BuildPanelEngine,
    BuildPanelError,
    get_engine,
)


class TestBuildPanelEngine:
    def setup_method(self) -> None:
        self.eng = BuildPanelEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> BuildPanelConfig:
        defaults: dict = {}
        return BuildPanelConfig(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "ib_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "ib_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(BuildPanelError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "ib_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(BuildPanelError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "ib_id"))
        with pytest.raises(BuildPanelError):
            self.eng.get(getattr(item, "ib_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestBuildPanelEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
