"""
W5 — 多 Spoke 监控
Tests: MultiSpokeMonitorEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cp_multi_spoke_monitor import MultiSpokeMonitor, MultiSpokeMonitorEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    MultiSpokeMonitorEngine().reset()
    yield
    MultiSpokeMonitorEngine().reset()


class TestMultiSpokeMonitorEngine:
    def test_register(self):
        item = MultiSpokeMonitor(name="test-item")
        result = MultiSpokeMonitorEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = MultiSpokeMonitor(name="get-test")
        MultiSpokeMonitorEngine().register(item)
        found = MultiSpokeMonitorEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert MultiSpokeMonitorEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            MultiSpokeMonitorEngine().register(MultiSpokeMonitor(name=f"list-{i}"))
        items = MultiSpokeMonitorEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = MultiSpokeMonitor(name="original")
        MultiSpokeMonitorEngine().register(item)
        updated = MultiSpokeMonitorEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert MultiSpokeMonitorEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = MultiSpokeMonitor(name="delete-me")
        MultiSpokeMonitorEngine().register(item)
        assert MultiSpokeMonitorEngine().delete(item.id) is True
        assert MultiSpokeMonitorEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            MultiSpokeMonitorEngine().register(MultiSpokeMonitor(name=f"cap-{i}"))
        assert len(MultiSpokeMonitorEngine().list()) == 100

    def test_singleton(self):
        e1 = MultiSpokeMonitorEngine()
        e2 = MultiSpokeMonitorEngine()
        assert e1 is e2
