"""
W6 — 虚拟表创建
Tests: VirtualTableCreateEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.di_virtual_table_create import VirtualTableCreate, VirtualTableCreateEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    VirtualTableCreateEngine().reset()
    yield
    VirtualTableCreateEngine().reset()


class TestVirtualTableCreateEngine:
    def test_register(self):
        item = VirtualTableCreate(name="test-item")
        result = VirtualTableCreateEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = VirtualTableCreate(name="get-test")
        VirtualTableCreateEngine().register(item)
        found = VirtualTableCreateEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert VirtualTableCreateEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            VirtualTableCreateEngine().register(VirtualTableCreate(name=f"list-{i}"))
        items = VirtualTableCreateEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = VirtualTableCreate(name="original")
        VirtualTableCreateEngine().register(item)
        updated = VirtualTableCreateEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert VirtualTableCreateEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = VirtualTableCreate(name="delete-me")
        VirtualTableCreateEngine().register(item)
        assert VirtualTableCreateEngine().delete(item.id) is True
        assert VirtualTableCreateEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            VirtualTableCreateEngine().register(VirtualTableCreate(name=f"cap-{i}"))
        assert len(VirtualTableCreateEngine().list()) == 100

    def test_singleton(self):
        e1 = VirtualTableCreateEngine()
        e2 = VirtualTableCreateEngine()
        assert e1 is e2
