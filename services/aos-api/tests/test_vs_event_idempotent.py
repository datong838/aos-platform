"""
W5 — 事件幂等
Tests: EventIdempotentEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.vs_event_idempotent import EventIdempotent, EventIdempotentEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    EventIdempotentEngine().reset()
    yield
    EventIdempotentEngine().reset()


class TestEventIdempotentEngine:
    def test_register(self):
        item = EventIdempotent(name="test-item")
        result = EventIdempotentEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = EventIdempotent(name="get-test")
        EventIdempotentEngine().register(item)
        found = EventIdempotentEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert EventIdempotentEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            EventIdempotentEngine().register(EventIdempotent(name=f"list-{i}"))
        items = EventIdempotentEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = EventIdempotent(name="original")
        EventIdempotentEngine().register(item)
        updated = EventIdempotentEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert EventIdempotentEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = EventIdempotent(name="delete-me")
        EventIdempotentEngine().register(item)
        assert EventIdempotentEngine().delete(item.id) is True
        assert EventIdempotentEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            EventIdempotentEngine().register(EventIdempotent(name=f"cap-{i}"))
        assert len(EventIdempotentEngine().list()) == 100

    def test_singleton(self):
        e1 = EventIdempotentEngine()
        e2 = EventIdempotentEngine()
        assert e1 is e2
