"""
W5 — 键盘快捷键
Tests: KeyboardShortcutEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_keyboard_shortcut import KeyboardShortcut, KeyboardShortcutEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    KeyboardShortcutEngine().reset()
    yield
    KeyboardShortcutEngine().reset()


class TestKeyboardShortcutEngine:
    def test_register(self):
        item = KeyboardShortcut(name="test-item")
        result = KeyboardShortcutEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = KeyboardShortcut(name="get-test")
        KeyboardShortcutEngine().register(item)
        found = KeyboardShortcutEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert KeyboardShortcutEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            KeyboardShortcutEngine().register(KeyboardShortcut(name=f"list-{i}"))
        items = KeyboardShortcutEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = KeyboardShortcut(name="original")
        KeyboardShortcutEngine().register(item)
        updated = KeyboardShortcutEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert KeyboardShortcutEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = KeyboardShortcut(name="delete-me")
        KeyboardShortcutEngine().register(item)
        assert KeyboardShortcutEngine().delete(item.id) is True
        assert KeyboardShortcutEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            KeyboardShortcutEngine().register(KeyboardShortcut(name=f"cap-{i}"))
        assert len(KeyboardShortcutEngine().list()) == 100

    def test_singleton(self):
        e1 = KeyboardShortcutEngine()
        e2 = KeyboardShortcutEngine()
        assert e1 is e2
