"W4 · 构建受影响数据集（220w L1825） 测试."""
from __future__ import annotations

import pytest

from aos_api.cr_build_affected import (
    BuildAffected,
    BuildAffectedEngine,
    BuildAffectedError,
    get_engine,
)


class TestBuildAffectedEngine:
    def setup_method(self) -> None:
        self.eng = BuildAffectedEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> BuildAffected:
        return BuildAffected(**kw)

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "baf_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "baf_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(BuildAffectedError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "baf_id"), {"name": "updated"})
        assert updated.name == "updated"

    def test_update_not_found(self) -> None:
        with pytest.raises(BuildAffectedError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "baf_id"))
        with pytest.raises(BuildAffectedError):
            self.eng.get(getattr(item, "baf_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestBuildAffectedSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
