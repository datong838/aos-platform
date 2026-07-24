"""
W5 — 链接 Object 视图
Tests: LinkedObjectViewEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oe_linked_view import LinkedObjectView, LinkedObjectViewEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    LinkedObjectViewEngine().reset()
    yield
    LinkedObjectViewEngine().reset()


class TestLinkedObjectViewEngine:
    def test_register(self):
        item = LinkedObjectView(name="test-item")
        result = LinkedObjectViewEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = LinkedObjectView(name="get-test")
        LinkedObjectViewEngine().register(item)
        found = LinkedObjectViewEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert LinkedObjectViewEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            LinkedObjectViewEngine().register(LinkedObjectView(name=f"list-{i}"))
        items = LinkedObjectViewEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = LinkedObjectView(name="original")
        LinkedObjectViewEngine().register(item)
        updated = LinkedObjectViewEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert LinkedObjectViewEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = LinkedObjectView(name="delete-me")
        LinkedObjectViewEngine().register(item)
        assert LinkedObjectViewEngine().delete(item.id) is True
        assert LinkedObjectViewEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            LinkedObjectViewEngine().register(LinkedObjectView(name=f"cap-{i}"))
        assert len(LinkedObjectViewEngine().list()) == 100

    def test_singleton(self):
        e1 = LinkedObjectViewEngine()
        e2 = LinkedObjectViewEngine()
        assert e1 is e2
