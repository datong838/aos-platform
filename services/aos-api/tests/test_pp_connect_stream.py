"""
W5 — 连接流
Tests: ConnectStreamEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_connect_stream import ConnectStream, ConnectStreamEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ConnectStreamEngine().reset()
    yield
    ConnectStreamEngine().reset()


class TestConnectStreamEngine:
    def test_register(self):
        item = ConnectStream(name="test-item")
        result = ConnectStreamEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ConnectStream(name="get-test")
        ConnectStreamEngine().register(item)
        found = ConnectStreamEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ConnectStreamEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ConnectStreamEngine().register(ConnectStream(name=f"list-{i}"))
        items = ConnectStreamEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ConnectStream(name="original")
        ConnectStreamEngine().register(item)
        updated = ConnectStreamEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ConnectStreamEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ConnectStream(name="delete-me")
        ConnectStreamEngine().register(item)
        assert ConnectStreamEngine().delete(item.id) is True
        assert ConnectStreamEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ConnectStreamEngine().register(ConnectStream(name=f"cap-{i}"))
        assert len(ConnectStreamEngine().list()) == 100

    def test_singleton(self):
        e1 = ConnectStreamEngine()
        e2 = ConnectStreamEngine()
        assert e1 is e2
