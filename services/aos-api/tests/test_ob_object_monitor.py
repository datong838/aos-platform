"""
W5 — 对象监视器
Tests: ObjectMonitorEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_object_monitor import ObjectMonitor, ObjectMonitorEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ObjectMonitorEngine().reset()
    yield
    ObjectMonitorEngine().reset()


class TestObjectMonitorEngine:
    def test_register(self):
        item = ObjectMonitor(name="test-item")
        result = ObjectMonitorEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ObjectMonitor(name="get-test")
        ObjectMonitorEngine().register(item)
        found = ObjectMonitorEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ObjectMonitorEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ObjectMonitorEngine().register(ObjectMonitor(name=f"list-{i}"))
        items = ObjectMonitorEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ObjectMonitor(name="original")
        ObjectMonitorEngine().register(item)
        updated = ObjectMonitorEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ObjectMonitorEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ObjectMonitor(name="delete-me")
        ObjectMonitorEngine().register(item)
        assert ObjectMonitorEngine().delete(item.id) is True
        assert ObjectMonitorEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ObjectMonitorEngine().register(ObjectMonitor(name=f"cap-{i}"))
        assert len(ObjectMonitorEngine().list()) == 100

    def test_singleton(self):
        e1 = ObjectMonitorEngine()
        e2 = ObjectMonitorEngine()
        assert e1 is e2
