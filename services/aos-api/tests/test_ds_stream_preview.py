"""
W5 — 流数据预览
Tests: StreamPreviewEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_stream_preview import StreamPreview, StreamPreviewEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    StreamPreviewEngine().reset()
    yield
    StreamPreviewEngine().reset()


class TestStreamPreviewEngine:
    def test_register(self):
        item = StreamPreview(name="test-item")
        result = StreamPreviewEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = StreamPreview(name="get-test")
        StreamPreviewEngine().register(item)
        found = StreamPreviewEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert StreamPreviewEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            StreamPreviewEngine().register(StreamPreview(name=f"list-{i}"))
        items = StreamPreviewEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = StreamPreview(name="original")
        StreamPreviewEngine().register(item)
        updated = StreamPreviewEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert StreamPreviewEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = StreamPreview(name="delete-me")
        StreamPreviewEngine().register(item)
        assert StreamPreviewEngine().delete(item.id) is True
        assert StreamPreviewEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            StreamPreviewEngine().register(StreamPreview(name=f"cap-{i}"))
        assert len(StreamPreviewEngine().list()) == 100

    def test_singleton(self):
        e1 = StreamPreviewEngine()
        e2 = StreamPreviewEngine()
        assert e1 is e2
