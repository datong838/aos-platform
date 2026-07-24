"""
W5 — 流标签
Tests: StreamTagEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_stream_tag import StreamTag, StreamTagEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    StreamTagEngine().reset()
    yield
    StreamTagEngine().reset()


class TestStreamTagEngine:
    def test_register(self):
        item = StreamTag(name="test-item")
        result = StreamTagEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = StreamTag(name="get-test")
        StreamTagEngine().register(item)
        found = StreamTagEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert StreamTagEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            StreamTagEngine().register(StreamTag(name=f"list-{i}"))
        items = StreamTagEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = StreamTag(name="original")
        StreamTagEngine().register(item)
        updated = StreamTagEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert StreamTagEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = StreamTag(name="delete-me")
        StreamTagEngine().register(item)
        assert StreamTagEngine().delete(item.id) is True
        assert StreamTagEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            StreamTagEngine().register(StreamTag(name=f"cap-{i}"))
        assert len(StreamTagEngine().list()) == 100

    def test_singleton(self):
        e1 = StreamTagEngine()
        e2 = StreamTagEngine()
        assert e1 is e2
