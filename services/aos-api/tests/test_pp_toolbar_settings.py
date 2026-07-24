"""W3 Task 5.1 · 顶部工具栏-搭建设置（220w L1005） 测试."""
from __future__ import annotations

import pytest

from aos_api.pp_toolbar_settings import (
    ToolbarSetting,
    ToolbarSettingsEngine,
    ToolbarSettingsError,
    get_engine,
)


class TestToolbarSettingsEngine:
    def setup_method(self) -> None:
        self.eng = ToolbarSettingsEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> ToolbarSetting:
        defaults: dict = {}
        return ToolbarSetting(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "ts_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "ts_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(ToolbarSettingsError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "ts_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(ToolbarSettingsError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "ts_id"))
        with pytest.raises(ToolbarSettingsError):
            self.eng.get(getattr(item, "ts_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestToolbarSettingsEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
