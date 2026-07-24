"""
W6 — 编辑器右键菜单
Tests: EditorContextMenuEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_editor_context_menu import EditorContextMenu, EditorContextMenuEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    EditorContextMenuEngine().reset()
    yield
    EditorContextMenuEngine().reset()


class TestEditorContextMenuEngine:
    def test_register(self):
        item = EditorContextMenu(name="test-item")
        result = EditorContextMenuEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = EditorContextMenu(name="get-test")
        EditorContextMenuEngine().register(item)
        found = EditorContextMenuEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert EditorContextMenuEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            EditorContextMenuEngine().register(EditorContextMenu(name=f"list-{i}"))
        items = EditorContextMenuEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = EditorContextMenu(name="original")
        EditorContextMenuEngine().register(item)
        updated = EditorContextMenuEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert EditorContextMenuEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = EditorContextMenu(name="delete-me")
        EditorContextMenuEngine().register(item)
        assert EditorContextMenuEngine().delete(item.id) is True
        assert EditorContextMenuEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            EditorContextMenuEngine().register(EditorContextMenu(name=f"cap-{i}"))
        assert len(EditorContextMenuEngine().list()) == 100

    def test_singleton(self):
        e1 = EditorContextMenuEngine()
        e2 = EditorContextMenuEngine()
        assert e1 is e2
