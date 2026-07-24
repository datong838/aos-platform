"""
W5 — 索引监控视图
Tests: IndexMonitorEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_index_monitor import IndexMonitor, IndexMonitorEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    IndexMonitorEngine().reset()
    yield
    IndexMonitorEngine().reset()


class TestIndexMonitorEngine:
    def test_register(self):
        item = IndexMonitor(name="test-item")
        result = IndexMonitorEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = IndexMonitor(name="get-test")
        IndexMonitorEngine().register(item)
        found = IndexMonitorEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert IndexMonitorEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            IndexMonitorEngine().register(IndexMonitor(name=f"list-{i}"))
        items = IndexMonitorEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = IndexMonitor(name="original")
        IndexMonitorEngine().register(item)
        updated = IndexMonitorEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert IndexMonitorEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = IndexMonitor(name="delete-me")
        IndexMonitorEngine().register(item)
        assert IndexMonitorEngine().delete(item.id) is True
        assert IndexMonitorEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            IndexMonitorEngine().register(IndexMonitor(name=f"cap-{i}"))
        assert len(IndexMonitorEngine().list()) == 100

    def test_singleton(self):
        e1 = IndexMonitorEngine()
        e2 = IndexMonitorEngine()
        assert e1 is e2
