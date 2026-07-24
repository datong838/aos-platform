"""
W5 — 接口元数据
Tests: InterfaceMetadataEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.if_interface_metadata import InterfaceMetadata, InterfaceMetadataEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    InterfaceMetadataEngine().reset()
    yield
    InterfaceMetadataEngine().reset()


class TestInterfaceMetadataEngine:
    def test_register(self):
        item = InterfaceMetadata(name="test-item")
        result = InterfaceMetadataEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = InterfaceMetadata(name="get-test")
        InterfaceMetadataEngine().register(item)
        found = InterfaceMetadataEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert InterfaceMetadataEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            InterfaceMetadataEngine().register(InterfaceMetadata(name=f"list-{i}"))
        items = InterfaceMetadataEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = InterfaceMetadata(name="original")
        InterfaceMetadataEngine().register(item)
        updated = InterfaceMetadataEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert InterfaceMetadataEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = InterfaceMetadata(name="delete-me")
        InterfaceMetadataEngine().register(item)
        assert InterfaceMetadataEngine().delete(item.id) is True
        assert InterfaceMetadataEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            InterfaceMetadataEngine().register(InterfaceMetadata(name=f"cap-{i}"))
        assert len(InterfaceMetadataEngine().list()) == 100

    def test_singleton(self):
        e1 = InterfaceMetadataEngine()
        e2 = InterfaceMetadataEngine()
        assert e1 is e2
