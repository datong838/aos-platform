"""
W5 — 列名自动补全
Tests: ColumnAutocompleteEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_col_autocomplete import ColumnAutocomplete, ColumnAutocompleteEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ColumnAutocompleteEngine().reset()
    yield
    ColumnAutocompleteEngine().reset()


class TestColumnAutocompleteEngine:
    def test_register(self):
        item = ColumnAutocomplete(name="test-item")
        result = ColumnAutocompleteEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ColumnAutocomplete(name="get-test")
        ColumnAutocompleteEngine().register(item)
        found = ColumnAutocompleteEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ColumnAutocompleteEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ColumnAutocompleteEngine().register(ColumnAutocomplete(name=f"list-{i}"))
        items = ColumnAutocompleteEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ColumnAutocomplete(name="original")
        ColumnAutocompleteEngine().register(item)
        updated = ColumnAutocompleteEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ColumnAutocompleteEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ColumnAutocomplete(name="delete-me")
        ColumnAutocompleteEngine().register(item)
        assert ColumnAutocompleteEngine().delete(item.id) is True
        assert ColumnAutocompleteEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ColumnAutocompleteEngine().register(ColumnAutocomplete(name=f"cap-{i}"))
        assert len(ColumnAutocompleteEngine().list()) == 100

    def test_singleton(self):
        e1 = ColumnAutocompleteEngine()
        e2 = ColumnAutocompleteEngine()
        assert e1 is e2
