"""
W5 — 标记再审批要求
Tests: TagReapprovalEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_tag_reapproval import TagReapproval, TagReapprovalEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    TagReapprovalEngine().reset()
    yield
    TagReapprovalEngine().reset()


class TestTagReapprovalEngine:
    def test_register(self):
        item = TagReapproval(name="test-item")
        result = TagReapprovalEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = TagReapproval(name="get-test")
        TagReapprovalEngine().register(item)
        found = TagReapprovalEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert TagReapprovalEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            TagReapprovalEngine().register(TagReapproval(name=f"list-{i}"))
        items = TagReapprovalEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = TagReapproval(name="original")
        TagReapprovalEngine().register(item)
        updated = TagReapprovalEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert TagReapprovalEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = TagReapproval(name="delete-me")
        TagReapprovalEngine().register(item)
        assert TagReapprovalEngine().delete(item.id) is True
        assert TagReapprovalEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            TagReapprovalEngine().register(TagReapproval(name=f"cap-{i}"))
        assert len(TagReapprovalEngine().list()) == 100

    def test_singleton(self):
        e1 = TagReapprovalEngine()
        e2 = TagReapprovalEngine()
        assert e1 is e2
