"""
W5 — 命令面板集成
Tests: CommandPaletteEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_command_palette import CommandPalette, CommandPaletteEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CommandPaletteEngine().reset()
    yield
    CommandPaletteEngine().reset()


class TestCommandPaletteEngine:
    def test_register(self):
        item = CommandPalette(name="test-item")
        result = CommandPaletteEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CommandPalette(name="get-test")
        CommandPaletteEngine().register(item)
        found = CommandPaletteEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CommandPaletteEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CommandPaletteEngine().register(CommandPalette(name=f"list-{i}"))
        items = CommandPaletteEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CommandPalette(name="original")
        CommandPaletteEngine().register(item)
        updated = CommandPaletteEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CommandPaletteEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CommandPalette(name="delete-me")
        CommandPaletteEngine().register(item)
        assert CommandPaletteEngine().delete(item.id) is True
        assert CommandPaletteEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CommandPaletteEngine().register(CommandPalette(name=f"cap-{i}"))
        assert len(CommandPaletteEngine().list()) == 100

    def test_singleton(self):
        e1 = CommandPaletteEngine()
        e2 = CommandPaletteEngine()
        assert e1 is e2
