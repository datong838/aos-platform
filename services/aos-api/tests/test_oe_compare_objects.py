"""
W5 — 比较对象集
Tests: CompareObjectsEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oe_compare_objects import CompareObjects, CompareObjectsEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CompareObjectsEngine().reset()
    yield
    CompareObjectsEngine().reset()


class TestCompareObjectsEngine:
    def test_register(self):
        item = CompareObjects(name="test-item")
        result = CompareObjectsEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CompareObjects(name="get-test")
        CompareObjectsEngine().register(item)
        found = CompareObjectsEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CompareObjectsEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CompareObjectsEngine().register(CompareObjects(name=f"list-{i}"))
        items = CompareObjectsEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CompareObjects(name="original")
        CompareObjectsEngine().register(item)
        updated = CompareObjectsEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CompareObjectsEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CompareObjects(name="delete-me")
        CompareObjectsEngine().register(item)
        assert CompareObjectsEngine().delete(item.id) is True
        assert CompareObjectsEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CompareObjectsEngine().register(CompareObjects(name=f"cap-{i}"))
        assert len(CompareObjectsEngine().list()) == 100

    def test_singleton(self):
        e1 = CompareObjectsEngine()
        e2 = CompareObjectsEngine()
        assert e1 is e2
