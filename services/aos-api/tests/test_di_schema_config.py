"""
W5 — Schema 配置
Tests: SchemaConfigEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.di_schema_config import SchemaConfig, SchemaConfigEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    SchemaConfigEngine().reset()
    yield
    SchemaConfigEngine().reset()


class TestSchemaConfigEngine:
    def test_register(self):
        item = SchemaConfig(name="test-item")
        result = SchemaConfigEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = SchemaConfig(name="get-test")
        SchemaConfigEngine().register(item)
        found = SchemaConfigEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert SchemaConfigEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            SchemaConfigEngine().register(SchemaConfig(name=f"list-{i}"))
        items = SchemaConfigEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = SchemaConfig(name="original")
        SchemaConfigEngine().register(item)
        updated = SchemaConfigEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert SchemaConfigEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = SchemaConfig(name="delete-me")
        SchemaConfigEngine().register(item)
        assert SchemaConfigEngine().delete(item.id) is True
        assert SchemaConfigEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            SchemaConfigEngine().register(SchemaConfig(name=f"cap-{i}"))
        assert len(SchemaConfigEngine().list()) == 100

    def test_singleton(self):
        e1 = SchemaConfigEngine()
        e2 = SchemaConfigEngine()
        assert e1 is e2
