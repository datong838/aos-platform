"""
W5 — 监视器活动历史
Tests: MonitorActivityEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_monitor_activity import MonitorActivity, MonitorActivityEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MonitorActivityEngine().reset()
    yield
    MonitorActivityEngine().reset()


class TestMonitorActivityEngine:
    def test_register(self):
        item = MonitorActivity(name="test-item")
        result = MonitorActivityEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MonitorActivity(name="get-test")
        MonitorActivityEngine().register(item)
        found = MonitorActivityEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MonitorActivityEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MonitorActivityEngine().register(MonitorActivity(name=f"list-{i}"))
        items = MonitorActivityEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MonitorActivity(name="original")
        MonitorActivityEngine().register(item)
        updated = MonitorActivityEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MonitorActivityEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MonitorActivity(name="delete-me")
        MonitorActivityEngine().register(item)
        assert MonitorActivityEngine().delete(item.id) is True
        assert MonitorActivityEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MonitorActivityEngine().register(MonitorActivity(name=f"cap-{i}"))
        assert len(MonitorActivityEngine().list()) == 100

    def test_singleton(self):
        e1 = MonitorActivityEngine()
        e2 = MonitorActivityEngine()
        assert e1 is e2
