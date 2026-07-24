"""
W6 — Java 变换 API
Tests: JavaTransformApiEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.mt_java_transform_api import JavaTransformApi, JavaTransformApiEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    JavaTransformApiEngine().reset()
    yield
    JavaTransformApiEngine().reset()


class TestJavaTransformApiEngine:
    def test_register(self):
        item = JavaTransformApi(name="test-item")
        result = JavaTransformApiEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = JavaTransformApi(name="get-test")
        JavaTransformApiEngine().register(item)
        found = JavaTransformApiEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert JavaTransformApiEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            JavaTransformApiEngine().register(JavaTransformApi(name=f"list-{i}"))
        items = JavaTransformApiEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = JavaTransformApi(name="original")
        JavaTransformApiEngine().register(item)
        updated = JavaTransformApiEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert JavaTransformApiEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = JavaTransformApi(name="delete-me")
        JavaTransformApiEngine().register(item)
        assert JavaTransformApiEngine().delete(item.id) is True
        assert JavaTransformApiEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            JavaTransformApiEngine().register(JavaTransformApi(name=f"cap-{i}"))
        assert len(JavaTransformApiEngine().list()) == 100

    def test_singleton(self):
        e1 = JavaTransformApiEngine()
        e2 = JavaTransformApiEngine()
        assert e1 is e2
