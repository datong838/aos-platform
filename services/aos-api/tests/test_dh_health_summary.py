"""
W5 — 项目健康检查摘要
Tests: HealthSummaryEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.dh_health_summary import HealthSummary, HealthSummaryEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    HealthSummaryEngine().reset()
    yield
    HealthSummaryEngine().reset()


class TestHealthSummaryEngine:
    def test_register(self):
        item = HealthSummary(name="test-item")
        result = HealthSummaryEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = HealthSummary(name="get-test")
        HealthSummaryEngine().register(item)
        found = HealthSummaryEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert HealthSummaryEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            HealthSummaryEngine().register(HealthSummary(name=f"list-{i}"))
        items = HealthSummaryEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = HealthSummary(name="original")
        HealthSummaryEngine().register(item)
        updated = HealthSummaryEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert HealthSummaryEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = HealthSummary(name="delete-me")
        HealthSummaryEngine().register(item)
        assert HealthSummaryEngine().delete(item.id) is True
        assert HealthSummaryEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            HealthSummaryEngine().register(HealthSummary(name=f"cap-{i}"))
        assert len(HealthSummaryEngine().list()) == 100

    def test_singleton(self):
        e1 = HealthSummaryEngine()
        e2 = HealthSummaryEngine()
        assert e1 is e2
