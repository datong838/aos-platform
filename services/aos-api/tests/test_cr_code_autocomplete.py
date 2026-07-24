"""
W6 — 代码自动完成
Tests: CodeAutocompleteEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_code_autocomplete import CodeAutocomplete, CodeAutocompleteEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CodeAutocompleteEngine().reset()
    yield
    CodeAutocompleteEngine().reset()


class TestCodeAutocompleteEngine:
    def test_register(self):
        item = CodeAutocomplete(name="test-item")
        result = CodeAutocompleteEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CodeAutocomplete(name="get-test")
        CodeAutocompleteEngine().register(item)
        found = CodeAutocompleteEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CodeAutocompleteEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CodeAutocompleteEngine().register(CodeAutocomplete(name=f"list-{i}"))
        items = CodeAutocompleteEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CodeAutocomplete(name="original")
        CodeAutocompleteEngine().register(item)
        updated = CodeAutocompleteEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CodeAutocompleteEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CodeAutocomplete(name="delete-me")
        CodeAutocompleteEngine().register(item)
        assert CodeAutocompleteEngine().delete(item.id) is True
        assert CodeAutocompleteEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CodeAutocompleteEngine().register(CodeAutocomplete(name=f"cap-{i}"))
        assert len(CodeAutocompleteEngine().list()) == 100

    def test_singleton(self):
        e1 = CodeAutocompleteEngine()
        e2 = CodeAutocompleteEngine()
        assert e1 is e2
