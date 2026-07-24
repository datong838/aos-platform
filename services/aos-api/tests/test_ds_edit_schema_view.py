"""
W5 — 编辑模式视图
Tests: EditSchemaViewEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_edit_schema_view import EditSchemaView, EditSchemaViewEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    EditSchemaViewEngine().reset()
    yield
    EditSchemaViewEngine().reset()


class TestEditSchemaViewEngine:
    def test_register(self):
        item = EditSchemaView(name="test-item")
        result = EditSchemaViewEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = EditSchemaView(name="get-test")
        EditSchemaViewEngine().register(item)
        found = EditSchemaViewEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert EditSchemaViewEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            EditSchemaViewEngine().register(EditSchemaView(name=f"list-{i}"))
        items = EditSchemaViewEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = EditSchemaView(name="original")
        EditSchemaViewEngine().register(item)
        updated = EditSchemaViewEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert EditSchemaViewEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = EditSchemaView(name="delete-me")
        EditSchemaViewEngine().register(item)
        assert EditSchemaViewEngine().delete(item.id) is True
        assert EditSchemaViewEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            EditSchemaViewEngine().register(EditSchemaView(name=f"cap-{i}"))
        assert len(EditSchemaViewEngine().list()) == 100

    def test_singleton(self):
        e1 = EditSchemaViewEngine()
        e2 = EditSchemaViewEngine()
        assert e1 is e2
