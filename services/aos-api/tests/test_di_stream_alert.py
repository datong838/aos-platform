"""
W5 — 流监控告警
Tests: StreamAlertEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.di_stream_alert import StreamAlert, StreamAlertEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    StreamAlertEngine().reset()
    yield
    StreamAlertEngine().reset()


class TestStreamAlertEngine:
    def test_register(self):
        item = StreamAlert(name="test-item")
        result = StreamAlertEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = StreamAlert(name="get-test")
        StreamAlertEngine().register(item)
        found = StreamAlertEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert StreamAlertEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            StreamAlertEngine().register(StreamAlert(name=f"list-{i}"))
        items = StreamAlertEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = StreamAlert(name="original")
        StreamAlertEngine().register(item)
        updated = StreamAlertEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert StreamAlertEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = StreamAlert(name="delete-me")
        StreamAlertEngine().register(item)
        assert StreamAlertEngine().delete(item.id) is True
        assert StreamAlertEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            StreamAlertEngine().register(StreamAlert(name=f"cap-{i}"))
        assert len(StreamAlertEngine().list()) == 100

    def test_singleton(self):
        e1 = StreamAlertEngine()
        e2 = StreamAlertEngine()
        assert e1 is e2
