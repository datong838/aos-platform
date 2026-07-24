"""
W6 — 远程下发
Tests: RemoteDispatchEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.hs_remote_dispatch import RemoteDispatch, RemoteDispatchEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    RemoteDispatchEngine().reset()
    yield
    RemoteDispatchEngine().reset()


class TestRemoteDispatchEngine:
    def test_register(self):
        item = RemoteDispatch(name="test-item")
        result = RemoteDispatchEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = RemoteDispatch(name="get-test")
        RemoteDispatchEngine().register(item)
        found = RemoteDispatchEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert RemoteDispatchEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            RemoteDispatchEngine().register(RemoteDispatch(name=f"list-{i}"))
        items = RemoteDispatchEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = RemoteDispatch(name="original")
        RemoteDispatchEngine().register(item)
        updated = RemoteDispatchEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert RemoteDispatchEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = RemoteDispatch(name="delete-me")
        RemoteDispatchEngine().register(item)
        assert RemoteDispatchEngine().delete(item.id) is True
        assert RemoteDispatchEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            RemoteDispatchEngine().register(RemoteDispatch(name=f"cap-{i}"))
        assert len(RemoteDispatchEngine().list()) == 100

    def test_singleton(self):
        e1 = RemoteDispatchEngine()
        e2 = RemoteDispatchEngine()
        assert e1 is e2
