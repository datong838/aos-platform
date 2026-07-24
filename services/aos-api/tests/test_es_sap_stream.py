"""W3 Task 7.3 · SAP 实时流（220w L2188） 测试."""
from __future__ import annotations

import pytest

from aos_api.es_sap_stream import (
    SapStreamConfig,
    SapStreamEngine,
    SapStreamError,
    get_engine,
)


class TestSapStreamEngine:
    def setup_method(self) -> None:
        self.eng = SapStreamEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> SapStreamConfig:
        defaults: dict = {}
        return SapStreamConfig(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "ss_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "ss_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(SapStreamError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "ss_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(SapStreamError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "ss_id"))
        with pytest.raises(SapStreamError):
            self.eng.get(getattr(item, "ss_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestSapStreamEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
