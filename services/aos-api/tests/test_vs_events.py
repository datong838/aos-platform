"""
W5 — Events
Tests: VsEventsEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.vs_events import VsEvents, VsEventsEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    VsEventsEngine().reset()
    yield
    VsEventsEngine().reset()


class TestVsEventsEngine:
    def test_register(self):
        item = VsEvents(name="test-item")
        result = VsEventsEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = VsEvents(name="get-test")
        VsEventsEngine().register(item)
        found = VsEventsEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert VsEventsEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            VsEventsEngine().register(VsEvents(name=f"list-{i}"))
        items = VsEventsEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = VsEvents(name="original")
        VsEventsEngine().register(item)
        updated = VsEventsEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert VsEventsEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = VsEvents(name="delete-me")
        VsEventsEngine().register(item)
        assert VsEventsEngine().delete(item.id) is True
        assert VsEventsEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            VsEventsEngine().register(VsEvents(name=f"cap-{i}"))
        assert len(VsEventsEngine().list()) == 100

    def test_singleton(self):
        e1 = VsEventsEngine()
        e2 = VsEventsEngine()
        assert e1 is e2
