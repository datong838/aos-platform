"""
W5 — Object Table 进阶
Tests: ObjectTableAdvancedEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.wk_object_table_advanced import ObjectTableAdvanced, ObjectTableAdvancedEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ObjectTableAdvancedEngine().reset()
    yield
    ObjectTableAdvancedEngine().reset()


class TestObjectTableAdvancedEngine:
    def test_register(self):
        item = ObjectTableAdvanced(name="test-item")
        result = ObjectTableAdvancedEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ObjectTableAdvanced(name="get-test")
        ObjectTableAdvancedEngine().register(item)
        found = ObjectTableAdvancedEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ObjectTableAdvancedEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ObjectTableAdvancedEngine().register(ObjectTableAdvanced(name=f"list-{i}"))
        items = ObjectTableAdvancedEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ObjectTableAdvanced(name="original")
        ObjectTableAdvancedEngine().register(item)
        updated = ObjectTableAdvancedEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ObjectTableAdvancedEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ObjectTableAdvanced(name="delete-me")
        ObjectTableAdvancedEngine().register(item)
        assert ObjectTableAdvancedEngine().delete(item.id) is True
        assert ObjectTableAdvancedEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ObjectTableAdvancedEngine().register(ObjectTableAdvanced(name=f"cap-{i}"))
        assert len(ObjectTableAdvancedEngine().list()) == 100

    def test_singleton(self):
        e1 = ObjectTableAdvancedEngine()
        e2 = ObjectTableAdvancedEngine()
        assert e1 is e2
