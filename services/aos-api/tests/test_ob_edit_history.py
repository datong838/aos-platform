"""
W5 — 编辑历史保留
Tests: EditHistoryEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_edit_history import EditHistory, EditHistoryEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    EditHistoryEngine().reset()
    yield
    EditHistoryEngine().reset()


class TestEditHistoryEngine:
    def test_register(self):
        item = EditHistory(name="test-item")
        result = EditHistoryEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = EditHistory(name="get-test")
        EditHistoryEngine().register(item)
        found = EditHistoryEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert EditHistoryEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            EditHistoryEngine().register(EditHistory(name=f"list-{i}"))
        items = EditHistoryEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = EditHistory(name="original")
        EditHistoryEngine().register(item)
        updated = EditHistoryEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert EditHistoryEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = EditHistory(name="delete-me")
        EditHistoryEngine().register(item)
        assert EditHistoryEngine().delete(item.id) is True
        assert EditHistoryEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            EditHistoryEngine().register(EditHistory(name=f"cap-{i}"))
        assert len(EditHistoryEngine().list()) == 100

    def test_singleton(self):
        e1 = EditHistoryEngine()
        e2 = EditHistoryEngine()
        assert e1 is e2
