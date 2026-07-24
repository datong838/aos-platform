"""
W5 — Edited 字段标记
Tests: AtEditedMarkerEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.at_edited_marker import AtEditedMarker, AtEditedMarkerEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    AtEditedMarkerEngine().reset()
    yield
    AtEditedMarkerEngine().reset()


class TestAtEditedMarkerEngine:
    def test_register(self):
        item = AtEditedMarker(name="test-item")
        result = AtEditedMarkerEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = AtEditedMarker(name="get-test")
        AtEditedMarkerEngine().register(item)
        found = AtEditedMarkerEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert AtEditedMarkerEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            AtEditedMarkerEngine().register(AtEditedMarker(name=f"list-{i}"))
        items = AtEditedMarkerEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = AtEditedMarker(name="original")
        AtEditedMarkerEngine().register(item)
        updated = AtEditedMarkerEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert AtEditedMarkerEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = AtEditedMarker(name="delete-me")
        AtEditedMarkerEngine().register(item)
        assert AtEditedMarkerEngine().delete(item.id) is True
        assert AtEditedMarkerEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            AtEditedMarkerEngine().register(AtEditedMarker(name=f"cap-{i}"))
        assert len(AtEditedMarkerEngine().list()) == 100

    def test_singleton(self):
        e1 = AtEditedMarkerEngine()
        e2 = AtEditedMarkerEngine()
        assert e1 is e2
