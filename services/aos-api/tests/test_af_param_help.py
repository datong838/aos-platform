"W4 · 参数描述/帮助（220w L2894） 测试."""
from __future__ import annotations

import pytest

from aos_api.af_param_help import (
    ParamHelp,
    ParamHelpEngine,
    ParamHelpError,
    get_engine,
)


class TestParamHelpEngine:
    def setup_method(self) -> None:
        self.eng = ParamHelpEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> ParamHelp:
        return ParamHelp(**kw)

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "ph2_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "ph2_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(ParamHelpError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "ph2_id"), {"name": "updated"})
        assert updated.name == "updated"

    def test_update_not_found(self) -> None:
        with pytest.raises(ParamHelpError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "ph2_id"))
        with pytest.raises(ParamHelpError):
            self.eng.get(getattr(item, "ph2_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestParamHelpSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
