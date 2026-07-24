"""
W5 — 动态模式拖放
Tests: DynamicDragDropEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.sc_dynamic_drag_drop import DynamicDragDrop, DynamicDragDropEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DynamicDragDropEngine().reset()
    yield
    DynamicDragDropEngine().reset()


class TestDynamicDragDropEngine:
    def test_register(self):
        item = DynamicDragDrop(name="test-item")
        result = DynamicDragDropEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DynamicDragDrop(name="get-test")
        DynamicDragDropEngine().register(item)
        found = DynamicDragDropEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DynamicDragDropEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DynamicDragDropEngine().register(DynamicDragDrop(name=f"list-{i}"))
        items = DynamicDragDropEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DynamicDragDrop(name="original")
        DynamicDragDropEngine().register(item)
        updated = DynamicDragDropEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DynamicDragDropEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DynamicDragDrop(name="delete-me")
        DynamicDragDropEngine().register(item)
        assert DynamicDragDropEngine().delete(item.id) is True
        assert DynamicDragDropEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DynamicDragDropEngine().register(DynamicDragDrop(name=f"cap-{i}"))
        assert len(DynamicDragDropEngine().list()) == 100

    def test_singleton(self):
        e1 = DynamicDragDropEngine()
        e2 = DynamicDragDropEngine()
        assert e1 is e2
