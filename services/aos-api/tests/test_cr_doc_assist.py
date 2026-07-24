"""
W5 — 文档辅助
Tests: DocAssistEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.cr_doc_assist import DocAssist, DocAssistEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    DocAssistEngine().reset()
    yield
    DocAssistEngine().reset()


class TestDocAssistEngine:
    def test_register(self):
        item = DocAssist(name="test-item")
        result = DocAssistEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = DocAssist(name="get-test")
        DocAssistEngine().register(item)
        found = DocAssistEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert DocAssistEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            DocAssistEngine().register(DocAssist(name=f"list-{i}"))
        items = DocAssistEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = DocAssist(name="original")
        DocAssistEngine().register(item)
        updated = DocAssistEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert DocAssistEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = DocAssist(name="delete-me")
        DocAssistEngine().register(item)
        assert DocAssistEngine().delete(item.id) is True
        assert DocAssistEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            DocAssistEngine().register(DocAssist(name=f"cap-{i}"))
        assert len(DocAssistEngine().list()) == 100

    def test_singleton(self):
        e1 = DocAssistEngine()
        e2 = DocAssistEngine()
        assert e1 is e2
