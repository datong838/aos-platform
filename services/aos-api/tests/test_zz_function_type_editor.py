"""
W6 — Function Type 编辑器
Tests: FunctionTypeEditorEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.zz_function_type_editor import FunctionTypeEditor, FunctionTypeEditorEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    FunctionTypeEditorEngine().reset()
    yield
    FunctionTypeEditorEngine().reset()


class TestFunctionTypeEditorEngine:
    def test_register(self):
        item = FunctionTypeEditor(name="test-item")
        result = FunctionTypeEditorEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = FunctionTypeEditor(name="get-test")
        FunctionTypeEditorEngine().register(item)
        found = FunctionTypeEditorEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert FunctionTypeEditorEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            FunctionTypeEditorEngine().register(FunctionTypeEditor(name=f"list-{i}"))
        items = FunctionTypeEditorEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = FunctionTypeEditor(name="original")
        FunctionTypeEditorEngine().register(item)
        updated = FunctionTypeEditorEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert FunctionTypeEditorEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = FunctionTypeEditor(name="delete-me")
        FunctionTypeEditorEngine().register(item)
        assert FunctionTypeEditorEngine().delete(item.id) is True
        assert FunctionTypeEditorEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            FunctionTypeEditorEngine().register(FunctionTypeEditor(name=f"cap-{i}"))
        assert len(FunctionTypeEditorEngine().list()) == 100

    def test_singleton(self):
        e1 = FunctionTypeEditorEngine()
        e2 = FunctionTypeEditorEngine()
        assert e1 is e2
