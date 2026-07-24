"""
W6 — API 文档 JavaDoc
Tests: ApiJavadocEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_api_javadoc import ApiJavadoc, ApiJavadocEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    ApiJavadocEngine().reset()
    yield
    ApiJavadocEngine().reset()


class TestApiJavadocEngine:
    def test_register(self):
        item = ApiJavadoc(name="test-item")
        result = ApiJavadocEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = ApiJavadoc(name="get-test")
        ApiJavadocEngine().register(item)
        found = ApiJavadocEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert ApiJavadocEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            ApiJavadocEngine().register(ApiJavadoc(name=f"list-{i}"))
        items = ApiJavadocEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = ApiJavadoc(name="original")
        ApiJavadocEngine().register(item)
        updated = ApiJavadocEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert ApiJavadocEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = ApiJavadoc(name="delete-me")
        ApiJavadocEngine().register(item)
        assert ApiJavadocEngine().delete(item.id) is True
        assert ApiJavadocEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            ApiJavadocEngine().register(ApiJavadoc(name=f"cap-{i}"))
        assert len(ApiJavadocEngine().list()) == 100

    def test_singleton(self):
        e1 = ApiJavadocEngine()
        e2 = ApiJavadocEngine()
        assert e1 is e2
