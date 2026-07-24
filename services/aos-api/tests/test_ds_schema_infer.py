"""
W5 — 模式推断验证
Tests: SchemaInferenceEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.ds_schema_infer import SchemaInference, SchemaInferenceEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SchemaInferenceEngine().reset()
    yield
    SchemaInferenceEngine().reset()


class TestSchemaInferenceEngine:
    def test_register(self):
        item = SchemaInference(name="test-item")
        result = SchemaInferenceEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SchemaInference(name="get-test")
        SchemaInferenceEngine().register(item)
        found = SchemaInferenceEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SchemaInferenceEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SchemaInferenceEngine().register(SchemaInference(name=f"list-{i}"))
        items = SchemaInferenceEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SchemaInference(name="original")
        SchemaInferenceEngine().register(item)
        updated = SchemaInferenceEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SchemaInferenceEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SchemaInference(name="delete-me")
        SchemaInferenceEngine().register(item)
        assert SchemaInferenceEngine().delete(item.id) is True
        assert SchemaInferenceEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SchemaInferenceEngine().register(SchemaInference(name=f"cap-{i}"))
        assert len(SchemaInferenceEngine().list()) == 100

    def test_singleton(self):
        e1 = SchemaInferenceEngine()
        e2 = SchemaInferenceEngine()
        assert e1 is e2
