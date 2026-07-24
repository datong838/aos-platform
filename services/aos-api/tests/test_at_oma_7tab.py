"""
W5 — OMA Action 编辑器7Tab
Tests: OmaSevenTabEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.at_oma_7tab import OmaSevenTab, OmaSevenTabEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    OmaSevenTabEngine().reset()
    yield
    OmaSevenTabEngine().reset()


class TestOmaSevenTabEngine:
    def test_register(self):
        item = OmaSevenTab(name="test-item")
        result = OmaSevenTabEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = OmaSevenTab(name="get-test")
        OmaSevenTabEngine().register(item)
        found = OmaSevenTabEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert OmaSevenTabEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            OmaSevenTabEngine().register(OmaSevenTab(name=f"list-{i}"))
        items = OmaSevenTabEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = OmaSevenTab(name="original")
        OmaSevenTabEngine().register(item)
        updated = OmaSevenTabEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert OmaSevenTabEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = OmaSevenTab(name="delete-me")
        OmaSevenTabEngine().register(item)
        assert OmaSevenTabEngine().delete(item.id) is True
        assert OmaSevenTabEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            OmaSevenTabEngine().register(OmaSevenTab(name=f"cap-{i}"))
        assert len(OmaSevenTabEngine().list()) == 100

    def test_singleton(self):
        e1 = OmaSevenTabEngine()
        e2 = OmaSevenTabEngine()
        assert e1 is e2
