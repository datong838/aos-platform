"""
W5 — 公共扩展支持
Tests: PublicExtensionEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_public_extension import PublicExtension, PublicExtensionEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PublicExtensionEngine().reset()
    yield
    PublicExtensionEngine().reset()


class TestPublicExtensionEngine:
    def test_register(self):
        item = PublicExtension(name="test-item")
        result = PublicExtensionEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PublicExtension(name="get-test")
        PublicExtensionEngine().register(item)
        found = PublicExtensionEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PublicExtensionEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PublicExtensionEngine().register(PublicExtension(name=f"list-{i}"))
        items = PublicExtensionEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PublicExtension(name="original")
        PublicExtensionEngine().register(item)
        updated = PublicExtensionEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PublicExtensionEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PublicExtension(name="delete-me")
        PublicExtensionEngine().register(item)
        assert PublicExtensionEngine().delete(item.id) is True
        assert PublicExtensionEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PublicExtensionEngine().register(PublicExtension(name=f"cap-{i}"))
        assert len(PublicExtensionEngine().list()) == 100

    def test_singleton(self):
        e1 = PublicExtensionEngine()
        e2 = PublicExtensionEngine()
        assert e1 is e2
