"""
W5 — Python Transform 代码片段
Tests: PythonSnippetEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.id_python_snippet import PythonSnippet, PythonSnippetEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PythonSnippetEngine().reset()
    yield
    PythonSnippetEngine().reset()


class TestPythonSnippetEngine:
    def test_register(self):
        item = PythonSnippet(name="test-item")
        result = PythonSnippetEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PythonSnippet(name="get-test")
        PythonSnippetEngine().register(item)
        found = PythonSnippetEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PythonSnippetEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PythonSnippetEngine().register(PythonSnippet(name=f"list-{i}"))
        items = PythonSnippetEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PythonSnippet(name="original")
        PythonSnippetEngine().register(item)
        updated = PythonSnippetEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PythonSnippetEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PythonSnippet(name="delete-me")
        PythonSnippetEngine().register(item)
        assert PythonSnippetEngine().delete(item.id) is True
        assert PythonSnippetEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PythonSnippetEngine().register(PythonSnippet(name=f"cap-{i}"))
        assert len(PythonSnippetEngine().list()) == 100

    def test_singleton(self):
        e1 = PythonSnippetEngine()
        e2 = PythonSnippetEngine()
        assert e1 is e2
