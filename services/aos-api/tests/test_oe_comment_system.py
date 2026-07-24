"""
W5 — 评论系统
Tests: CommentEntryEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.oe_comment_system import CommentEntry, CommentEntryEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    CommentEntryEngine().reset()
    yield
    CommentEntryEngine().reset()


class TestCommentEntryEngine:
    def test_register(self):
        item = CommentEntry(name="test-item")
        result = CommentEntryEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = CommentEntry(name="get-test")
        CommentEntryEngine().register(item)
        found = CommentEntryEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert CommentEntryEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            CommentEntryEngine().register(CommentEntry(name=f"list-{i}"))
        items = CommentEntryEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = CommentEntry(name="original")
        CommentEntryEngine().register(item)
        updated = CommentEntryEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert CommentEntryEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = CommentEntry(name="delete-me")
        CommentEntryEngine().register(item)
        assert CommentEntryEngine().delete(item.id) is True
        assert CommentEntryEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            CommentEntryEngine().register(CommentEntry(name=f"cap-{i}"))
        assert len(CommentEntryEngine().list()) == 100

    def test_singleton(self):
        e1 = CommentEntryEngine()
        e2 = CommentEntryEngine()
        assert e1 is e2
