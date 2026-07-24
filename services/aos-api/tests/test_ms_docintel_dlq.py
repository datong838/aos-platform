"""
W5 — DocIntel 死信队列
Tests: DocIntelDlqEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_docintel_dlq import DocIntelDlq, DocIntelDlqEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DocIntelDlqEngine().reset()
    yield
    DocIntelDlqEngine().reset()


class TestDocIntelDlqEngine:
    def test_register(self):
        item = DocIntelDlq(name="test-item")
        result = DocIntelDlqEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DocIntelDlq(name="get-test")
        DocIntelDlqEngine().register(item)
        found = DocIntelDlqEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DocIntelDlqEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DocIntelDlqEngine().register(DocIntelDlq(name=f"list-{i}"))
        items = DocIntelDlqEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DocIntelDlq(name="original")
        DocIntelDlqEngine().register(item)
        updated = DocIntelDlqEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DocIntelDlqEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DocIntelDlq(name="delete-me")
        DocIntelDlqEngine().register(item)
        assert DocIntelDlqEngine().delete(item.id) is True
        assert DocIntelDlqEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DocIntelDlqEngine().register(DocIntelDlq(name=f"cap-{i}"))
        assert len(DocIntelDlqEngine().list()) == 100

    def test_singleton(self):
        e1 = DocIntelDlqEngine()
        e2 = DocIntelDlqEngine()
        assert e1 is e2
