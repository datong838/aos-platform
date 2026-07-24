"""
W6 — Java Transform 集成
Tests: JavaTransformIntegrationEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ms_java_transform_integration import JavaTransformIntegration, JavaTransformIntegrationEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    JavaTransformIntegrationEngine().reset()
    yield
    JavaTransformIntegrationEngine().reset()


class TestJavaTransformIntegrationEngine:
    def test_register(self):
        item = JavaTransformIntegration(name="test-item")
        result = JavaTransformIntegrationEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = JavaTransformIntegration(name="get-test")
        JavaTransformIntegrationEngine().register(item)
        found = JavaTransformIntegrationEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert JavaTransformIntegrationEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            JavaTransformIntegrationEngine().register(JavaTransformIntegration(name=f"list-{i}"))
        items = JavaTransformIntegrationEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = JavaTransformIntegration(name="original")
        JavaTransformIntegrationEngine().register(item)
        updated = JavaTransformIntegrationEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert JavaTransformIntegrationEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = JavaTransformIntegration(name="delete-me")
        JavaTransformIntegrationEngine().register(item)
        assert JavaTransformIntegrationEngine().delete(item.id) is True
        assert JavaTransformIntegrationEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            JavaTransformIntegrationEngine().register(JavaTransformIntegration(name=f"cap-{i}"))
        assert len(JavaTransformIntegrationEngine().list()) == 100

    def test_singleton(self):
        e1 = JavaTransformIntegrationEngine()
        e2 = JavaTransformIntegrationEngine()
        assert e1 is e2
