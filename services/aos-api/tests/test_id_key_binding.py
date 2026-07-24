"""
W5 — 键绑定自定义
Tests: KeyBindingEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_key_binding import KeyBinding, KeyBindingEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    KeyBindingEngine().reset()
    yield
    KeyBindingEngine().reset()


class TestKeyBindingEngine:
    def test_register(self):
        item = KeyBinding(name="test-item")
        result = KeyBindingEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = KeyBinding(name="get-test")
        KeyBindingEngine().register(item)
        found = KeyBindingEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert KeyBindingEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            KeyBindingEngine().register(KeyBinding(name=f"list-{i}"))
        items = KeyBindingEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = KeyBinding(name="original")
        KeyBindingEngine().register(item)
        updated = KeyBindingEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert KeyBindingEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = KeyBinding(name="delete-me")
        KeyBindingEngine().register(item)
        assert KeyBindingEngine().delete(item.id) is True
        assert KeyBindingEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            KeyBindingEngine().register(KeyBinding(name=f"cap-{i}"))
        assert len(KeyBindingEngine().list()) == 100

    def test_singleton(self):
        e1 = KeyBindingEngine()
        e2 = KeyBindingEngine()
        assert e1 is e2
