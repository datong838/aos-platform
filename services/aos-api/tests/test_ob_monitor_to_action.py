"""
W5 — 监视器自动操作
Tests: MonitorToActionEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_monitor_to_action import MonitorToAction, MonitorToActionEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MonitorToActionEngine().reset()
    yield
    MonitorToActionEngine().reset()


class TestMonitorToActionEngine:
    def test_register(self):
        item = MonitorToAction(name="test-item")
        result = MonitorToActionEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MonitorToAction(name="get-test")
        MonitorToActionEngine().register(item)
        found = MonitorToActionEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MonitorToActionEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MonitorToActionEngine().register(MonitorToAction(name=f"list-{i}"))
        items = MonitorToActionEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MonitorToAction(name="original")
        MonitorToActionEngine().register(item)
        updated = MonitorToActionEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MonitorToActionEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MonitorToAction(name="delete-me")
        MonitorToActionEngine().register(item)
        assert MonitorToActionEngine().delete(item.id) is True
        assert MonitorToActionEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MonitorToActionEngine().register(MonitorToAction(name=f"cap-{i}"))
        assert len(MonitorToActionEngine().list()) == 100

    def test_singleton(self):
        e1 = MonitorToActionEngine()
        e2 = MonitorToActionEngine()
        assert e1 is e2
