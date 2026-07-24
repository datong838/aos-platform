"""
W5 — 内联编辑
Tests: InlineEditEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ob_inline_edit import InlineEdit, InlineEditEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    InlineEditEngine().reset()
    yield
    InlineEditEngine().reset()


class TestInlineEditEngine:
    def test_register(self):
        item = InlineEdit(name="test-item")
        result = InlineEditEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = InlineEdit(name="get-test")
        InlineEditEngine().register(item)
        found = InlineEditEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert InlineEditEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            InlineEditEngine().register(InlineEdit(name=f"list-{i}"))
        items = InlineEditEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = InlineEdit(name="original")
        InlineEditEngine().register(item)
        updated = InlineEditEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert InlineEditEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = InlineEdit(name="delete-me")
        InlineEditEngine().register(item)
        assert InlineEditEngine().delete(item.id) is True
        assert InlineEditEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            InlineEditEngine().register(InlineEdit(name=f"cap-{i}"))
        assert len(InlineEditEngine().list()) == 100

    def test_singleton(self):
        e1 = InlineEditEngine()
        e2 = InlineEditEngine()
        assert e1 is e2
