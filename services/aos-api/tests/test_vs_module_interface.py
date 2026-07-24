"""
W5 — Module interface
Tests: VsModuleInterfaceEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.vs_module_interface import VsModuleInterface, VsModuleInterfaceEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    VsModuleInterfaceEngine().reset()
    yield
    VsModuleInterfaceEngine().reset()


class TestVsModuleInterfaceEngine:
    def test_register(self):
        item = VsModuleInterface(name="test-item")
        result = VsModuleInterfaceEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = VsModuleInterface(name="get-test")
        VsModuleInterfaceEngine().register(item)
        found = VsModuleInterfaceEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert VsModuleInterfaceEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            VsModuleInterfaceEngine().register(VsModuleInterface(name=f"list-{i}"))
        items = VsModuleInterfaceEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = VsModuleInterface(name="original")
        VsModuleInterfaceEngine().register(item)
        updated = VsModuleInterfaceEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert VsModuleInterfaceEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = VsModuleInterface(name="delete-me")
        VsModuleInterfaceEngine().register(item)
        assert VsModuleInterfaceEngine().delete(item.id) is True
        assert VsModuleInterfaceEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            VsModuleInterfaceEngine().register(VsModuleInterface(name=f"cap-{i}"))
        assert len(VsModuleInterfaceEngine().list()) == 100

    def test_singleton(self):
        e1 = VsModuleInterfaceEngine()
        e2 = VsModuleInterfaceEngine()
        assert e1 is e2
