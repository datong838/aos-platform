"""
W5 — Shell 终端
Tests: ShellTerminalEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_shell_terminal import ShellTerminal, ShellTerminalEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ShellTerminalEngine().reset()
    yield
    ShellTerminalEngine().reset()


class TestShellTerminalEngine:
    def test_register(self):
        item = ShellTerminal(name="test-item")
        result = ShellTerminalEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ShellTerminal(name="get-test")
        ShellTerminalEngine().register(item)
        found = ShellTerminalEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ShellTerminalEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ShellTerminalEngine().register(ShellTerminal(name=f"list-{i}"))
        items = ShellTerminalEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ShellTerminal(name="original")
        ShellTerminalEngine().register(item)
        updated = ShellTerminalEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ShellTerminalEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ShellTerminal(name="delete-me")
        ShellTerminalEngine().register(item)
        assert ShellTerminalEngine().delete(item.id) is True
        assert ShellTerminalEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ShellTerminalEngine().register(ShellTerminal(name=f"cap-{i}"))
        assert len(ShellTerminalEngine().list()) == 100

    def test_singleton(self):
        e1 = ShellTerminalEngine()
        e2 = ShellTerminalEngine()
        assert e1 is e2
