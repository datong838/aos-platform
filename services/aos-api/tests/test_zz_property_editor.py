"""
W6 — Property Editor
Tests: PropertyEditorEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.zz_property_editor import PropertyEditor, PropertyEditorEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PropertyEditorEngine().reset()
    yield
    PropertyEditorEngine().reset()


class TestPropertyEditorEngine:
    def test_register(self):
        item = PropertyEditor(name="test-item")
        result = PropertyEditorEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PropertyEditor(name="get-test")
        PropertyEditorEngine().register(item)
        found = PropertyEditorEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PropertyEditorEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PropertyEditorEngine().register(PropertyEditor(name=f"list-{i}"))
        items = PropertyEditorEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PropertyEditor(name="original")
        PropertyEditorEngine().register(item)
        updated = PropertyEditorEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PropertyEditorEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PropertyEditor(name="delete-me")
        PropertyEditorEngine().register(item)
        assert PropertyEditorEngine().delete(item.id) is True
        assert PropertyEditorEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PropertyEditorEngine().register(PropertyEditor(name=f"cap-{i}"))
        assert len(PropertyEditorEngine().list()) == 100

    def test_singleton(self):
        e1 = PropertyEditorEngine()
        e2 = PropertyEditorEngine()
        assert e1 is e2
