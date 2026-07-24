"""W3 Task 5.3 · 搭建设置（9种批处理+6种流式计算配置文件）（220w L1236） 测试."""
from __future__ import annotations

import pytest

from aos_api.pb_build_profiles import (
    BuildProfile,
    BuildProfilesEngine,
    BuildProfilesError,
    get_engine,
)


class TestBuildProfilesEngine:
    def setup_method(self) -> None:
        self.eng = BuildProfilesEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> BuildProfile:
        defaults: dict = {}
        return BuildProfile(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "pf_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "pf_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(BuildProfilesError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "pf_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(BuildProfilesError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "pf_id"))
        with pytest.raises(BuildProfilesError):
            self.eng.get(getattr(item, "pf_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestBuildProfilesEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
