"""
W5 — Schema 推断
Tests: PpSchemaInferEngine CRUD + singleton + capacity
"""
import threading

import pytest

from aos_api.pp_schema_infer import PpSchemaInfer, PpSchemaInferEngine


@pytest.fixture(autouse=True)
def _reset():
    """Clear engine before each test."""
    PpSchemaInferEngine().reset()
    yield
    PpSchemaInferEngine().reset()


class TestPpSchemaInferEngine:
    def test_register(self):
        item = PpSchemaInfer(name="test-item")
        result = PpSchemaInferEngine().register(item)
        assert result.id == item.id
        assert result.name == "test-item"

    def test_get(self):
        item = PpSchemaInfer(name="get-test")
        PpSchemaInferEngine().register(item)
        found = PpSchemaInferEngine().get(item.id)
        assert found is not None
        assert found.name == "get-test"

    def test_get_not_found(self):
        assert PpSchemaInferEngine().get("nonexistent-id") is None

    def test_list(self):
        for i in range(5):
            PpSchemaInferEngine().register(PpSchemaInfer(name=f"list-{i}"))
        items = PpSchemaInferEngine().list()
        assert len(items) == 5

    def test_update(self):
        item = PpSchemaInfer(name="original")
        PpSchemaInferEngine().register(item)
        updated = PpSchemaInferEngine().update(item.id, {"name": "updated", "enabled": False})
        assert updated is not None
        assert updated.name == "updated"
        assert updated.enabled is False

    def test_update_not_found(self):
        assert PpSchemaInferEngine().update("no-id", {"name": "x"}) is None

    def test_delete(self):
        item = PpSchemaInfer(name="delete-me")
        PpSchemaInferEngine().register(item)
        assert PpSchemaInferEngine().delete(item.id) is True
        assert PpSchemaInferEngine().get(item.id) is None

    def test_capacity_limit(self):
        """Engine handles large number of entries."""
        for i in range(100):
            PpSchemaInferEngine().register(PpSchemaInfer(name=f"cap-{i}"))
        assert len(PpSchemaInferEngine().list()) == 100

    def test_singleton(self):
        e1 = PpSchemaInferEngine()
        e2 = PpSchemaInferEngine()
        assert e1 is e2
