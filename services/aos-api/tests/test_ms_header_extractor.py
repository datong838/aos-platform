"""W3 Task 7.1 · 表格表头提取器（220w L1978） 测试."""
from __future__ import annotations

import pytest

from aos_api.ms_header_extractor import (
    HeaderExtraction,
    HeaderExtractorEngine,
    HeaderExtractorError,
    get_engine,
)


class TestHeaderExtractorEngine:
    def setup_method(self) -> None:
        self.eng = HeaderExtractorEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> HeaderExtraction:
        defaults: dict = {}
        return HeaderExtraction(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "he_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "he_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(HeaderExtractorError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "he_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(HeaderExtractorError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "he_id"))
        with pytest.raises(HeaderExtractorError):
            self.eng.get(getattr(item, "he_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestHeaderExtractorEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
