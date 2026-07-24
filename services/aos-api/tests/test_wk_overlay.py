"""
W5 — Overlay
Tests: WkOverlayEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.wk_overlay import WkOverlay, WkOverlayEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    WkOverlayEngine().reset()
    yield
    WkOverlayEngine().reset()


class TestWkOverlayEngine:
    def test_register(self):
        item = WkOverlay(name="test-item")
        result = WkOverlayEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = WkOverlay(name="get-test")
        WkOverlayEngine().register(item)
        found = WkOverlayEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert WkOverlayEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            WkOverlayEngine().register(WkOverlay(name=f"list-{i}"))
        items = WkOverlayEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = WkOverlay(name="original")
        WkOverlayEngine().register(item)
        updated = WkOverlayEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert WkOverlayEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = WkOverlay(name="delete-me")
        WkOverlayEngine().register(item)
        assert WkOverlayEngine().delete(item.id) is True
        assert WkOverlayEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            WkOverlayEngine().register(WkOverlay(name=f"cap-{i}"))
        assert len(WkOverlayEngine().list()) == 100

    def test_singleton(self):
        e1 = WkOverlayEngine()
        e2 = WkOverlayEngine()
        assert e1 is e2
