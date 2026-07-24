"""
W6 — 表单解析器
Tests: FormParserEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_form_parser import FormParser, FormParserEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    FormParserEngine().reset()
    yield
    FormParserEngine().reset()


class TestFormParserEngine:
    def test_register(self):
        item = FormParser(name="test-item")
        result = FormParserEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = FormParser(name="get-test")
        FormParserEngine().register(item)
        found = FormParserEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert FormParserEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            FormParserEngine().register(FormParser(name=f"list-{i}"))
        items = FormParserEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = FormParser(name="original")
        FormParserEngine().register(item)
        updated = FormParserEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert FormParserEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = FormParser(name="delete-me")
        FormParserEngine().register(item)
        assert FormParserEngine().delete(item.id) is True
        assert FormParserEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            FormParserEngine().register(FormParser(name=f"cap-{i}"))
        assert len(FormParserEngine().list()) == 100

    def test_singleton(self):
        e1 = FormParserEngine()
        e2 = FormParserEngine()
        assert e1 is e2
