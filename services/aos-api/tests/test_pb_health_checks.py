"""W3 Task 5.5 · 健康检查配置（任务级/搭建级/新鲜度检查）（220w L1265） 测试."""
from __future__ import annotations

import pytest

from aos_api.pb_health_checks import (
    HealthCheckConfig,
    HealthCheckEngine,
    HealthCheckError,
    get_engine,
)


class TestHealthCheckEngine:
    def setup_method(self) -> None:
        self.eng = HealthCheckEngine()
        self.eng._items = {}

    def _mk(self, **kw) -> HealthCheckConfig:
        defaults: dict = {}
        return HealthCheckConfig(**{**defaults, **kw})

    def test_register(self) -> None:
        item = self.eng.register(self._mk())
        assert "hc_id" in item.model_dump()

    def test_get(self) -> None:
        item = self.eng.register(self._mk())
        got = self.eng.get(getattr(item, "hc_id"))
        assert got is not None

    def test_get_not_found(self) -> None:
        with pytest.raises(HealthCheckError) as exc:
            self.eng.get("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk())
        self.eng.register(self._mk())
        assert len(self.eng.list()) == 2

    def test_update(self) -> None:
        item = self.eng.register(self._mk())
        updated = self.eng.update(getattr(item, "hc_id"), {"_test": True})
        assert updated.updated_at is not None

    def test_update_not_found(self) -> None:
        with pytest.raises(HealthCheckError):
            self.eng.update("x", {"y": 1})

    def test_delete(self) -> None:
        item = self.eng.register(self._mk())
        self.eng.delete(getattr(item, "hc_id"))
        with pytest.raises(HealthCheckError):
            self.eng.get(getattr(item, "hc_id"))

    def test_capacity_limit(self) -> None:
        for _ in range(205):
            self.eng.register(self._mk())
        assert len(self.eng._items) <= 200


class TestHealthCheckEngineSingleton:
    def test_singleton(self) -> None:
        assert get_engine() is get_engine()
