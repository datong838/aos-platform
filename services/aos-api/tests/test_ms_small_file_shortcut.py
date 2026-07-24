"""
W5 — 小文件短路
Tests: SmallFileShortcutEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_small_file_shortcut import SmallFileShortcut, SmallFileShortcutEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SmallFileShortcutEngine().reset()
    yield
    SmallFileShortcutEngine().reset()


class TestSmallFileShortcutEngine:
    def test_register(self):
        item = SmallFileShortcut(name="test-item")
        result = SmallFileShortcutEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SmallFileShortcut(name="get-test")
        SmallFileShortcutEngine().register(item)
        found = SmallFileShortcutEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SmallFileShortcutEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SmallFileShortcutEngine().register(SmallFileShortcut(name=f"list-{i}"))
        items = SmallFileShortcutEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SmallFileShortcut(name="original")
        SmallFileShortcutEngine().register(item)
        updated = SmallFileShortcutEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SmallFileShortcutEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SmallFileShortcut(name="delete-me")
        SmallFileShortcutEngine().register(item)
        assert SmallFileShortcutEngine().delete(item.id) is True
        assert SmallFileShortcutEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SmallFileShortcutEngine().register(SmallFileShortcut(name=f"cap-{i}"))
        assert len(SmallFileShortcutEngine().list()) == 100

    def test_singleton(self):
        e1 = SmallFileShortcutEngine()
        e2 = SmallFileShortcutEngine()
        assert e1 is e2
