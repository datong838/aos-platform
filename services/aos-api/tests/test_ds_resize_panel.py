"""
W5 — 可调整列宽面板
Tests: ResizePanelEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_resize_panel import ResizePanel, ResizePanelEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ResizePanelEngine().reset()
    yield
    ResizePanelEngine().reset()


class TestResizePanelEngine:
    def test_register(self):
        item = ResizePanel(name="test-item")
        result = ResizePanelEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ResizePanel(name="get-test")
        ResizePanelEngine().register(item)
        found = ResizePanelEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ResizePanelEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ResizePanelEngine().register(ResizePanel(name=f"list-{i}"))
        items = ResizePanelEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ResizePanel(name="original")
        ResizePanelEngine().register(item)
        updated = ResizePanelEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ResizePanelEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ResizePanel(name="delete-me")
        ResizePanelEngine().register(item)
        assert ResizePanelEngine().delete(item.id) is True
        assert ResizePanelEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ResizePanelEngine().register(ResizePanel(name=f"cap-{i}"))
        assert len(ResizePanelEngine().list()) == 100

    def test_singleton(self):
        e1 = ResizePanelEngine()
        e2 = ResizePanelEngine()
        assert e1 is e2
