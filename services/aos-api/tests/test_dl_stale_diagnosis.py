"""W3 Task 3.4 · 过时数据集诊断（220w L652） 测试."""
from __future__ import annotations

import pytest

from aos_api.dl_stale_diagnosis import (
    StaleDiagnosis,
    StaleDiagnosisEngine,
    StaleDiagnosisError,
    get_engine,
)


class TestStaleDiagnosisEngine:
    def setup_method(self) -> None:
        self.eng = StaleDiagnosisEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> StaleDiagnosis:
        defaults: dict = {}
        return StaleDiagnosis(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "sd_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "sd_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(StaleDiagnosisError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "sd_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(StaleDiagnosisError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "sd_id"))
        with pytest.raises(StaleDiagnosisError):
            self.eng.get(getattr(item, "sd_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestStaleDiagnosisEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
