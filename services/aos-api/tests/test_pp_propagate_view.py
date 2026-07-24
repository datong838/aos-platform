"""
W5 — 传播视图要求
Tests: PropagateViewEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_propagate_view import PropagateView, PropagateViewEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PropagateViewEngine().reset()
    yield
    PropagateViewEngine().reset()


class TestPropagateViewEngine:
    def test_register(self):
        item = PropagateView(name="test-item")
        result = PropagateViewEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PropagateView(name="get-test")
        PropagateViewEngine().register(item)
        found = PropagateViewEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PropagateViewEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PropagateViewEngine().register(PropagateView(name=f"list-{i}"))
        items = PropagateViewEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PropagateView(name="original")
        PropagateViewEngine().register(item)
        updated = PropagateViewEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PropagateViewEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PropagateView(name="delete-me")
        PropagateViewEngine().register(item)
        assert PropagateViewEngine().delete(item.id) is True
        assert PropagateViewEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PropagateViewEngine().register(PropagateView(name=f"cap-{i}"))
        assert len(PropagateViewEngine().list()) == 100

    def test_singleton(self):
        e1 = PropagateViewEngine()
        e2 = PropagateViewEngine()
        assert e1 is e2
