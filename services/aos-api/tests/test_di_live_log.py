"""
W5 — 实时日志
Tests: LiveLogEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.di_live_log import LiveLog, LiveLogEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    LiveLogEngine().reset()
    yield
    LiveLogEngine().reset()


class TestLiveLogEngine:
    def test_register(self):
        item = LiveLog(name="test-item")
        result = LiveLogEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = LiveLog(name="get-test")
        LiveLogEngine().register(item)
        found = LiveLogEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert LiveLogEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            LiveLogEngine().register(LiveLog(name=f"list-{i}"))
        items = LiveLogEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = LiveLog(name="original")
        LiveLogEngine().register(item)
        updated = LiveLogEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert LiveLogEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = LiveLog(name="delete-me")
        LiveLogEngine().register(item)
        assert LiveLogEngine().delete(item.id) is True
        assert LiveLogEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            LiveLogEngine().register(LiveLog(name=f"cap-{i}"))
        assert len(LiveLogEngine().list()) == 100

    def test_singleton(self):
        e1 = LiveLogEngine()
        e2 = LiveLogEngine()
        assert e1 is e2
