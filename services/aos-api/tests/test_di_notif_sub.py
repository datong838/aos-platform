"""
W5 — 通知订阅
Tests: NotifSubscriptionEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.di_notif_sub import NotifSubscription, NotifSubscriptionEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    NotifSubscriptionEngine().reset()
    yield
    NotifSubscriptionEngine().reset()


class TestNotifSubscriptionEngine:
    def test_register(self):
        item = NotifSubscription(name="test-item")
        result = NotifSubscriptionEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = NotifSubscription(name="get-test")
        NotifSubscriptionEngine().register(item)
        found = NotifSubscriptionEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert NotifSubscriptionEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            NotifSubscriptionEngine().register(NotifSubscription(name=f"list-{i}"))
        items = NotifSubscriptionEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = NotifSubscription(name="original")
        NotifSubscriptionEngine().register(item)
        updated = NotifSubscriptionEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert NotifSubscriptionEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = NotifSubscription(name="delete-me")
        NotifSubscriptionEngine().register(item)
        assert NotifSubscriptionEngine().delete(item.id) is True
        assert NotifSubscriptionEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            NotifSubscriptionEngine().register(NotifSubscription(name=f"cap-{i}"))
        assert len(NotifSubscriptionEngine().list()) == 100

    def test_singleton(self):
        e1 = NotifSubscriptionEngine()
        e2 = NotifSubscriptionEngine()
        assert e1 is e2
